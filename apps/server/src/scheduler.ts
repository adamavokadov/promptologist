import { DAY_MS, HOUR_MS, randBetween } from './util.ts';
import { type Db, type Row, acquireLock, releaseLock } from './db.ts';

type Rand = (min: number, max: number) => number;
/** next_check_at = now + randomInt(10..15) days + jitter(0..4h). */
export function computeNextCheck(now: Date, rand: Rand = randBetween): Date {
  return new Date(now.getTime() + rand(10, 15) * DAY_MS + rand(0, 240) * 60_000);
}
/** After a failure: retry in randomInt(24..48) hours; after 3 consecutive failures wait a full interval. */
export function computeRetry(now: Date, consecutiveFailures: number, rand: Rand = randBetween): Date {
  if (consecutiveFailures >= 3) return computeNextCheck(now, rand);
  return new Date(now.getTime() + rand(24, 48) * HOUR_MS);
}
export const MUTEX_NAME = 'refresh';
export const MUTEX_TTL_MS = 60 * 60_000;
export const MIN_PAUSE_BETWEEN_RUNS_MS = 10 * 60_000;
export const HARD_CAP_PER_DISPATCH = 2;
export const LAZY_CHECK_INTERVAL_MS = 3_600_000;
export const LAZY_OVERDUE_MS = 24 * HOUR_MS;

export function dueSkills(db: Db, now = Date.now(), overdueMs = 0): Row[] {
  const rows = db.all("SELECT * FROM skills WHERE paused = 0 AND status != 'running' AND next_check_at IS NOT NULL").filter((r) => Date.parse(r.next_check_at) + overdueMs <= now);
  for (let i = rows.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [rows[i], rows[j]] = [rows[j]!, rows[i]!]; }
  return rows;
}
export { acquireLock, releaseLock };
