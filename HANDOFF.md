# HANDOFF (for the next AI agent)

_Last scripted update: 2026-11-22. Release history: CHANGELOG.md._

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
  seed/skills.ts, seed/templates.ts 5 seed skills (English bodies), 9 seed templates (Russian/English/Spanish body)
  generation.ts                     stages A-D, transformOne (+repair), regeneration, canary accounting + auto-rollback, retention
  refresh.ts                        agent pipeline, budgets, golden tests, dispatch/manual/resume orchestration, keep-alive
  scheduler.ts                      next-check/retry computation, due selection, mutex constants
  jobs.ts                           signature verification, runId dedupe outbox, job registration (+lazy fallback), lazy trigger
  routes.ts                         all HTTP routes, SSE, security headers, static SPA
apps/web/src/                       main.tsx, App.tsx (shell, nav, theme, wake overlay, iframe resize), api.ts (fetch + SSE + polling fallback), ui.tsx (primitives), context.tsx, strings.ru.ts, index.css (design system), screens/*, components/{ResultCard,TemplateSaveModal}
scripts/deploy.mjs smoke.mjs pack-source.mjs docs_update.py   (docs_update.py = scripted CHANGELOG/HANDOFF maintenance)
tests/core.test.ts pipeline.test.ts helpers.ts
patches/                            applied patch scripts (see section 16)
design.md                           canonical UI spec: «Ноябрь» brief v1.0 + Addendum A (mapping, contrast overrides, decisions D1-D5)
agents.md, CLAUDE.md                operating manual for AI agents; CLAUDE.md imports agents.md for Claude Code
docs/claude-project-instructions.md text pasted into the Claude Project custom instructions
.github/workflows/ci.yml, .devcontainer/devcontainer.json, .editorconfig, .gitattributes, .nvmrc, repomix.config.json   repo hygiene
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
11. Template `language` supports only ru|en: the Spanish agent-graph template is flagged EN, so sending it to the generator selects English output. Spanish output is not a supported language.
12. Repomix excludes `package-lock.json` by default, so repomix packs do not show the lockfile; it must stay committed (`npm ci` needs it).
13. Floating composer vs the Bitrix24 iframe auto-height (`vibe:resize`): `position: fixed` and `100vh` anchor to the full-height frame, not to the visible window, so the Brief's fixed composer cannot be built correctly until the placement iframe height behavior is confirmed (design.md A6, conflict C1, decision D4).
14. Optimizer engine contracts (unverified, see `shared/src/optimizer.ts`): model ids other than Anthropic's come from the product spec and are not confirmed against provider docs; default base URLs and request shapes of OpenAI-compatible, Google, Alibaba and Moonshot providers follow public documentation and were tested only with mocked fetch; outbound egress from the Alaio platform to third-party providers is unverified; the platform gateway model list (`GET /models`) is not used for the optimizer catalog.
15. Optimizer scope gaps: reverse engineering takes pasted text or .txt/.md/.csv/.json files up to 200 KB, not images or documents (needs a verified vision contract); token savings are estimates, not provider counts; the Generator and Optimizer do not share history yet.
16. Third-party billing, external provider access, iframe host placement, and scheduler delivery still require a smoke test in the target Bitrix24 environment. The iframe resize message is documented by the platform.

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
15. The Karpathy-inspired agent-graph prompt (Opus 5.5) ships as a seed TEMPLATE, not as skill content: skills are fed only from whitelisted official vendor sources and are rewritten by the refresh agent, so third-party guidance would be lost or rejected. Seed templates are inserted by title at start (`seedAll`), so existing databases receive it automatically.
16. The template body is kept in Spanish verbatim (only the `<prompt>` wrapper of the source note is dropped). Variables are lower-cased (`{{tarea}}`, ...) because `VAR_RE` accepts only `[a-z0-9_]`; `language` is `'en'` because templates support only ru/en.
17. CHANGELOG.md and HANDOFF.md are updated only through `scripts/docs_update.py` (owner's standing rule); patch scripts import the same logic and are archived in `patches/`.
18. Canonical UI is the «Ноябрь» design system (Minimal Editorial Workspace: light canvas, warm neutrals, one terracotta accent, floating composer). It supersedes the v1.0 neo-glassmorphism and is specified in `design.md`: Part I is the owner's brief v1.0 (formatting normalised, wording unchanged), Addendum A maps it onto this codebase and holds the overrides. The redesign is not implemented yet; the code still ships the glassmorphism UI.
19. Brief concepts without a counterpart in this app are not invented: the eight-stage stepper has no real data source (agent run steps are not exposed by any API; generation progress is three transient client states) and the composer has no attachment or voice controls. The `Stepper` is built only if the owner assigns a data source (design.md A5, decision D3).
20. The contrast audit of the Brief tokens against WCAG 2.2 AA produced proposed overrides (design.md A4): secondary and muted text, accent fill with white text, success and warning text, control borders, Grok identity dot. Brief hex values stay in Part I as the reference; implementation uses the overrides once the owner confirms (D5).
21. `agents.md` is the operating manual for AI agents; `CLAUDE.md` imports it for Claude Code; `docs/claude-project-instructions.md` is the text pasted into the Claude Project custom instructions. Keep the three consistent.
22. D1 (2026-11-20): sidebar is expanded at 280px from 1024px up with an explicit collapse toggle to a 64px icon rail; state in localStorage key `sidebar` (try/catch); from 800 to 1023px the rail starts collapsed unless the user chose otherwise; under 800px bottom tabs and the «Ещё» sheet stay; hover expansion removed.
23. D2 (2026-11-20): light is the default theme for users without a stored choice; dark/light/system switcher stays; hand-authored dark map lives in design.md A10 and `apps/web/src/styles/tokens.css`; `DEFAULT_SETTINGS.theme` changed to `light`; a saved user choice always wins.
24. D3 (2026-11-20): the workflow stepper is not built (no real data source); no Stepper component and no fake stages.
25. D4 (2026-11-20): the future Generator composer uses a sticky transparent wrapper at the bottom of the canvas (`position: sticky; bottom: var(--space-6)`, wrapper `pointer-events: none`, composer `pointer-events: auto`), not `position: fixed`; `vibe:resize` keeps working; resolves conflict C1 without a host contract. The composer itself is a later task.
26. D5 (2026-11-20): all contrast overrides from design.md A4 are adopted, including `--color-control-border` for input boundaries, switches and checkboxes; `npm run audit:contrast` guards them.
27. Analytics section (2026-11-20): admin-only nav entry `#/analytics` in the «Система» group; «Новый промпт» is the Generator entry (no duplicate Generator item).
28. Design system (2026-11-21): Obsidian / Linear Dark (shadcn-style semantics on existing Tailwind and CSS) is canonical and recorded in design.md Part 0; the «Ноябрь» visual values are superseded, its structure, accessibility and QA rules stay. Tokens in `apps/web/src/styles/tokens.css`, dark and light hand-authored, guarded by `npm run audit:contrast`.
29. Theme default (2026-11-21): dark is the default theme again (supersedes D2 of 2026-11-20); light and system stay; a stored user choice wins; `DEFAULT_SETTINGS.theme` is `dark`.
30. No shadcn/ui or Radix packages (2026-11-21): the visual language is applied through existing CSS; adopting the packages needs an owner decision (no new dependencies without asking). Lucide icons use stroke width 1.75 via CSS.
31. Contrast overrides of the Obsidian palette (2026-11-21): muted text `#8F8F99` (dark), accent hover `#4B57C0`, new `--color-accent-text` for links, `--color-control-border` for input boundaries; light-theme values are our own (design.md §0.4).
32. Prompt Optimizer Pro (2026-11-22): a standalone «Оптимизатор» screen (`#/optimizer`) and «Библиотека» screen (`#/library`) sit next to the Generator; the Generator, its skills, templates, history and favorites are unchanged. Server code: `engine.ts`, `optimizer.ts`, `optimizer-routes.ts`, shared contracts in `shared/src/optimizer.ts`, migration v2 (`optimizations`, `folders`).
33. Engine settings (2026-11-22): provider (platform gateway by default, anthropic, openai, google, alibaba, moonshot, custom OpenAI-compatible), model, Custom Base URL, temperature, API key. Admin-only writes; the key is AES-256-GCM encrypted with `ENGINE_SECRET` and never returned to the browser; keys cannot be saved without the secret; Custom Base URL must be https and may not point to private or link-local addresses (`ENGINE_ALLOW_PRIVATE=1` only for local proxies).
34. Structured output (2026-11-22): every engine call is fenced (user text inside `<user_input>` as data), parsed from JSON, validated by zod, and re-asked once with the validation error; scores are clamped to 1..10 and are the model's own estimate. The language-bridge sentence is appended server-side, never trusted to the model.
35. Compression (2026-11-22): the compressed prompt is accepted only if it keeps every [Variable] and is shorter by the approximate token estimate (no tokenizer dependency); otherwise the original is kept and the UI says so. Compression keeps the prompt language.
36. Production audit: Node 22.12+ is the declared minimum and the platform target stays Node 24. The dependency lock keeps its existing graph except for the Node typings and their dependency.
37. Custom engine connections use validated public DNS addresses through TLS. Changing the provider or effective URL requires a fresh provider key.

## 13. Conventions
English identifiers and comments; Russian only in `strings.ru.ts`, seed templates and Russian meta-prompts. No UI strings outside `strings.ru.ts`. SQL only via prepared statements. zod validates every input. Commit style: imperative, phase-scoped (`phase 4: ...`). No stubs in working scenarios.

## 14. Verification commands
```
npm ci && npm run build && npm test
DEV_AUTH_BYPASS=1 DATA_DIR=$(mktemp -d) PORT=3111 node dist/server.js &   # then:
node scripts/smoke.mjs --base http://127.0.0.1:3111
```

## 15. Scripted maintenance
CHANGELOG.md and HANDOFF.md are maintained ONLY by `scripts/docs_update.py` (stdlib Python, idempotent). Never edit them by hand.
```
python3 scripts/docs_update.py changelog --added "..." --changed "..." --fixed "..."   # into [Unreleased]
python3 scripts/docs_update.py release X.Y.Z                                           # [Unreleased] -> [X.Y.Z], bumps package.json/lock
python3 scripts/docs_update.py handoff --decision "..." --limitation "..." --patch "id: summary"
python3 scripts/docs_update.py handoff --sub "old text" "new text"                      # exact, idempotent substitution
```
Add `--dry-run` after the subcommand to preview a diff. Patch scripts live in `patches/` and call the same functions.

## 16. Patch log
Applied patch scripts (newest last); sources in `patches/`.
- 2026-11-20 2026-11-20-agent-graph-and-hygiene: agent-graph seed template, 9 seed templates in tests/smoke/docs, repo hygiene files, scripted docs tool
- 2026-11-20 2026-11-20-design-system-docs: design.md (Ноябрь + Addendum A), agents.md, CLAUDE.md, Claude project instructions, docs placeholder cleanup
- 2026-11-21 2026-11-21-noyabr-tokens-shell: «Ноябрь» tokens, flat primitives, collapsible sidebar shell, analytics nav entry (WP0-WP2); decisions D1-D5 resolved
- 2026-11-21 2026-11-21-obsidian-design-system: Obsidian / Linear Dark becomes the canonical design system (tokens dark+light, density, docs)
- 2026-11-22 2026-11-22-optimizer-pro: Prompt Optimizer Pro (engine settings, four workflows, scores, compression, library with folders)
- 2026-11-22 2026-11-22_production_audit: production audit for persistence, provider settings, responsive UI and dependency compatibility
