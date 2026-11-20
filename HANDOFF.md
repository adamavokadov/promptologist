# HANDOFF (for the next AI agent)

Dense reference. Paths are repo-relative. Language policy: code, comments, commits, docs in English; app UI (`apps/web/src/strings.ru.ts`), card explanations and chat reports to the owner in Russian.

## 1. Mission and context
Product: Promptolog, a web app inside Bitrix24 on the Alaio Vibecode platform. Raw idea -> structured prompt per target AI system (claude|chatgpt|kimi|qwen|grok), output language ru|en. Per-system **skills** (versioned Markdown+frontmatter) are the only source of structure/style rules for the transformer model. An **agent** refreshes each skill every 10-15 days (random per skill) from whitelisted official sources, validates the draft, regression-tests it against the old version, applies it with a 3-generation canary and auto-rollback.
Status: v1.0.0 built and tested **without platform access**. Not deployed by the author. See section 10 for unverified platform contracts.

## 2. Architecture map
```
Bitrix24 iframe -> Vibecode Gateway (adds X-Vibe-* identity headers) -> Fastify app (this repo)
                                                       |-- SQLite (node:sqlite) in DATA_DIR
                                                       |-- Vibecode API (service key): /chat/completions, /search, /research (SSE), /models, /ai/usage, /infra/.../jobs, /me
Platform scheduler --signed POST /internal/jobs/dispatcher--> app (daily; dispatcher picks due skills)
```
Single process. Background work runs in-process after a fast 200. Keep-alive self-ping (`GET {APP_PUBLIC_URL}/healthz` every 4 min) during agent runs.

## 3. Annotated file tree
```
package.json, package-lock.json     runtime deps: fastify, @fastify/static, zod, diff. Everything else is devDependency (bundled by Vite).
tsconfig.base.json                  strict TS; allowImportingTsExtensions (imports use .ts)
vitest.config.ts                    tests/**/*.test.ts
shared/src/index.ts                 constants (SYSTEM_IDS, LIMITS, REQUIRED_SKILL_SECTIONS, PROTECTED_INVARIANTS, GOLDEN_SET), zod schemas, DTO types, template-variable helpers, language heuristic
apps/server/src/
  main.ts                           bootstrap: listen first, then seed + scheduler job check + resume pending job runs/refresh runs (/api/* returns 503+Retry-After until ready)
  config.ts                         env -> config; DATA_DIR autodetect (/data, /opt/app/data, ./data); maskSecrets()
  util.ts                           uid/time/sleep, JSON helpers, structured logger, AppError
  db.ts                             node:sqlite wrapper, migrations via PRAGMA user_version, settings, search index (FTS5 or LIKE), TTL lock
  vibe.ts                           platform client: retry/backoff/Retry-After, BOTH error envelopes, chat/search/research(SSE)/me/models/usage/jobs/notify
  auth.ts                           Gateway identity (X-Vibe-*), /v1/me resolution cached 15 min by sha256(session), rate limiter
  skills.ts                         seeding, version/DTO helpers, checklist parser/runner, skill-draft validator
  seed/skills.ts, seed/templates.ts 5 seed skills (English bodies), 8 seed templates (Russian/English)
  generation.ts                     stages A-D, transformOne (+repair), regeneration, canary accounting + auto-rollback, retention
  refresh.ts                        agent pipeline, budgets, golden tests, dispatch/manual/resume orchestration, keep-alive
  scheduler.ts                      next-check/retry computation, due selection, mutex constants
  jobs.ts                           signature verification, runId dedupe outbox, job registration (+lazy fallback), lazy trigger
  routes.ts                         all HTTP routes, SSE, security headers, static SPA
apps/web/src/                       main.tsx, App.tsx (shell, nav, theme, wake overlay, iframe resize), api.ts (fetch + SSE + polling fallback), ui.tsx (primitives), context.tsx, strings.ru.ts, index.css (design system), screens/*, components/{ResultCard,TemplateSaveModal}
scripts/deploy.mjs smoke.mjs pack-source.mjs
tests/core.test.ts pipeline.test.ts helpers.ts
```

## 4. Data model (SQLite, migration v1 in `db.ts`)
`skills(id PK slug, display_name, current_version_id, model_lineup JSON, sources JSON, last_check_at, next_check_at, status fresh|due|running|failed|paused, consecutive_failures, canary_remaining, canary_failures, paused, ...)`; `skill_versions(id, skill_id, version, frontmatter JSON, body_md, changelog JSON, sources JSON, origin seed|agent|rollback, golden_result JSON, created_at; UNIQUE(skill_id,version))` immutable; `generations(id, user_id, raw_input, language, options JSON, systems JSON, intent JSON, questions JSON, status draft_questions|running|ok|partial|failed, tokens_used, latency_ms, deleted_at)`; `generation_results(id, generation_id, skill_id, skill_version_id, prompt_text, improvements JSON, assumptions JSON, usage_notes, status ok|failed, error, is_favorite, favorited_at, variant_of, ...)`; `templates(id, user_id NULL for seed, title, description, body, language, default_systems, tags, is_seed, usage_count, deleted_at)`; `refresh_runs(id, skill_id, trigger schedule|manual|lazy, job_run_id, status pending|running|done|failed|rejected|no_changes|rolled_back, step, payload JSON, budget_used JSON, error)`; `reports(id, run_id, skill_id, verdict, summary_ru, changelog, sources, golden, budget, version_from, version_to)`; `settings(key,value JSON)`; `job_dedupe(run_id PK, received_at, response_status, processed_at)`; `app_lock(name PK, holder, expires_at)`; `search_docs(ref_type, ref_id, user_id, body)` + FTS5 table `search_fts` when available.
Deviation from the brief: `skills.paused` is a column (boolean) instead of a status-only flag; `generations.systems`/`questions` columns added; `job_dedupe.processed_at` makes acceptance durable (outbox) so a restart finishes accepted-but-unprocessed runs.

## 5. Internal HTTP API (JSON; errors `{error:{code,message}}`)
Auth: all `/api/*` need Gateway headers (401 `authorization_required` otherwise). Admin = `X-Vibe-User-Role: ADMIN` or `/v1/me` `currentUser.isAdmin`.
| Route | Notes |
|---|---|
| `GET /healthz` | no auth |
| `GET /api/me` | `{user_id,name,role,is_admin}` |
| `POST /api/generate` | body `generateRequestSchema`; SSE events `start, intent, card_start, card_done, card_error, questions, done`; response header `X-Generation-Id`; 6/min/user |
| `POST /api/generate/:id/answer` | `{answers:string[]}`; SSE continuation of a `draft_questions` run |
| `GET /api/generations?page&q&system&language&favorites&from&to` | 20 per page |
| `GET/DELETE /api/generations/:id` | DELETE = soft delete |
| `POST /api/generations/:id/results/:resultId/regenerate` | `{feedback?}` -> new `ResultDTO` (variant_of set) |
| `PATCH /api/results/:id/favorite` | `{value}` |
| `GET /api/favorites?q&system&page` | per prompt, not per run |
| `POST /api/history/clear` | removes non-favourite generations |
| `GET/POST /api/templates`, `GET/PATCH/DELETE /api/templates/:id`, `POST .../:id/duplicate`, `POST .../:id/use`, `POST /api/templates/generalize` | seed templates are read-only (403) |
| `GET /api/skills`, `GET /api/skills/:id`, `GET .../versions`, `GET .../versions/:a/diff/:b` | a,b are version numbers |
| `POST /api/skills/:id/rollback {version_id}`, `POST .../refresh`, `PATCH /api/skills/:id {paused}`, `POST /api/skills/refresh-all` | admin only; refresh -> 202 `{run_id}`, 409 on cooldown/busy |
| `GET /api/agent/status` | mode, pause reason, next check, secret presence |
| `GET /api/reports?page&skill&verdict`, `GET /api/reports/:id` | |
| `GET/PUT /api/settings` (PUT admin, whitelist; `scheduler_mode` not writable), `POST /api/settings/resume-agent` | |
| `GET /api/models`, `GET /api/usage` | proxies of `/v1/models`, `/v1/ai/usage?days=30` |
| `POST /api/export`, `POST /api/import/templates` | |
| `POST /internal/jobs/dispatcher` | signature + dedupe; no session |
Rate limits: general 120/min/user; generate and regenerate share 6/min/user; manual refresh 1 per 6 h per skill. 429 carries `Retry-After`.

## 6. Platform integration points
Base `https://vibecode.bitrix24.com/v1`, header `X-Api-Key` (service key). Used endpoints: `POST /chat/completions` (OpenAI-compatible; `response_format:{type:"json_object"}`), `POST /search` (Tavily-like: `query, search_depth, max_results, include_domains, time_range`), `POST /research` (SSE only), `GET /models`, `GET /ai/usage`, `GET /me` (with `X-Api-Key: <vibe_app_...>` + `Authorization: Bearer <X-Vibe-Authorization session>` for identity), `GET|POST /infra/servers/:id/jobs`, `POST /notifications` (best effort).
Gateway request headers consumed: `X-Vibe-User-Id`, `X-Vibe-User-Role`, `X-Vibe-Authorization`, `X-Vibe-User-Name-Encoded`, `X-Vibe-Portal-Id`, `X-Vibe-Request-Id` (echoed back).
**Both error envelopes** are parsed (`vibe.ts: parseErrorEnvelope`): raw OpenAI `{error:{message,type,code}}` and V1 `{success:false,error:{code,message}}`. Kinds: `quota` (402, `ai_quota_exhausted`, `insufficient_balance`), `rate_limit` (429, `rate_limit_exceeded`), `congested` (`ai_congested`, `ai_provider_cooldown`), `auth`, `invalid`, `server`, `network`, `timeout`. Retried (3x, exp backoff + jitter, `Retry-After` honoured, capped 60 s): rate_limit, congested, server, network, timeout. Timeouts: LLM 120 s, analyzer 180 s, search 60 s, research 300 s.
**Job signature** (docs `/docs/infra/jobs/signature`, implemented in `jobs.ts: verifyJobRequest`): caller header `X-Vibe-Caller-Kind` must be `schedule`; single `Vibe-Signature: t=<unix>,v1=<64 hex>` (duplicate physical headers rejected via `rawHeaders`); HMAC-SHA256 over `"<t>.<raw body bytes>"` keyed with the UTF-8 secret (`vjs_...`); |now - t| <= 300 s; constant-time compare. The raw body is captured by the JSON content-type parser. Verified with the platform's published reference vector in `tests/core.test.ts`.
Job payload: `{type:"scheduled_job.run", jobId, runId, scheduledFor, attempt 1..4, late, trigger}`. 2xx means "accepted", not "done": the app inserts `runId` into `job_dedupe`, returns `200 {ok:true}` immediately, then works in the background. Duplicate delivery -> 200 without work.
Docs: https://vibecode.bitrix24.com/docs/infra/app-runtime, /docs/infra/jobs, /docs/infra/jobs/signature, /docs/errors, /llms.txt.

## 7. Generation pipeline (`generation.ts`)
A: intent JSON (temp 0.2). In `questions` mode with critical `missing_info` the run stops as `draft_questions` (<=3 questions). B: per system, concurrency 2, temp 0.4, max_tokens 4000, JSON mode; system message = Russian meta-prompt + skill body; user message = `<intent>`, `<raw_request>`, `<options>`, optional `<refinement>`. C: zod schema (`improvements 3..7`, `assumptions 0..6`) + `runChecklist` (length, language heuristic, explicit language directive, no meta-prompt leakage, skill `has:`/`has-any:` markers); one repair call; second failure -> failed card (counts as a hard failure for the canary). D: persist, index for search, retention (default 500 non-favourite generations/user; generations containing favourites are exempt).
Skill checklist markers: a line in `## Validation Checklist` may contain `` `has:<literal>` `` or `` `has-any:a|b` `` (case-insensitive substring checks). Keep them when editing skills.

## 8. Refresh agent internals (`refresh.ts`, `scheduler.ts`, `jobs.ts`)
- Schedule: `next_check_at = now + randomInt(10..15) days + randomInt(0..240) min`. After failure: +24..48 h; after 3 consecutive failures: a full interval and status `failed`. Single platform job `promptolog-dispatcher`, cron `<rand 0-59> 4 * * *` in `settings.scheduler_timezone` (default Europe/Moscow), created by the app if missing.
- Dispatch: master switch -> quota-pause probe (<= 1/day) -> in-process flag + SQLite TTL mutex (60 min, holder `promptolog-app`) -> due skills (shuffled) -> max 1 per delivery (hard cap 2, 10 min pause between) -> `executeRun`.
- Steps (checkpointed in `refresh_runs.step/payload`, resumable): plan (4-6 queries incl. past changelog hints) -> search (<=6 sequential calls, 2-5 s pauses, domain whitelist, window since `last_check_at` capped 30 d, rank official > announce > other) -> deep (<=1 research call if >= 2 change signals) -> analyze (analyzer model, temp 0.2, JSON) -> validate (zod, required sections, protected invariants verbatim, checklist 5-10 items, size <= 14000, changelog sources whitelisted; non-whitelisted items dropped, none left -> `rejected`) -> golden (3 tasks x old/new transform + pairwise judge with randomised A/B; new must never lose; tie OK) -> apply (new immutable version, switch, canary 3, reschedule) -> report + best-effort notification.
- Budget per run: search <= 6, research <= 1, LLM calls <= 12, tokens <= 150K (counted in a wrapper; exceeding -> `budget_error`, retry per schedule). A normal updating run uses 1 + 6 + 3 = 10 LLM calls.
- Canary: next 3 generations on the new version are counted; >= 2 hard failures -> automatic switch back to the previous version (no new row), status `failed`, report `rolled_back`.
- Whitelists: claude `platform.claude.com, anthropic.com`; chatgpt `developers.openai.com, openai.com, cookbook.openai.com`; kimi `platform.kimi.ai, moonshot.ai, kimi.com`; qwen `qwen.readthedocs.io, qwen.ai, alibabacloud.com`; grok `docs.x.ai, x.ai`.
- Untrusted data: raw input and web content are always wrapped in tags; analyzer must paraphrase; protected invariants are checked by string match and forced back into the frontmatter.
- Fallback: `scheduler_mode=lazy` (no job entitlement / no server id): `maybeLazyCheck` on authenticated requests at most hourly, overdue > 24 h.

## 9. Secrets handling (names only)
`VIBE_API_KEY`, `VIBE_APP_KEY`, `JOB_SECRET`, `JOB_SECRET_PREVIOUS` come from deploy env. If the app creates the job itself, the returned secret is stored in `<DATA_DIR>/job_secret` (0600). Keys never go to the browser, logs (masked by `maskSecrets`), the archive or the DB. `.env` is git-ignored and excluded from the archive.

## 10. Known limitations, degradations and OPEN RISKS (verify first on the real platform)
1. **Deploy archive contract** (`scripts/deploy.mjs`): how to pass an archive to `POST /infra/servers/:id/deploy` is not confirmed (script sends `source.archive` base64; `--source-url` form follows the documented URL source). Confirm at `/docs/infra/deploy`.
2. **Placement bind** body for `POST /v1/placements/bind` and the icon upload endpoint: not verified; icon upload is not implemented. Auto-height uses `postMessage({type:'vibe:resize', height})` per the brief; confirm the exact contract in the placements docs.
3. **Job creation response**: the secret field name is assumed (`secret`/`signingSecret`/`job.secret`, prefix `vjs_`). If absent, the app logs a warning; rotate the secret and set `JOB_SECRET`.
4. **`GET /v1/me` shape**: identity uses `currentUser.bitrixUserId`, `currentUser.isAdmin`, `portal`; falls back to `X-Vibe-User-Id`/role headers when unavailable. Confirm field names.
5. **Response envelopes** of `/search`, `/models`, `/ai/usage`, `/research` frames (`delta/content/answer`) and `POST /notifications` are handled defensively but were not observed live.
6. **Skill seeds** come from the brief digest (dated 2026-11-13); build-time enrichment from the live vendor pages was not possible. The first agent run will reconcile them.
7. Node: built and tested on Node 22.23 (`node:sqlite` emits an ExperimentalWarning). The platform runtime should be `node24`.
8. In-memory state: rate limits, identity cache and the lazy timer reset on restart (acceptable for a single instance).
9. Deleting a generation hides its favourites too (soft delete is a deliberate full removal from all views).
10. Agent notifications are skipped silently without the required scope.

## 11. Runbook pointers
Build/deploy/rollback/rotate/manual refresh/fallback: see OPERATIONS.md. Smoke: `node scripts/smoke.mjs --base http://127.0.0.1:$PORT --generate --jobs`.

## 12. Decisions log
1. One root `package.json` (no workspaces); `shared/` imported by relative path; one `npm run build`.
2. Server bundled with esbuild into `dist/server.js` (`--packages=external`); `tsc` is used for type checking only. Reason: shared code outside `apps/server` and a single start file.
3. Frontend-only libraries are devDependencies so the platform install step (`npm ci --omit=dev`) stays small.
4. Tailwind 3 (stable PostCSS pipeline) with a hand-written design system in `index.css`; `@fontsource` packages provide self-hosted woff2 (Cyrillic included).
5. zod 4 and TypeScript 7 (versions resolved at install time; lockfile pins them).
6. SSE over `fetch` (POST) instead of `EventSource`; the generation id is sent in `X-Generation-Id` so the 5 s no-event watchdog can switch to polling `GET /api/generations/:id`.
7. FTS5 virtual table is maintained manually in `search_docs`/`search_fts`; automatic LIKE fallback.
8. Durable job acceptance (outbox) instead of fire-and-forget.
9. Skill bodies are English (model instructions); explanations produced for users are Russian.
10. Golden "old failed to produce output" counts as a win for the new skill; "new failed" counts as a loss.
11. Settings are admin-only to change; theme is also stored per browser (localStorage, try/catch for blocked storage).
12. `GET /api/settings` is readable by all users; `scheduler_mode` is system-managed.
13. Manual rollback inserts no version row; only the pointer moves and a `rolled_back` report is written.
14. Retention exempts any generation that contains a favourite.

## 13. Conventions
English identifiers and comments; Russian only in `strings.ru.ts`, seed templates and Russian meta-prompts. No UI strings outside `strings.ru.ts`. SQL only via prepared statements. zod validates every input. Commit style: imperative, phase-scoped (`phase 4: ...`). No stubs in working scenarios.

## 14. Verification commands
```
npm ci && npm run build && npm test
DEV_AUTH_BYPASS=1 DATA_DIR=$(mktemp -d) PORT=3111 node dist/server.js &   # then:
node scripts/smoke.mjs --base http://127.0.0.1:3111
```
