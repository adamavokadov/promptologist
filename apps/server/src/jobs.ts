import { createHmac, timingSafeEqual } from 'node:crypto';
import type { IncomingMessage } from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { jobPayloadSchema, type JobPayload } from '../../../shared/src/index.ts';
import { config } from './config.ts';
import { type Db, getSettings, setSettings } from './db.ts';
import { VibeError, type VibeClient } from './vibe.ts';
import { dispatchDue, type RefreshDeps } from './refresh.ts';
import { nowIso, log, randBetween } from './util.ts';

export const JOB_LABEL = 'promptolog-dispatcher';
export const JOB_PATH = '/internal/jobs/dispatcher';

// ---- signature verification (scheme from /docs/infra/jobs/signature) ----
export function verifyJobRequest(x: { callerKind: unknown; singleSignatureHeader: unknown; rawBody: Buffer; secret: string; nowSeconds: number }): boolean {
  if (x.callerKind !== 'schedule' || typeof x.singleSignatureHeader !== 'string' || !x.secret) return false;
  const m = /^t=(0|[1-9][0-9]{0,15}),v1=([0-9a-f]{64})$/.exec(x.singleSignatureHeader);
  if (!m || m[0] !== x.singleSignatureHeader) return false;
  const t = Number(m[1]);
  if (!Number.isSafeInteger(t) || !Number.isFinite(x.nowSeconds) || Math.abs(x.nowSeconds - t) > 300) return false;
  const actual = Buffer.from(m[2]!, 'hex');
  const expected = createHmac('sha256', Buffer.from(x.secret, 'utf8')).update(m[1]!, 'ascii').update('.', 'ascii').update(x.rawBody).digest();
  return actual.length === expected.length && timingSafeEqual(actual, expected);
}
export function singleHeader(req: Pick<IncomingMessage, 'rawHeaders'>, name: string): string | undefined {
  const values: string[] = [];
  for (let i = 0; i < req.rawHeaders.length; i += 2) if (req.rawHeaders[i]!.toLowerCase() === name.toLowerCase()) values.push(req.rawHeaders[i + 1]!);
  return values.length === 1 ? values[0] : undefined;
}

// ---- secret storage: env first, then a file on the persistent volume ----
const secretFile = () => path.join(config.dataDir, 'job_secret');
export function getJobSecrets(): string[] {
  const out: string[] = [];
  let current = config.jobSecret;
  if (!current) { try { current = fs.readFileSync(secretFile(), 'utf8').trim(); } catch { current = ''; } }
  if (current) out.push(current);
  if (config.jobSecretPrevious) out.push(config.jobSecretPrevious);
  return out;
}
export function verifyWithAnySecret(args: Omit<Parameters<typeof verifyJobRequest>[0], 'secret'>): boolean {
  return getJobSecrets().some((secret) => verifyJobRequest({ ...args, secret }));
}
export function storeJobSecret(secret: string): void {
  fs.mkdirSync(config.dataDir, { recursive: true });
  fs.writeFileSync(secretFile(), secret, { mode: 0o600 });
}

// ---- durable acceptance (dedupe by runId) ----
export function acceptRun(db: Db, runId: string): { duplicate: boolean } {
  const r = db.run('INSERT OR IGNORE INTO job_dedupe(run_id, received_at, response_status) VALUES(?,?,202)', runId, nowIso());
  return { duplicate: Number(r.changes) === 0 };
}
export function pendingRuns(db: Db): string[] { return db.all<{ run_id: string }>('SELECT run_id FROM job_dedupe WHERE processed_at IS NULL ORDER BY received_at').map((r) => r.run_id); }
export function markProcessed(db: Db, runId: string): void { db.run('UPDATE job_dedupe SET processed_at = ? WHERE run_id = ?', nowIso(), runId); }

export async function processJobRun(deps: RefreshDeps, payload: Pick<JobPayload, 'runId'>): Promise<string[]> {
  try { return await dispatchDue(deps, { trigger: 'schedule', jobRunId: payload.runId, max: 1 }); }
  finally { markProcessed(deps.db, payload.runId); }
}

// ---- scheduler job lifecycle ----
export interface SchedulerStatus { mode: 'job' | 'lazy'; created: boolean; reason?: string }
const LAZY_CODES = ['WAKE_SCHEDULE_GALAXY_DISABLED', 'FEATURE_DISABLED'];
export async function ensureSchedulerJob(db: Db, vibe: VibeClient, rand = randBetween): Promise<SchedulerStatus> {
  if (!config.serverId || !config.apiKey) { setSettings(db, { scheduler_mode: 'lazy' }); return { mode: 'lazy', created: false, reason: 'VIBE_SERVER_ID or VIBE_API_KEY is not configured' }; }
  try {
    const jobs = await vibe.listJobs(config.serverId);
    if (jobs.some((j: any) => j.label === JOB_LABEL && j.enabled !== false)) { setSettings(db, { scheduler_mode: 'job' }); return { mode: 'job', created: false }; }
    const tz = getSettings(db).scheduler_timezone;
    const created = await vibe.createJob(config.serverId, { label: JOB_LABEL, cronExpr: `${rand(0, 59)} 4 * * *`, timezone: tz, path: JOB_PATH, enabled: true });
    const secret = created?.secret ?? created?.signingSecret ?? created?.job?.secret;
    if (typeof secret === 'string' && secret.startsWith('vjs_')) {
      storeJobSecret(secret);
      log.warn('Job secret created and stored on the data volume. Also set JOB_SECRET in the app environment (see OPERATIONS.md).');
    } else log.warn('Job created but the response carried no secret; rotate the secret and store it (see OPERATIONS.md).');
    setSettings(db, { scheduler_mode: 'job' });
    return { mode: 'job', created: true };
  } catch (e) {
    const code = e instanceof VibeError ? e.code : '';
    if (LAZY_CODES.includes(code) || (e instanceof VibeError && (e.kind === 'auth' || e.kind === 'invalid'))) {
      setSettings(db, { scheduler_mode: 'lazy' });
      return { mode: 'lazy', created: false, reason: code || (e as Error).message };
    }
    log.warn('scheduler job check failed (network?), keeping current mode', { err: (e as Error).message });
    return { mode: getSettings(db).scheduler_mode, created: false, reason: 'check failed' };
  }
}

export function parseJobPayload(raw: Buffer): JobPayload | null {
  try { const r = jobPayloadSchema.safeParse(JSON.parse(raw.toString('utf8'))); return r.success ? r.data : null; } catch { return null; }
}

// ---- lazy fallback: opportunistic check at most once per hour ----
let lastLazy = 0;
export function maybeLazyCheck(deps: RefreshDeps, now = Date.now()): boolean {
  const s = getSettings(deps.db);
  if (s.scheduler_mode !== 'lazy' || !s.auto_refresh_enabled || now - lastLazy < 3_600_000) return false;
  lastLazy = now;
  void dispatchDue(deps, { trigger: 'lazy', max: 1, overdueMs: 24 * 3_600_000 }).catch((e) => log.warn('lazy refresh failed', { err: (e as Error).message }));
  return true;
}
export function resetLazyForTests(): void { lastLazy = 0; }
