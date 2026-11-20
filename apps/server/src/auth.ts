import { createHash } from 'node:crypto';
import type { FastifyRequest } from 'fastify';
import { config } from './config.ts';
import { AppError, log } from './util.ts';
import type { VibeClient } from './vibe.ts';

export interface Identity { userId: string; name: string; role: 'ADMIN' | 'MEMBER'; isAdmin: boolean; portal: string | null; requestId: string }
const CACHE_TTL_MS = 15 * 60_000;
const cache = new Map<string, { at: number; value: Omit<Identity, 'requestId'> }>();

const hdr = (req: FastifyRequest, name: string): string | undefined => {
  const v = req.headers[name];
  return Array.isArray(v) ? v[0] : v;
};
export function clearIdentityCache(): void { cache.clear(); }

/** Resolves the caller from Gateway headers; identity is verified via GET /v1/me (cached 15 min by session hash). */
export async function resolveIdentity(req: FastifyRequest, vibe: VibeClient): Promise<Identity> {
  const requestId = hdr(req, 'x-vibe-request-id') ?? `req_${Math.random().toString(16).slice(2, 18)}`;
  if (config.devAuthBypass) return { userId: 'dev-user', name: 'Dev User', role: 'ADMIN', isAdmin: true, portal: 'dev.local', requestId };
  const bearer = hdr(req, 'x-vibe-authorization')?.replace(/^Bearer\s+/i, '');
  const headerUser = hdr(req, 'x-vibe-user-id');
  if (!bearer && !headerUser) throw new AppError(401, 'authorization_required', 'Откройте приложение из меню Bitrix24.');
  const role: 'ADMIN' | 'MEMBER' = hdr(req, 'x-vibe-user-role') === 'ADMIN' ? 'ADMIN' : 'MEMBER';
  let name = '';
  try { name = decodeURIComponent(hdr(req, 'x-vibe-user-name-encoded') ?? ''); } catch { name = ''; }
  if (bearer) {
    const key = createHash('sha256').update(bearer).digest('hex');
    const hit = cache.get(key);
    if (hit && Date.now() - hit.at < CACHE_TTL_MS) return { ...hit.value, requestId };
    if (config.appKey) {
      try {
        const me = await vibe.me(bearer);
        const bitrixId = me?.currentUser?.bitrixUserId;
        if (bitrixId) {
          const value = { userId: String(bitrixId), name, role, isAdmin: role === 'ADMIN' || me?.currentUser?.isAdmin === true, portal: me?.portal ?? null };
          cache.set(key, { at: Date.now(), value });
          return { ...value, requestId };
        }
      } catch (e) {
        log.warn('identity resolve via /v1/me failed', { requestId, err: (e as Error).message });
        const status = (e as { status?: number }).status;
        if (status === 401) throw new AppError(401, 'authorization_required', 'Сессия истекла. Откройте приложение из меню Bitrix24 заново.');
      }
    }
  }
  if (!headerUser) throw new AppError(401, 'authorization_required', 'Откройте приложение из меню Bitrix24.');
  return { userId: headerUser, name, role, isAdmin: role === 'ADMIN', portal: hdr(req, 'x-vibe-portal-id') ?? null, requestId };
}

// ---------- in-memory sliding-window rate limiter ----------
const windows = new Map<string, number[]>();
export function rateLimit(key: string, max: number, windowMs: number, now = Date.now()): { ok: boolean; retryAfter: number } {
  const arr = (windows.get(key) ?? []).filter((t) => now - t < windowMs);
  if (arr.length >= max) { windows.set(key, arr); return { ok: false, retryAfter: Math.max(1, Math.ceil((windowMs - (now - arr[0]!)) / 1000)) }; }
  arr.push(now); windows.set(key, arr);
  return { ok: true, retryAfter: 0 };
}
export function resetRateLimits(): void { windows.clear(); }
