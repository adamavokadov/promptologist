# Changelog

All notable changes to this project are documented here. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), versioning: [SemVer](https://semver.org/).

## [Unreleased]

### Added
- Seed template «Граф узлов для Claude Code (по Karpathy, Opus 5.5)»: Spanish agent-graph prompt inspired by Andrej Karpathy's autoresearch (bounded nodes, deterministic code nodes, evidence gates, graph.md / checks.md / progress.md handoff) with variables `{{tarea}}`, `{{salida}}`, `{{checks}}`, `{{fuentes}}`, `{{alcance}}`, `{{limite}}`; flagged EN because template language supports only ru/en.
- Tests: seed-template invariants (unique titles, valid variables, size limits) and a structure test for the agent-graph template.
- Repository hygiene: `.editorconfig`, `.gitattributes`, `.nvmrc`, `.devcontainer/devcontainer.json` (Node 24, Python 3), `.github/workflows/ci.yml` (build and test on Node 22 and 24), `repomix.config.json`.
- `scripts/docs_update.py` and `docs:*` npm scripts: idempotent scripted updates of CHANGELOG.md and HANDOFF.md; applied patch scripts are archived in `patches/`.

### Changed
- .gitignore extended (env variants, data dir, coverage, tsbuildinfo, job_secret, OS/IDE files, repomix output, patch backups).
- Seed template count 8 -> 9 in tests (now derived from `SEED_TEMPLATES.length`), smoke script, README and OPERATIONS.

## [1.0.0] - 2026-11-13
First complete release. Source-only handover: the build, tests and archive were produced without access to the Vibecode platform; platform contracts that could not be verified are listed in HANDOFF.md ("Open risks").

### Phase 5 - Polish (2026-11-13)
- Neo-glassmorphism design system: aurora background, noise/grid overlays, glass surfaces with a solid fallback, dark/light/system themes, micro-interactions, skeleton shimmer, toasts.
- Accessibility: keyboard navigation, Ctrl+Enter, focus traps in dialogs, Esc to close, aria labels, `prefers-reduced-motion`.
- Degradation banners (quota, agent paused, fallback scheduler), cold-start "app is waking" overlay, error boundary, empty states.
- Documentation: README, HANDOFF (AI-first), OPERATIONS, CHANGELOG.

### Phase 4 - Self-updating agent (2026-11-13)
- Single dispatcher job (`promptolog-dispatcher`) with HMAC signature verification, durable `runId` dedupe and background execution.
- Per-skill random schedule (10-15 days + 0-4 h jitter), retries 24-48 h, global TTL mutex, keep-alive, checkpoints with resume on restart.
- 9-step pipeline: plan, search, deep research (conditional), analyze, validate, golden tests (pairwise judge with randomised A/B), apply, canary (3 generations, auto-rollback on 2 hard failures), report and notify.
- Budgets (6 search, 1 research, 12 LLM calls, 150K tokens), quota auto-pause and auto-resume, lazy fallback scheduler, manual refresh with 6 h cooldown.

### Phase 3 - Skills manager (2026-11-13)
- Skills screen with statuses, versions, server-side diff, rollback (admin), pause, sources and changelog.

### Phase 2 - History, templates, favourites (2026-11-13)
- Full-text search (FTS5 with automatic LIKE fallback), filters, pagination, soft delete, retention that never removes favourites.
- Templates with `{{variables}}`, use-form with live preview, LLM generalisation, 8 seed templates, JSON export and template import.

### Phase 1 - Generation core (2026-11-13)
- Five seed skills; pipeline A-D (intent, per-system transformation with concurrency 2, checklist validation with one repair call, persistence).
- SSE transport with polling fallback, RU/EN output, clarifying-questions mode, per-card regeneration with feedback and variant history.

### Phase 0 - Skeleton (2026-11-13)
- Fastify + `node:sqlite` backend, React/Vite/Tailwind frontend, Gateway identity middleware, `/healthz`, SPA serving with CSP, build and deploy scripts.
