# Operations runbook

All platform calls below use JSON mode (never `?stream=true`) and the service key in `X-Api-Key`. Values in `<...>` are yours. Secrets are never printed, committed or baked into the archive.

## Deploy / redeploy
```
VIBE_API_KEY=... VIBE_SERVER_ID=... VIBE_APP_KEY=... APP_PUBLIC_URL=https://... node scripts/deploy.mjs --bind-placement
node scripts/deploy.mjs --dry-run --skip-build      # show the request without sending it
```
Env is injected at start, not baked into the image. `EXEC_BUSY`, `WAKE_TIMEOUT` and `GALAXY_UPLOAD_BUSY` are retried by the script using `Retry-After`; the server is never re-created. The archive contract and the placement body are marked UNVERIFIED in the script: confirm them against `/docs/infra/deploy` and `/docs/apps/placements/bind` before the first run.

## Verify after deploy
Run on the server (exec) or against a reachable instance:
```
node scripts/smoke.mjs --base http://127.0.0.1:$PORT --generate --jobs
```
Checks: healthz, static files, 5 skills, 8 seed templates, agent status, one real free generation, job presence.

## Rotate the job signing secret
1. Rotate through the platform (the rotate-secret endpoint is described in `/docs/infra/jobs`). The new secret is shown once.
2. Put the old value into `JOB_SECRET_PREVIOUS` and the new one into `JOB_SECRET`, then redeploy (or only replace the file `job_secret` on the data volume). Both are accepted, so there is no gap.
3. After the first successful signed delivery, remove `JOB_SECRET_PREVIOUS` at the next redeploy.
If a job was created by the app itself, the secret is also stored in `<DATA_DIR>/job_secret` (mode 0600); the Settings screen shows whether a secret is configured.

## Roll back a skill version
- UI: Skills -> open a skill -> Versions -> "Откатиться" (admin only). A report with verdict `rolled_back` is written.
- API: `POST /api/skills/:id/rollback {"version_id":"..."}` (admin). Versions are immutable; rollback only switches `current_version_id`.
- Automatic: two hard failures among the first three generations after an agent update switch the skill back to the previous version and mark it `failed` until the next scheduled check.

## Manual refresh
UI "Проверить сейчас" on a skill, or `POST /api/skills/:id/refresh` (admin; per-skill cooldown 6 h; shares the global mutex). "Проверить все сейчас" in Settings makes every skill due; the dispatcher still processes at most one skill per delivery (hard cap 2).

## Fallback (lazy) scheduler
If the platform refuses jobs (`WAKE_SCHEDULE_GALAXY_DISABLED`, `FEATURE_DISABLED`) or `VIBE_SERVER_ID` is missing, `scheduler_mode` becomes `lazy`: any authenticated API call, at most once per hour, starts the due skills that are overdue by more than 24 h, under the same mutex and budgets. Settings shows "Fallback: проверка при использовании". The app re-checks the platform job at start and every 24 h and switches back to `job` automatically.

## Agent paused by quota
HTTP 402 / `ai_quota_exhausted` / `insufficient_balance` sets `agent_paused_reason`. A probe call is attempted at most once per day and clears the pause when it succeeds. Admins can also press "Возобновить" in Settings.

## Stuck run or lock
Runs checkpoint to `refresh_runs`; after a restart the app resumes unfinished runs. The global mutex expires after 60 minutes. To inspect: `sqlite3 <DATA_DIR>/promptolog.db "select id,skill_id,status,step from refresh_runs order by started_at desc limit 10"`.

## Backups
The only state is `<DATA_DIR>/promptolog.db` (+ `-wal`/`-shm`) and `job_secret`. Copy them while the app is idle, or use `sqlite3 .backup`.
