import { config, maskSecrets } from './config.ts';
import { sleep, log } from './util.ts';

export type VibeErrorKind = 'quota' | 'rate_limit' | 'congested' | 'auth' | 'invalid' | 'server' | 'network' | 'timeout' | 'other';
export class VibeError extends Error {
  constructor(public status: number, public code: string, message: string, public kind: VibeErrorKind, public retryAfter?: number) {
    super(maskSecrets(message));
  }
}

/** Parses BOTH error envelopes: raw OpenAI {error:{message,type,code}} and V1 {success:false,error:{code,message}}. */
export function parseErrorEnvelope(status: number, body: any, retryAfterHeader?: string | null): VibeError {
  const err = body?.error ?? {};
  const code = String(err.code ?? err.type ?? `HTTP_${status}`);
  const message = String(err.message ?? err.userMessage ?? `HTTP ${status}`);
  const retryAfter = retryAfterHeader && /^\d+$/.test(retryAfterHeader) ? Number(retryAfterHeader) : (typeof err.retryAfter === 'number' ? err.retryAfter : undefined);
  const lc = code.toLowerCase();
  let kind: VibeErrorKind = 'other';
  if (status === 402 || lc === 'ai_quota_exhausted' || lc === 'insufficient_balance') kind = 'quota';
  else if (status === 429 || lc === 'rate_limit_exceeded') kind = 'rate_limit';
  else if (lc === 'ai_congested' || lc === 'ai_provider_cooldown') kind = 'congested';
  else if (status === 401 || status === 403) kind = 'auth';
  else if (status === 400 || status === 422) kind = 'invalid';
  else if (status >= 500) kind = 'server';
  return new VibeError(status, code, message, kind, retryAfter);
}

export interface ChatMessage { role: 'system' | 'user' | 'assistant'; content: string }
export interface ChatResult { content: string; totalTokens: number; model: string }
export interface SearchResult { id?: string; url: string; title: string; content: string; score?: number; publishedDate?: string | null }
export interface SearchResponse { answer?: string; results: SearchResult[] }

export interface VibeOptions {
  fetchImpl?: typeof fetch;
  sleepImpl?: (ms: number) => Promise<void>;
  apiKey?: string;
  baseUrl?: string;
  maxRetries?: number;
}
export const TIMEOUTS = { llm: 120_000, analyzer: 180_000, search: 60_000, research: 300_000, default: 30_000 } as const;

export function createVibeClient(opts: VibeOptions = {}) {
  const f = opts.fetchImpl ?? fetch;
  const wait = opts.sleepImpl ?? sleep;
  const maxRetries = opts.maxRetries ?? 3;
  const base = () => opts.baseUrl ?? config.baseUrl;
  const key = () => opts.apiKey ?? config.apiKey;

  async function request<T>(path: string, init: { method?: string; body?: unknown; timeoutMs?: number; headers?: Record<string, string>; apiKey?: string; raw?: boolean } = {}): Promise<T> {
    const url = `${base()}${path}`;
    let lastErr: VibeError | undefined;
    for (let attempt = 0; attempt <= maxRetries; attempt++) {
      const ctrl = new AbortController();
      const timer = setTimeout(() => ctrl.abort(), init.timeoutMs ?? TIMEOUTS.default);
      try {
        const res = await f(url, {
          method: init.method ?? (init.body !== undefined ? 'POST' : 'GET'),
          headers: { 'Content-Type': 'application/json', 'X-Api-Key': init.apiKey ?? key(), ...(init.headers ?? {}) },
          body: init.body !== undefined ? JSON.stringify(init.body) : undefined,
          signal: ctrl.signal,
        });
        if (init.raw) { clearTimeout(timer); if (!res.ok) throw parseErrorEnvelope(res.status, await res.json().catch(() => ({})), res.headers.get('retry-after')); return res as unknown as T; }
        const text = await res.text();
        clearTimeout(timer);
        let json: any = {};
        try { json = text ? JSON.parse(text) : {}; } catch { json = { error: { message: text.slice(0, 200) } }; }
        if (res.ok && json?.success !== false) return json as T;
        throw parseErrorEnvelope(res.status, json, res.headers.get('retry-after'));
      } catch (e) {
        clearTimeout(timer);
        const err = e instanceof VibeError ? e
          : (e as Error)?.name === 'AbortError' ? new VibeError(0, 'TIMEOUT', 'Request timed out', 'timeout')
          : new VibeError(0, 'NETWORK', (e as Error)?.message ?? 'network error', 'network');
        lastErr = err;
        const retryable = ['rate_limit', 'congested', 'server', 'network', 'timeout'].includes(err.kind);
        if (!retryable || attempt === maxRetries) throw err;
        const backoff = 500 * 2 ** attempt + Math.floor(Math.random() * 300);
        const delay = err.retryAfter !== undefined ? Math.min(err.retryAfter * 1000, 60_000) : backoff;
        log.warn('vibe retry', { path, attempt: attempt + 1, code: err.code, delay });
        await wait(delay);
      }
    }
    throw lastErr ?? new VibeError(0, 'UNKNOWN', 'unknown error', 'other');
  }

  return {
    request,
    async chat(model: string, messages: ChatMessage[], o: { temperature?: number; maxTokens?: number; json?: boolean; timeoutMs?: number } = {}): Promise<ChatResult> {
      const body: Record<string, unknown> = { model, messages, temperature: o.temperature ?? 0.4, max_tokens: o.maxTokens ?? 4000 };
      if (o.json) body.response_format = { type: 'json_object' };
      const data = await request<any>('/chat/completions', { body, timeoutMs: o.timeoutMs ?? TIMEOUTS.llm });
      const content = data?.choices?.[0]?.message?.content;
      if (typeof content !== 'string') throw new VibeError(502, 'EMPTY_COMPLETION', 'Model returned no content', 'server');
      return { content, totalTokens: Number(data?.usage?.total_tokens ?? 0), model: String(data?.model ?? model) };
    },
    async search(p: { query: string; search_depth?: 'basic' | 'advanced'; max_results?: number; include_domains?: string[]; time_range?: string; provider?: string }): Promise<SearchResponse> {
      const data = await request<any>('/search', { body: p, timeoutMs: TIMEOUTS.search });
      const d = data?.data ?? data;
      return { answer: d?.answer, results: Array.isArray(d?.results) ? d.results : [] };
    },
    async searchProviders(): Promise<any> { return request('/search/providers'); },
    /** Deep research is SSE-only. Parses `data:` frames and returns the concatenated text/final answer. */
    async research(query: string): Promise<{ text: string; tokens: number }> {
      const res = await request<Response>('/research', { body: { query }, timeoutMs: TIMEOUTS.research, raw: true, headers: { Accept: 'text/event-stream' } });
      const reader = res.body?.getReader();
      if (!reader) return { text: '', tokens: 0 };
      const dec = new TextDecoder();
      let buf = ''; let text = ''; let final = '';
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        let idx: number;
        while ((idx = buf.indexOf('\n\n')) >= 0) {
          const frame = buf.slice(0, idx); buf = buf.slice(idx + 2);
          for (const line of frame.split('\n')) {
            if (!line.startsWith('data:')) continue;
            const payload = line.slice(5).trim();
            if (!payload || payload === '[DONE]') continue;
            try {
              const j = JSON.parse(payload);
              if (typeof j.delta === 'string') text += j.delta;
              else if (typeof j.content === 'string') text += j.content;
              if (typeof j.answer === 'string') final = j.answer;
              if (typeof j.overview === 'string' && !final) final = j.overview;
            } catch { text += payload; }
          }
        }
      }
      return { text: final || text, tokens: Math.ceil((final || text).length / 4) };
    },
    async me(bearer: string, appKey = config.appKey): Promise<any> {
      const data = await request<any>('/me', { headers: { Authorization: `Bearer ${bearer}` }, apiKey: appKey });
      return data?.data ?? data;
    },
    async meService(): Promise<any> { const d = await request<any>('/me'); return d?.data ?? d; },
    async models(): Promise<any[]> {
      const d = await request<any>('/models');
      const list = d?.data?.models ?? d?.data ?? d?.models ?? [];
      return Array.isArray(list) ? list : [];
    },
    async usage(days = 30): Promise<any> { const d = await request<any>(`/ai/usage?days=${days}`); return d?.data ?? d; },
    async listJobs(serverId: string): Promise<any[]> {
      const d = await request<any>(`/infra/servers/${encodeURIComponent(serverId)}/jobs`);
      return d?.data?.items ?? [];
    },
    async createJob(serverId: string, body: { label: string; cronExpr: string; timezone: string; path: string; enabled?: boolean }): Promise<any> {
      const d = await request<any>(`/infra/servers/${encodeURIComponent(serverId)}/jobs`, { body });
      return d?.data ?? d;
    },
    /** Best-effort notification; endpoint is unverified on this platform build, failures are swallowed by callers. */
    async notify(userId: string, message: string): Promise<void> {
      await request('/notifications', { body: { userId, message } });
    },
  };
}
export type VibeClient = ReturnType<typeof createVibeClient>;

let singleton: VibeClient | null = null;
export function getVibe(): VibeClient { return (singleton ??= createVibeClient()); }
export function setVibeForTests(c: VibeClient | null): void { singleton = c; }
