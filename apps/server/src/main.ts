import { config } from './config.ts';
import { openDb } from './db.ts';
import { seedAll } from './skills.ts';
import { getVibe } from './vibe.ts';
import { buildApp } from './routes.ts';
import { ensureSchedulerJob, pendingRuns, processJobRun } from './jobs.ts';
import { resumeUnfinished } from './refresh.ts';
import { log, HOUR_MS } from './util.ts';

async function main() {
  const db = openDb();
  let ready = false;
  const vibe = getVibe();
  const app = await buildApp({ db, vibe, ready: () => ready });
  await app.listen({ port: config.port, host: config.host });
  log.info('listening', { port: config.port, dataDir: config.dataDir, fts: db.fts });
  // /healthz is served before seeding finishes; /api/* answers 503 + Retry-After until ready.
  setImmediate(async () => {
    try {
      seedAll(db);
      ready = true;
      const deps = { db, vibe };
      await ensureSchedulerJob(db, vibe).then((s) => log.info('scheduler', { ...s }));
      for (const runId of pendingRuns(db)) await processJobRun(deps, { runId });
      await resumeUnfinished(deps);
    } catch (e) {
      log.error('startup tasks failed', { err: String((e as Error).message) });
      if (!ready) process.exitCode = 1;
      if (!ready) await app.close();
    }
  });
  const daily = setInterval(() => { void ensureSchedulerJob(db, vibe).catch(() => {}); }, 24 * HOUR_MS);
  daily.unref();
  const shutdown = () => { void app.close().then(() => process.exit(0)); };
  process.on('SIGTERM', shutdown); process.on('SIGINT', shutdown);
}
main().catch((e) => { console.error(e); process.exit(1); });
