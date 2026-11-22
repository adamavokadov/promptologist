import { createCipheriv, createDecipheriv, randomBytes, scryptSync } from 'node:crypto';
import { lookup } from 'node:dns/promises';
import net from 'node:net';
import { config } from './config.ts';
import { type Db } from './db.ts';
import { log, AppError, jsonParse } from './util.ts';
import { VibeError, parseErrorEnvelope, type ChatMessage, type VibeClient } from './vibe.ts';
import { engineConfigSchema, engineUpdateSchema, ENGINE_CATALOG, type EngineConfig, type EngineView, type Provider } from '../../../shared/src/index.ts';
import type { z } from 'zod';

/** Public defaults (from provider docs, overridable with Custom_Base_URL; not verified against Nov 2026 docs). */
export const DEFAULT_BASE_URLS: Record<string, string> = {
  anthropic: 'https://api.anthropic.com', openai: 'https://api.openai.com/v1', google: 'https://generativelanguage.googleapis.com/v1beta',
  alibaba: 'https://dashscope-intl.aliyuncs.com/compatible-mode/v1', moonshot: 'https://api.moonshot.ai/v1',
};
const SETTINGS_KEY = 'engine';
const KEY_SETTINGS_KEY = 'engine_key';
const LLM_TIMEOUT = 120_000;

// ---------- key encryption (AES-256-GCM, secret from ENGINE_SECRET) ----------
function aesKey(): Buffer {
  if (config.engineSecret.length < 16) throw new AppError(409, 'engine_secret_missing', 'ENGINE_SECRET (минимум 16 символов) не задан: ключи API сохранять нельзя');
  return scryptSync(config.engineSecret, 'promptolog-engine-v1', 32);
}
export function encryptSecret(plain: string): string {
  const iv = randomBytes(12); const c = createCipheriv('aes-256-gcm', aesKey(), iv);
  const ct = Buffer.concat([c.update(plain, 'utf8'), c.final()]);
  return ['v1', iv.toString('base64'), c.getAuthTag().toString('base64'), ct.toString('base64')].join(':');
}
export function decryptSecret(blob: string): string {
  const [v, iv, tag, ct] = blob.split(':');
  if (v !== 'v1' || !iv || !tag || !ct) throw new AppError(500, 'engine_key_corrupt', 'Сохранённый ключ повреждён: введите его заново');
  try {
    const d = createDecipheriv('aes-256-gcm', aesKey(), Buffer.from(iv, 'base64')); d.setAuthTag(Buffer.from(tag, 'base64'));
    return Buffer.concat([d.update(Buffer.from(ct, 'base64')), d.final()]).toString('utf8');
  } catch (e) {
    if (e instanceof AppError) throw e;
    throw new AppError(500, 'engine_key_corrupt', 'Ключ не расшифровывается (изменился ENGINE_SECRET?): введите его заново');
  }
}

// ---------- config storage ----------
export function getEngineConfig(db: Db): EngineConfig {
  const row = db.get<{ value: string }>('SELECT value FROM settings WHERE key = ?', SETTINGS_KEY);
  const parsed = engineConfigSchema.safeParse(jsonParse(row?.value, {}));
  return parsed.success ? parsed.data : engineConfigSchema.parse({});
}
function storedKey(db: Db): string {
  const row = db.get<{ value: string }>('SELECT value FROM settings WHERE key = ?', KEY_SETTINGS_KEY);
  return jsonParse<string>(row?.value, '');
}
export function engineView(db: Db): EngineView {
  const cfg = getEngineConfig(db); const blob = storedKey(db);
  let hint = '';
  if (blob) { try { const k = decryptSecret(blob); hint = k.length > 8 ? `…${k.slice(-4)}` : '…'; } catch { hint = ''; } }
  return { ...cfg, has_key: !!blob, key_hint: hint, secret_configured: config.engineSecret.length >= 16, catalog: ENGINE_CATALOG, default_base_urls: DEFAULT_BASE_URLS };
}
export async function updateEngine(db: Db, input: z.infer<typeof engineUpdateSchema>): Promise<EngineView> {
  const body = engineUpdateSchema.parse(input);
  const next = engineConfigSchema.parse({ ...getEngineConfig(db), ...Object.fromEntries(Object.entries(body).filter(([k, v]) => k !== 'api_key' && v !== undefined)) });
  if (next.base_url) await assertSafeBaseUrl(next.base_url);
  if (next.provider === 'custom' && !next.base_url) throw new AppError(400, 'base_url_required', 'Для custom-провайдера нужен Custom Base URL');
  const put = (k: string, v: unknown) => db.run('INSERT INTO settings(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value', k, JSON.stringify(v));
  const del = (k: string) => db.run('DELETE FROM settings WHERE key = ?', k);
  // Encrypt first: a missing ENGINE_SECRET must fail before anything is written.
  const blob = body.api_key === undefined ? undefined : body.api_key === '' ? '' : encryptSecret(body.api_key.trim());
  db.tx(() => { put(SETTINGS_KEY, next); if (blob === '') del(KEY_SETTINGS_KEY); else if (blob) put(KEY_SETTINGS_KEY, blob); });
  return engineView(db);
}

// ---------- SSRF guard for Custom_Base_URL ----------
export function isPrivateAddress(ip: string): boolean {
  if (net.isIPv4(ip)) {
    const [a, b] = ip.split('.').map(Number) as [number, number];
    return a === 10 || a === 127 || a === 0 || (a === 169 && b === 254) || (a === 172 && b >= 16 && b <= 31) || (a === 192 && b === 168) || (a === 100 && b >= 64 && b <= 127);
  }
  const v = ip.toLowerCase();
  if (v.startsWith('::ffff:')) return isPrivateAddress(v.slice(7));
  return v === '::1' || v === '::' || v.startsWith('fc') || v.startsWith('fd') || v.startsWith('fe80');
}
export async function assertSafeBaseUrl(raw: string): Promise<URL> {
  let u: URL;
  try { u = new URL(raw); } catch { throw new AppError(400, 'bad_base_url', 'Custom Base URL: некорректный адрес'); }
  const allowPrivate = config.engineAllowPrivate;
  if (u.protocol !== 'https:' && !(allowPrivate && u.protocol === 'http:')) throw new AppError(400, 'bad_base_url', 'Custom Base URL должен начинаться с https://');
  if (u.username || u.password) throw new AppError(400, 'bad_base_url', 'Custom Base URL не должен содержать логин и пароль');
  if (allowPrivate) return u;
  const host = u.hostname.replace(/^\[|\]$/g, '');
  const addrs = net.isIP(host) ? [host] : (await lookup(host, { all: true }).catch(() => { throw new AppError(400, 'bad_base_url', 'Custom Base URL: хост не найден'); })).map((a) => a.address);
  if (host === 'localhost' || addrs.some(isPrivateAddress)) throw new AppError(400, 'bad_base_url', 'Custom Base URL указывает на внутренний адрес: это запрещено');
  return u;
}

// ---------- provider adapters ----------
export interface EngineChat { content: string; tokens: number; model: string; provider: Provider }
export interface EngineDeps { vibe: VibeClient; fetchImpl?: typeof fetch }

function redact(text: string, key: string): string { return key ? text.split(key).join('***') : text; }
async function httpJson(f: typeof fetch, url: string, headers: Record<string, string>, body: unknown, key: string): Promise<any> {
  const ctrl = new AbortController(); const timer = setTimeout(() => ctrl.abort(), LLM_TIMEOUT);
  try {
    const res = await f(url, { method: 'POST', headers: { 'Content-Type': 'application/json', ...headers }, body: JSON.stringify(body), signal: ctrl.signal, redirect: 'error' });
    const text = await res.text(); let json: any = {};
    try { json = text ? JSON.parse(text) : {}; } catch { json = { error: { message: redact(text.slice(0, 200), key) } }; }
    if (!res.ok) { const e = parseErrorEnvelope(res.status, json, res.headers.get('retry-after')); throw new VibeError(e.status, e.code, redact(e.message, key), e.kind, e.retryAfter); }
    return json;
  } catch (e) {
    if (e instanceof VibeError) throw e;
    if ((e as Error)?.name === 'AbortError') throw new VibeError(0, 'TIMEOUT', 'Request timed out', 'timeout');
    throw new VibeError(0, 'NETWORK', redact((e as Error)?.message ?? 'network error', key), 'network');
  } finally { clearTimeout(timer); }
}

/** One chat completion through the configured engine. JSON mode is a hint only; callers always validate. */
export async function engineChat(db: Db, deps: EngineDeps, messages: ChatMessage[], o: { json?: boolean; maxTokens?: number } = {}): Promise<EngineChat> {
  const cfg = getEngineConfig(db); const f = deps.fetchImpl ?? fetch; const maxTokens = o.maxTokens ?? 4000;
  if (cfg.provider === 'platform') {
    const r = await deps.vibe.chat(cfg.model, messages, { temperature: cfg.temperature, maxTokens, json: o.json });
    return { content: r.content, tokens: r.totalTokens, model: r.model, provider: 'platform' };
  }
  const blob = storedKey(db);
  if (!blob) throw new AppError(409, 'engine_key_missing', 'Для выбранного провайдера не задан ключ API (Настройки, Движок)');
  const key = decryptSecret(blob);
  const base = (cfg.base_url || DEFAULT_BASE_URLS[cfg.provider] || '').replace(/\/+$/, '');
  if (!base) throw new AppError(400, 'base_url_required', 'Для custom-провайдера нужен Custom Base URL');
  if (cfg.base_url) await assertSafeBaseUrl(cfg.base_url);
  const sys = messages.filter((m) => m.role === 'system').map((m) => m.content).join('\n\n'); const rest = messages.filter((m) => m.role !== 'system');
  try {
    if (cfg.provider === 'anthropic') {
      const j = await httpJson(f, `${base}/v1/messages`, { 'x-api-key': key, 'anthropic-version': '2023-06-01' },
        { model: cfg.model, max_tokens: maxTokens, temperature: Math.min(1, cfg.temperature), system: sys, messages: rest.map((m) => ({ role: m.role, content: m.content })) }, key);
      const text = (Array.isArray(j.content) ? j.content : []).filter((b: any) => b?.type === 'text').map((b: any) => b.text).join('');
      if (!text) throw new VibeError(502, 'EMPTY_COMPLETION', 'Model returned no content', 'server');
      return { content: text, tokens: Number(j.usage?.input_tokens ?? 0) + Number(j.usage?.output_tokens ?? 0), model: String(j.model ?? cfg.model), provider: 'anthropic' };
    }
    if (cfg.provider === 'google') {
      const j = await httpJson(f, `${base}/models/${encodeURIComponent(cfg.model)}:generateContent`, { 'x-goog-api-key': key },
        { systemInstruction: { parts: [{ text: sys }] }, contents: rest.map((m) => ({ role: m.role === 'assistant' ? 'model' : 'user', parts: [{ text: m.content }] })),
          generationConfig: { temperature: cfg.temperature, maxOutputTokens: maxTokens, ...(o.json ? { responseMimeType: 'application/json' } : {}) } }, key);
      const text = (j.candidates?.[0]?.content?.parts ?? []).map((p: any) => p?.text ?? '').join('');
      if (!text) throw new VibeError(502, 'EMPTY_COMPLETION', 'Model returned no content', 'server');
      return { content: text, tokens: Number(j.usageMetadata?.totalTokenCount ?? 0), model: cfg.model, provider: 'google' };
    }
    // openai, alibaba, moonshot, custom: OpenAI-compatible chat completions
    const j = await httpJson(f, `${base}/chat/completions`, { Authorization: `Bearer ${key}` },
      { model: cfg.model, messages, temperature: cfg.temperature, max_tokens: maxTokens, ...(o.json && cfg.provider === 'openai' ? { response_format: { type: 'json_object' } } : {}) }, key);
    const content = j?.choices?.[0]?.message?.content;
    if (typeof content !== 'string') throw new VibeError(502, 'EMPTY_COMPLETION', 'Model returned no content', 'server');
    return { content, tokens: Number(j.usage?.total_tokens ?? 0), model: String(j.model ?? cfg.model), provider: cfg.provider };
  } catch (e) {
    if (e instanceof VibeError) log.warn('engine call failed', { provider: cfg.provider, code: e.code, kind: e.kind });
    throw e;
  }
}

// ---------- structured output ----------
export function extractJsonObject(text: string): unknown {
  const t = text.trim().replace(/^```(?:json)?\s*/i, '').replace(/\s*```$/i, '');
  try { return JSON.parse(t); } catch { /* locate the outermost object */ }
  const s = t.indexOf('{'); const e = t.lastIndexOf('}');
  if (s >= 0 && e > s) return JSON.parse(t.slice(s, e + 1));
  throw new Error('No JSON object found');
}
export class EngineOutputError extends AppError {
  constructor(detail: string) { super(502, 'engine_bad_output', `Модель вернула ответ в неверном формате: ${detail}`); }
}
/** Calls the engine, parses and validates JSON against `schema`; on failure asks once more with the validation error. */
export async function engineJson<S extends z.ZodTypeAny>(db: Db, deps: EngineDeps, messages: ChatMessage[], schema: S, o: { maxTokens?: number } = {}): Promise<{ data: z.infer<S>; tokens: number; model: string; provider: Provider }> {
  let tokens = 0; let last = ''; let msgs = messages;
  for (let attempt = 0; attempt < 2; attempt++) {
    const r = await engineChat(db, deps, msgs, { json: true, maxTokens: o.maxTokens });
    tokens += r.tokens;
    try {
      const parsed = schema.safeParse(extractJsonObject(r.content));
      if (parsed.success) return { data: parsed.data, tokens, model: r.model, provider: r.provider };
      last = parsed.error.issues.slice(0, 3).map((i) => `${i.path.join('.') || 'root'}: ${i.message}`).join('; ');
    } catch (e) { last = (e as Error).message; }
    msgs = [...messages, { role: 'assistant', content: r.content.slice(0, 4000) }, { role: 'user', content: `Your previous reply was invalid (${last}). Reply again with ONE valid JSON object only, matching the schema exactly. No prose, no code fences.` }];
  }
  throw new EngineOutputError(last.slice(0, 160));
}
