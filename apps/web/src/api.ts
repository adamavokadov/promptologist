import type { GenerationDTO, ResultDTO, SystemId } from '../../../shared/src/index.ts';
import { t } from './strings.ru.ts';

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string, public retryAfter?: number) { super(message); }
}

// ---- cold-start ("app is waking") state, observable by the shell ----
type WakeListener = (waking: boolean) => void;
const wakeListeners = new Set<WakeListener>();
let wakeCount = 0;
export const onWake = (cb: WakeListener): (() => void) => { wakeListeners.add(cb); return () => { wakeListeners.delete(cb); }; };
const setWake = (delta: number) => { const before = wakeCount > 0; wakeCount = Math.max(0, wakeCount + delta); const after = wakeCount > 0; if (before !== after) wakeListeners.forEach((l) => l(after)); };
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
const WAKE_BUDGET_MS = 5 * 60_000;

async function request<T>(path: string, init: { method?: string; body?: unknown } = {}): Promise<T> {
  const method = init.method ?? 'GET';
  const started = Date.now(); let waking = false; let attempt = 0;
  try {
    for (;;) {
      const slow = setTimeout(() => { if (method === 'GET' && !waking) { waking = true; setWake(1); } }, 3000);
      try {
        const res = await fetch(path, { method, headers: init.body !== undefined ? { 'Content-Type': 'application/json' } : undefined, body: init.body !== undefined ? JSON.stringify(init.body) : undefined });
        clearTimeout(slow);
        const text = await res.text(); let json: any = null;
        try { json = text ? JSON.parse(text) : null; } catch { json = null; }
        const retryable = method === 'GET' || json?.error?.code === 'starting';
        if (res.status === 503 && retryable && Date.now() - started < WAKE_BUDGET_MS) {
          if (!waking) { waking = true; setWake(1); }
          const ra = Number(res.headers.get('retry-after')); await sleep((Number.isFinite(ra) && ra > 0 ? Math.min(ra, 20) : Math.min(2 + attempt, 10)) * 1000); attempt++; continue;
        }
        if (!res.ok) throw new ApiError(res.status, json?.error?.code ?? `http_${res.status}`, json?.error?.message ?? t.common.error, Number(res.headers.get('retry-after')) || undefined);
        return json as T;
      } catch (e) {
        clearTimeout(slow);
        if (e instanceof ApiError) throw e;
        const isGet = method === 'GET';
        if (isGet && Date.now() - started < WAKE_BUDGET_MS) { if (!waking) { waking = true; setWake(1); } await sleep(Math.min(2 + attempt, 10) * 1000); attempt++; continue; }
        throw new ApiError(0, 'network', t.common.error);
      }
    }
  } finally { if (waking) setWake(-1); }
}
export const get = <T>(p: string) => request<T>(p);
export const post = <T>(p: string, body: unknown = {}) => request<T>(p, { method: 'POST', body });
export const put = <T>(p: string, body: unknown) => request<T>(p, { method: 'PUT', body });
export const patch = <T>(p: string, body: unknown) => request<T>(p, { method: 'PATCH', body });
export const del = <T>(p: string) => request<T>(p, { method: 'DELETE' });

async function* sseFrames(body: ReadableStream<Uint8Array>) {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  try {
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let end: number;
      while ((end = buffer.indexOf('\n\n')) >= 0) {
        const frame = buffer.slice(0, end);
        buffer = buffer.slice(end + 2);
        const type = /^event: (.+)$/m.exec(frame)?.[1];
        const data = /^data: (.+)$/m.exec(frame)?.[1];
        if (type && data) yield { type, data };
      }
    }
  } finally {
    await reader.cancel().catch(() => {});
    reader.releaseLock();
  }
}

export async function postPrompt<T>(path: string, body: unknown = {}): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' }, body: JSON.stringify(body) });
  } catch { throw new ApiError(0, 'network', t.common.error); }
  if (!res.ok) {
    const data = await res.json().catch(() => null);
    throw new ApiError(res.status, data?.error?.code ?? 'error', data?.error?.message ?? t.common.error,
      Number(res.headers.get('retry-after')) || undefined);
  }
  if (!res.body || !res.headers.get('content-type')?.includes('text/event-stream')) {
    const data = await res.json().catch(() => null);
    if (data === null) throw new ApiError(0, 'stream', t.prompt.streamInterrupted);
    return data as T;
  }
  try {
    for await (const frame of sseFrames(res.body)) {
      if (frame.type === 'result') return JSON.parse(frame.data) as T;
      if (frame.type === 'failure') {
        const error = JSON.parse(frame.data);
        throw new ApiError(error.status, error.code, error.message, error.retryAfter);
      }
    }
  } catch (error) {
    if (error instanceof ApiError) throw error;
  }
  throw new ApiError(0, 'stream', t.prompt.streamInterrupted);
}

// ---- generation transport: SSE over fetch, with polling fallback ----
export interface GenHandlers {
  onStart?: (id: string) => void; onIntent?: () => void; onCardStart?: (s: SystemId) => void; onCard?: (r: ResultDTO) => void; onCardError?: (s: SystemId, e: string, r?: ResultDTO) => void;
  onQuestions?: (list: string[], id: string) => void; onDone?: (id: string, status: string) => void; onFallback?: () => void; onError?: (e: ApiError) => void;
}
export async function streamGenerate(path: string, body: unknown, h: GenHandlers): Promise<void> {
  let genId = ''; let gotEvent = false; let finished = false; let polling = false; const seen = new Set<string>();
  const finish = (id: string, status: string) => { if (finished) return; finished = true; h.onDone?.(id, status); };
  const poll = async () => {
    if (polling || !genId) return; polling = true; h.onFallback?.();
    while (!finished) {
      await sleep(2000);
      try {
        const g = await get<GenerationDTO>(`/api/generations/${genId}`);
        for (const r of g.results) if (!seen.has(r.id)) { seen.add(r.id); r.status === 'ok' ? h.onCard?.(r) : h.onCardError?.(r.skill_id, r.error ?? '', r); }
        if (g.status === 'draft_questions') { h.onQuestions?.(g.questions ?? [], g.id); finish(g.id, g.status); }
        else if (g.status !== 'running') finish(g.id, g.status);
      } catch (e) { if (e instanceof ApiError && e.status === 404) { finish(genId, 'failed'); } }
    }
  };
  const handle = (type: string, data: any) => {
    gotEvent = true;
    switch (type) {
      case 'start': genId = data.generation_id; h.onStart?.(genId); break;
      case 'intent': h.onIntent?.(); break;
      case 'card_start': h.onCardStart?.(data.system); break;
      case 'card_done': seen.add(data.result.id); h.onCard?.(data.result); break;
      case 'card_error': if (data.result) seen.add(data.result.id); h.onCardError?.(data.system, data.error, data.result); break;
      case 'questions': h.onQuestions?.(data.list, data.generation_id); break;
      case 'done': finish(data.generation_id || genId, data.status); break;
    }
  };
  let res: Response;
  try { res = await fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' }, body: JSON.stringify(body) }); }
  catch { h.onError?.(new ApiError(0, 'network', t.common.error)); return; }
  if (!res.ok || !res.body) {
    let j: any = null; try { j = await res.json(); } catch { /* ignore */ }
    h.onError?.(new ApiError(res.status, j?.error?.code ?? 'error', j?.error?.message ?? t.common.error, Number(res.headers.get('retry-after')) || undefined)); return;
  }
  genId = res.headers.get('x-generation-id') ?? '';
  // If the proxy buffers the stream, no events arrive: fall back to polling after 5 seconds.
  const watchdog = setTimeout(() => { if (!gotEvent && !finished) void poll(); }, 5000);
  try {
    for await (const frame of sseFrames(res.body)) {
      if (finished) break;
      try { handle(frame.type, JSON.parse(frame.data)); } catch { /* ignore malformed frame */ }
    }
  } catch { /* stream broke: fall back to polling below */ }
  clearTimeout(watchdog);
  if (!finished) { if (genId) await poll(); else h.onError?.(new ApiError(0, 'stream', t.common.error)); }
}
