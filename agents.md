# agents.md: operating manual for AI agents

Read this first. Deep reference: `HANDOFF.md` (architecture, API, data model, decisions, open risks). UI work: `design.md` is mandatory. Runbook: `OPERATIONS.md`. Release history: `CHANGELOG.md`.

## 1. Project

Promptolog («Промптолог»): a web app inside Bitrix24 on the Alaio Vibecode platform. The user writes a raw idea; the app returns a structured prompt per target AI system (Claude, ChatGPT, Kimi, Qwen, Grok) in RU or EN. Each system has a versioned **skill** (Markdown); a built-in **agent** refreshes each skill every 10–15 days from whitelisted official sources, with golden tests, a canary and auto-rollback.

The owner works in GitHub Codespaces and deploys by himself. Agents produce source and patches only: no deployment, no real keys.

## 2. Stack and layout

- Node >= 22.5 (devcontainer: 24), TypeScript strict, Fastify 5, `node:sqlite`, zod 4. React 18, Vite, Tailwind 3 with a hand-written design system in `index.css`, lucide-react, marked + DOMPurify. Tests: vitest.
- `shared/src/index.ts`: constants, zod schemas, DTO types. `apps/server/src/*`: backend. `apps/web/src/*`: `App.tsx` (shell), `ui.tsx` (primitives), `strings.ru.ts` (all UI strings), `index.css`, `screens/*`, `components/*`. `scripts/`, `tests/`, `patches/` (archived patch scripts).

## 3. Commands

```
npm ci
npm run typecheck
npm run build                     # typecheck + vite build + esbuild
npm test
DEV_AUTH_BYPASS=1 DATA_DIR=./data npm run dev:server     # :3000 (bypass ignored in production)
npm run dev:web                                           # :5173, proxies /api to :3000
node scripts/smoke.mjs --base http://127.0.0.1:3000
npm run pack:repomix              # refresh repomix-output.xml
```

## 4. Language policy

- Think, write code, comments, commits and docs in English.
- App UI strings are Russian and live only in `apps/web/src/strings.ru.ts`.
- Reports and chat replies to the owner are in Russian.

## 5. Hard rules

1. `CHANGELOG.md` and `HANDOFF.md` are changed only through `scripts/docs_update.py` (`npm run docs:*`), never by hand. Never run its usage examples verbatim: the placeholders (`...`, `id: summary`) get written into the files. Use `--dry-run` first.
2. Deliver changes as ONE Python patch script plus Codespaces commands (sections 7 and 8). Loose snippets only when the owner asks.
3. Preserve business logic, API routes, persisted data and enum values, permissions. UI tasks do not touch `apps/server`, `shared` or `tests` unless the task says so.
4. No UI strings outside `strings.ru.ts`. No colors, spacing, radii or shadows outside design tokens.
5. Never print or commit secrets. Use `REPLACE_WITH_…` placeholders. Do not invent platform API contracts: unverified ones are listed in `HANDOFF.md` section 10.
6. No new dependency without approval (state why and the size). No CDN assets: CSP and the iframe forbid them. Keep `package-lock.json` committed (repomix omits it).
7. Do not hide defects: no `overflow: hidden` to mask a layout bug, no extra wrapper hacks (`design.md` §17).
8. Report a conflict between a requirement and the architecture early. Take the smallest maintainable change. Ask at most one question, and only if blocked; otherwise state the assumption and proceed.
9. `localStorage` is always wrapped in `try/catch` (blocked in iframes). SQL only through prepared statements. zod validates every input.

## 6. Design system

Before any UI task read `design.md` fully: Part 0 is the canonical Obsidian / Linear Dark system (dark default, light sibling, indigo accent, tokens in `apps/web/src/styles/tokens.css`); Part I (the «Ноябрь» brief) and Addendum A keep structure, accessibility, engineering and QA rules, and their visual values are superseded. Decisions D1–D5 are resolved (D2 superseded: dark default). Tokens and the shell are implemented; the screens still use deprecated flat aliases (`glass`, `card`, `inset-field`) until migrated. Run `npm run audit:contrast` after any token change.

## 7. Patch-script standard

File `patch_<YYYY-MM-DD>_<slug>.py` in the repo root. Python 3.12, stdlib only.

- Docstring with usage; `PATCH_ID` and `PATCH_DATE` constants.
- `find_root()` checks `package.json` name is `promptolog`.
- Two-phase: build the whole plan in memory, validate every anchor, write nothing if any check fails.
- Idempotent: a re-run prints "Nothing to do". Anchors use `replace_once(rel, old, new, marker)`. New files never overwrite existing ones unless explicitly forced.
- LF newlines. Backups to `.patch-backup/<PATCH_ID>/`. Flags: `--dry-run`, `--diff`, `--commit`, `--no-backup`, `--root`.
- Docs go through `scripts/docs_update.py` functions. The script archives itself to `patches/`.
- Validate `package.json` stays valid JSON after edits.
- Test the script on a clean copy of the repo (dry-run, apply, re-apply) before handing it over, and say what could not be run.

## 8. Codespaces activation

```
cd /workspaces/<repo>
python3 patch_<id>.py --dry-run --diff
python3 patch_<id>.py
npm ci && npm run build && npm test
git status && git add -A && git commit -m "<type>: <imperative summary>"
npm run pack:repomix
```

Commit style: imperative, with a type prefix (`feat:`, `fix:`, `style:`, `docs:`, `chore:`). Legacy phase commits looked like `phase 4: ...`.

## 9. Workflow for every task

1. Read the task, the relevant `HANDOFF.md` sections and the actual files. Never assume a file's content; if it is not in the pack or the repo, say so and ask for it.
2. State assumptions in one to three lines.
3. Implement the smallest change that satisfies the intent. No stubs in working scenarios.
4. Verify: `typecheck`, `build`, `test`; for UI also run the app and inspect it (section 10).
5. Record the change through `docs_update.py`: changelog entries under `[Unreleased]`; handoff decisions, limitations and the patch log.
6. Report to the owner (section 12).

## 10. UI QA (design.md §18)

- Run `dev:server` and `dev:web`; inspect the rendered result, not only the code.
- Screenshots before and after at 2048, 1440, 1280 and 390px (add 1024 and 768 for responsive checks). Playwright through `npx --yes playwright` is fine ad hoc; do not add it to `package.json` without approval. Keep screenshots out of the repo.
- Test the iframe behavior with a local harness page that embeds the app and listens for `vibe:resize` (see `design.md` A6, conflict C1).
- Check: console errors, keyboard navigation and visible focus, reduced motion, no horizontal overflow, contrast of rendered text, and unchanged routes and API calls.

## 11. Definition of done

- Build and tests pass; no unrelated files changed; docs updated through the tool.
- UI tasks: `design.md` §19 checklist plus Addendum A9.
- Patch scripts: tested as in section 7.

## 12. Report format (to the owner, in Russian, short)

1. Что сделано. 2. Файлы. 3. Как проверено (команды и результат; что не удалось запустить). 4. Отклонения, решения по умолчанию, риски. 5. Команды для Codespaces.

## 13. Known traps

- Seed templates are inserted by title at start; template `language` supports only `ru|en`.
- Deleting a generation hides its favourites too (soft delete is a full removal from all views).
- `DEV_AUTH_BYPASS=1` works only when `NODE_ENV` is not `production`.
- The app lives in an auto-height iframe: `position: fixed` and `100vh` do not behave like in a normal page (conflict C1 in `design.md`).
- TypeScript 7 and Vite 8 versions are pinned by the lockfile; use `npm ci`, not `npm install`, for reproducible builds.
- `repomix-output.xml` is a read-only snapshot and may be stale.
