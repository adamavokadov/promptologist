# Promptolog («Промптолог»)

A web app for Alaio Vibecode (Bitrix24). The user writes a raw idea in their own words, picks target AI systems (Claude, ChatGPT, Kimi, Qwen, Grok) and an output language (RU/EN), and gets a complete, structured prompt for each system. Every system has its own versioned **skill**; a built-in **agent** refreshes each skill every 10-15 days from fresh official sources, with tests, a canary and automatic rollback.

UI language: Russian. Generated prompts: RU or EN (user's choice). Explanations ("what was improved", assumptions): always Russian.

## Features
- **Generator**: intent analysis, per-system transformation (2 in parallel), checklist validation with one repair call, SSE streaming with polling fallback, clarifying-questions mode, per-card regeneration with feedback and variant history, compare view.
- **History / Favourites / Templates**: full-text search, filters, soft delete, favourites per prompt, templates with `{{variables}}`, LLM generalisation, 9 seed templates, JSON export and template import.
- **Skills manager**: versions, server-side diff, rollback, pause, sources, changelog, manual refresh with cooldown.
- **Agent**: dispatcher job with signature check and dedupe, random per-skill schedule, golden tests with a pairwise judge, canary and auto-rollback, reports, lazy fallback scheduler, budgets.
- **Design**: neo-glassmorphism, dark/light/system themes, accessible, reduced-motion aware.

## Stack
Node.js >= 22.5 (platform runtime `node24`), TypeScript, Fastify 5, built-in `node:sqlite` (FTS5 when present, LIKE otherwise), zod; React 18 + Vite + Tailwind 3, lucide-react, marked + DOMPurify, jsdiff (`diff`), self-hosted Manrope and JetBrains Mono (no CDN). No axios: global `fetch` only.

## Quickstart (local)
```
npm ci
cp .env.example .env            # fill VIBE_API_KEY for real AI calls
npm run build
DEV_AUTH_BYPASS=1 DATA_DIR=./data npm start     # http://localhost:3000
# or two terminals with hot reload:
DEV_AUTH_BYPASS=1 npm run dev:server   &&   npm run dev:web
```
`DEV_AUTH_BYPASS=1` is honoured only when `NODE_ENV` is not `production`.

## Scripts
| Script | Purpose |
|---|---|
| `npm run build` | typecheck (server + web), `vite build` -> `dist/public`, esbuild bundle -> `dist/server.js` |
| `npm start` | `node dist/server.js` (listens on `PORT`) |
| `npm test` | vitest (unit + integration with a mocked AI router) |
| `npm run typecheck` | `tsc --noEmit` for both packages |
| `npm run deploy` | build archive and call the Deploy API (`scripts/deploy.mjs`, JSON mode) |
| `npm run smoke` | post-deploy checks (`scripts/smoke.mjs`) |
| `npm run pack:source` | create `deliverables/promptolog-source-v<version>.zip` |
| `npm run pack:repomix` | pack the repo into `repomix-output.xml` (`repomix.config.json`) |
| `npm run docs:changelog -- --added "..."` | scripted CHANGELOG.md update (`scripts/docs_update.py`); CHANGELOG/HANDOFF are never edited by hand |
| `npm run docs:handoff -- --decision "..."` | scripted HANDOFF.md update (decisions, limitations, patch log) |
| `npm run docs:release -- X.Y.Z` | turn `[Unreleased]` into a release and bump `package.json` / lockfile version |

## Environment variables (names only; see `.env.example`)
`VIBE_API_KEY` service key · `VIBE_APP_KEY` application key for identity · `VIBE_BASE_URL` · `VIBE_SERVER_ID` · `APP_PUBLIC_URL` · `DATA_DIR` · `JOB_SECRET` · `JOB_SECRET_PREVIOUS` · `NODE_ENV` · `PORT` (platform-injected) · `DEV_AUTH_BYPASS` (dev only) · `FRAME_ANCESTORS` (optional CSP override). All runtime-tunable options live in the `settings` table, not in env.

## Project structure
```
apps/server/src   Fastify API, SQLite, generation pipeline, refresh agent, job handling
apps/web/src      React SPA (screens/, components/, strings.ru.ts, api.ts)
shared/src        zod schemas, constants, template/language helpers (used by both)
scripts/          deploy.mjs, smoke.mjs, pack-source.mjs
tests/            vitest suites and helpers
```
Details: [HANDOFF.md](HANDOFF.md). Operations: [OPERATIONS.md](OPERATIONS.md). History: [CHANGELOG.md](CHANGELOG.md).

## Testing
`npm test` covers: scheduler bounds and retries, mutex, job signature (with the platform reference vector), runId dedupe, template variables, language heuristic, all zod contracts, checklist validator, canary and rollback, the generation pipeline (partial failure, repair, questions mode, quota), the refresh pipeline (no_changes / updated / rejected / budget / resume / degraded search) and the HTTP API (auth, scoping, rate limit, SSE, admin guards).

### Manual QA checklist (10 scenarios)
1. First open from the Bitrix24 left menu: name/initials shown, iframe height adapts, cold start shows the "waking" overlay and recovers.
2. Generate for all 5 systems in RU, then in EN: five valid prompts, language matches the switch.
3. "Сначала спросить" mode: up to 3 questions appear, answering continues the run.
4. Regenerate one card with feedback ("короче"): variant arrows appear, other cards untouched.
5. Star a result: it appears in Favourites; clearing history keeps it.
6. Create a template with variables, use it: form + live preview, "В генератор" prefills (no auto-run).
7. Skills -> "Проверить сейчас": run starts, a report appears; the button is disabled during the 6 h cooldown.
8. Skills -> Versions: select two versions, read the diff, roll back with confirmation; the report shows the rollback.
9. Switch to the light theme and back; system theme follows the OS.
10. Narrow the iframe below 800 px: bottom tab bar replaces the rail, everything stays usable.

## Troubleshooting
- **App is "waking"**: Galaxy containers sleep when idle; a cold start can take minutes. The UI retries on 503/network errors for up to 5 minutes.
- **"Квота ИИ исчерпана"**: HTTP 402 from the AI router. The agent pauses itself and resumes after a successful daily probe.
- **Scheduler shows Fallback**: jobs are unavailable on this deployment (entitlement) or `VIBE_SERVER_ID` is missing. See OPERATIONS.md.
- **401 in the UI**: open the app from the Bitrix24 menu (Gateway headers are required).
- **Search unavailable**: the agent runs in LLM-only audit mode and says so in reports.

## Platform documentation
[Docs](https://vibecode.bitrix24.com/docs) · [llms.txt](https://vibecode.bitrix24.com/llms.txt) · [App runtime](https://vibecode.bitrix24.com/docs/infra/app-runtime) · [Scheduled jobs](https://vibecode.bitrix24.com/docs/infra/jobs) · [Verify signatures](https://vibecode.bitrix24.com/docs/infra/jobs/signature) · [Errors](https://vibecode.bitrix24.com/docs/errors)
