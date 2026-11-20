import { randomUUID, randomInt } from 'node:crypto';

export const uid = (): string => randomUUID();
export const nowIso = (): string => new Date().toISOString();
export const sleep = (ms: number): Promise<void> => new Promise((r) => setTimeout(r, ms));
export const DAY_MS = 86_400_000;
export const HOUR_MS = 3_600_000;
export const jsonParse = <T>(s: string | null | undefined, fallback: T): T => {
  if (s == null || s === '') return fallback;
  try { return JSON.parse(s) as T; } catch { return fallback; }
};
export function randBetween(min: number, max: number): number { return randomInt(min, max + 1); }

export function createLogger(base: Record<string, unknown> = {}) {
  const write = (level: string, msg: string, extra?: Record<string, unknown>) => {
    const line = JSON.stringify({ t: nowIso(), level, msg, ...base, ...extra });
    // eslint-disable-next-line no-console
    (level === 'error' ? console.error : console.log)(line);
  };
  return {
    info: (m: string, e?: Record<string, unknown>) => write('info', m, e),
    warn: (m: string, e?: Record<string, unknown>) => write('warn', m, e),
    error: (m: string, e?: Record<string, unknown>) => write('error', m, e),
  };
}
export const log = createLogger();

export class AppError extends Error {
  constructor(public status: number, public code: string, message: string, public retryAfter?: number) {
    super(message);
  }
}
