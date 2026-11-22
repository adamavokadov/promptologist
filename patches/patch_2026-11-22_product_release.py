#!/usr/bin/env python3
"""Prepare Promptolog v1.2.0 from the 2026-11-22 snapshot or the audited checkout.

From the repository root, run:
    python3 patch_2026-11-22_product_release.py --dry-run --diff
    python3 patch_2026-11-22_product_release.py
    npm ci && npm run build && npm test && npm run audit:contrast

Requires Python 3.12 and the tracked package-lock.json from the repository.
The bundled production audit runs first when its archive is not present.
The entire plan is validated before writing. Backups are under .patch-backup/.
An archived copy lives in patches/. --commit commits only planned files.
"""

from __future__ import annotations

import argparse
import base64
import difflib
import hashlib
import json
from pathlib import Path
import runpy
import stat
import subprocess
import sys
import tempfile
import zlib
from dataclasses import dataclass

PATCH_ID = '2026-11-22_product_release'
PATCH_DATE = '2026-11-22'
PATCH_FILE = f'patch_{PATCH_ID}.py'
COMMIT_MESSAGE = 'feat: release Promptolog workspace and team library'
AUDIT_FILE = 'patch_2026-11-22_production_audit.py'
RELEASE_VERSION = '1.2.0'

HUNKS = {
    'OPERATIONS.md': (
      ((
        'Runs checkpoint to `refresh_runs`; after a restart the app resumes unfinished runs. The global mutex expires after 60 minutes. To inspect: `sqlite3 <DATA_DIR>/promptolog.db "select id,skill_id,status,step from refresh_runs order by started_at desc limit 10"`.\n'
        '\n'
        '## Backups\n'
        'The only state is `<DATA_DIR>/promptolog.db` (+ `-wal`/`-shm`) and `job_secret`. Copy them while the app is idle, or use `sqlite3 .backup`.\n'
      ), (
        'Runs checkpoint to `refresh_runs`; after a restart the app resumes unfinished runs. The global mutex expires after 60 minutes. To inspect: `sqlite3 <DATA_DIR>/promptolog.db "select id,skill_id,status,step from refresh_runs order by started_at desc limit 10"`.\n'
        '\n'
        '## Backups\n'
        'The only state is `<DATA_DIR>/promptolog.db` (+ `-wal`/`-shm`) and `job_secret`. Copy them while the app is idle, or use `sqlite3 .backup`.\n'
        '\n'
        '## Release v1.2 verification\n'
        '\n'
        'Use the existing SQLite backup procedure before the release. Migration v3 adds the team library and text revisions on first boot. Verify a copy of a v2 database before changing the production origin. A data rollback should restore a consistent pre-release backup, which excludes edits made after that backup.\n'
        '\n'
        'In the Bitrix24 placement, open the application as a portal administrator, an assigned editor, an assigned reader and an employee without access. Publish one disposable prompt to a restricted test folder and verify discovery, use, editing and revision visibility. Open the same placement on a phone and check copying plus one external destination. Run generation, optimization and execution through the intended provider and check service quotas. Details live in the [workspace specification](docs/prompt-workspace.md).\n'
      )),
    ),
    'README.md': (
      ((
        '\n'
        'UI language: Russian. Generated prompts: RU or EN (user\'s choice). Explanations ("what was improved", assumptions): always Russian.\n'
        '\n'
        '## Features\n'
        '- **Generator**: intent analysis, per-system transformation (2 in parallel), checklist validation with one repair call, SSE streaming with polling fallback, clarifying-questions mode, per-card regeneration with feedback and variant history, compare view.\n'
        '- **History / Favourites / Templates**: full-text search, filters, soft delete, favourites per prompt, templates with `{{variables}}`, LLM generalisation, 9 seed templates, JSON export and template import.\n'
        '- **Prompt optimizer**: four workflows (one-click, clarifier, bracket-variable templates, reverse engineering), goal and framework presets, output format and tone, RU-EN-RU bridge, scores with changelog, prompt compression, library with folders and search; engine settings with provider adapters (key encrypted by `ENGINE_SECRET`).\n'
        '- **Skills manager**: versions, server-side diff, rollback, pause, sources, changelog, manual refresh with cooldown.\n'
      ), (
        '\n'
        'UI language: Russian. Generated prompts: RU or EN (user\'s choice). Explanations ("what was improved", assumptions): always Russian.\n'
        '\n'
        '## Features\n'
        '\n'
        '- The **New prompt** workspace routes a single input to Generation, Optimization or Clarification. Manual modes, role-based examples and a hypothesis validation preset are available.\n'
        '- Prompt results include a four-part checklist, forms for placeholders, a compression diff, copy-and-open actions and one-off model execution.\n'
        '- The Library includes portal-scoped team folders with reader and editor roles, and version history for editable prompt bodies. See [product and design decisions](docs/prompt-workspace.md).\n'
        '- **Generator**: intent analysis, per-system transformation (2 in parallel), checklist validation with one repair call, SSE streaming with polling fallback, clarifying-questions mode, per-card regeneration with feedback and variant history, compare view.\n'
        '- **History / Favourites / Templates**: full-text search, filters, soft delete, favourites per prompt, templates with `{{variables}}`, LLM generalisation, 9 seed templates, JSON export and template import.\n'
        '- **Prompt optimizer**: four workflows (one-click, clarifier, bracket-variable templates, reverse engineering), goal and framework presets, output format and tone, RU-EN-RU bridge, scores with changelog, prompt compression, library with folders and search; engine settings with provider adapters (key encrypted by `ENGINE_SECRET`).\n'
        '- **Skills manager**: versions, server-side diff, rollback, pause, sources, changelog, manual refresh with cooldown.\n'
      )),
    ),
    'apps/server/src/db.ts': (
      ((
        '  UNIQUE(user_id, name)\n'
        ');\n'
        'CREATE INDEX idx_folders_user ON folders(user_id);\n'
        '`,\n'
        '];\n'
        '\n'
        'export function openDb(file?: string): Db {\n'
        '  let target = file;\n'
      ), (
        '  UNIQUE(user_id, name)\n'
        ');\n'
        'CREATE INDEX idx_folders_user ON folders(user_id);\n'
        '`,\n'
        '  /* v3: prompt revision history and portal-scoped team folders */ `\n'
        'CREATE TABLE prompt_versions (\n'
        '  scope TEXT NOT NULL, prompt_id TEXT NOT NULL, version INTEGER NOT NULL,\n'
        '  body TEXT NOT NULL, created_at TEXT NOT NULL, PRIMARY KEY (scope, prompt_id, version)\n'
        ');\n'
        'CREATE TABLE team_folders (\n'
        '  id TEXT PRIMARY KEY, portal_id TEXT NOT NULL, name TEXT NOT NULL,\n'
        "  visibility TEXT NOT NULL CHECK (visibility IN ('portal', 'restricted')),\n"
        '  UNIQUE (portal_id, name)\n'
        ');\n'
        'CREATE TABLE team_folder_members (\n'
        '  folder_id TEXT NOT NULL, user_id TEXT NOT NULL,\n'
        "  role TEXT NOT NULL CHECK (role IN ('reader', 'editor')),\n"
        '  PRIMARY KEY (folder_id, user_id)\n'
        ');\n'
        'CREATE TABLE team_prompts (\n'
        '  id TEXT PRIMARY KEY, folder_id TEXT NOT NULL, title TEXT NOT NULL, body TEXT NOT NULL,\n'
        '  created_at TEXT NOT NULL, updated_at TEXT NOT NULL\n'
        ');\n'
        'CREATE INDEX idx_team_prompts_folder ON team_prompts(folder_id, updated_at DESC, id);\n'
        '`,\n'
        '\n'
        '];\n'
        '\n'
        'export function openDb(file?: string): Db {\n'
        '  let target = file;\n'
      )),
    ),
    'apps/server/src/generation.ts': (
      ((
        '  return [\n'
        "    intent ? `<intent>${JSON.stringify(intent)}</intent>` : '',\n"
        '    `<raw_request>${rawInput}</raw_request>`,\n'
        '    `<options>detail=${o.detail}; include_format=${o.include_format}; task_type=${o.task_type}</options>`,\n'
        "    refinement ? `<refinement>${refinement}</refinement>` : '',\n"
        "  ].filter(Boolean).join('\\n');\n"
        '}\n'
        '\n'
      ), (
        '  return [\n'
        "    intent ? `<intent>${JSON.stringify(intent)}</intent>` : '',\n"
        '    `<raw_request>${rawInput}</raw_request>`,\n'
        '    `<options>detail=${o.detail}; include_format=${o.include_format}; task_type=${o.task_type}</options>`,\n'
        "    o.task_type === 'hypothesis'\n"
        "      ? 'Design the finished prompt to generate a practical validation plan. Ask for the hypothesis, target segment, cheapest credible test, required resources, measurable success and stop thresholds, a timeframe and the decision after the test. Label inferred assumptions. Do not invent market evidence.'\n"
        "      : '',\n"
        "    refinement ? `<refinement>${refinement}</refinement>` : '',\n"
        "  ].filter(Boolean).join('\\n');\n"
        '}\n'
        '\n'
      )),
    ),
    'apps/server/src/optimizer-routes.ts': (
      ((
        "import { unindexDoc, type Db } from './db.ts';\n"
        "import type { Identity } from './auth.ts';\n"
        "import { rateLimit } from './auth.ts';\n"
        "import { AppError, nowIso } from './util.ts';\n"
        "import type { VibeClient } from './vibe.ts';\n"
        "import { engineChat, engineView, updateEngine } from './engine.ts';\n"
        'import {\n'
        '  answerOptimization, compressOptimization, createFolder, getOwned, listFolders, listOptimizations, ownFolder, reindex, rowToOptimization, runOptimization,\n'
        "} from './optimizer.ts';\n"
        "import { OPT_LIMITS, answerRequestSchema, engineUpdateSchema, optimizeRequestSchema, OPT_WORKFLOWS } from '../../../shared/src/index.ts';\n"
        '\n'
        'export interface OptimizerRouteDeps { db: Db; vibe: VibeClient; me: (req: FastifyRequest) => Identity; admin: (req: FastifyRequest) => Identity; fetchImpl?: typeof fetch }\n'
        '\n'
        'const paramsSchema = z.object({ id: z.string().min(1).max(60) });\n'
        '\n'
        '/** Prompt optimizer: engine settings, four workflows, compression, library with folders. All routes are under /api/optimizer. */\n'
        'export function registerOptimizerRoutes(app: FastifyInstance, d: OptimizerRouteDeps): void {\n'
        '  const { db, me, admin } = d; const deps = { vibe: d.vibe, fetchImpl: d.fetchImpl };\n'
      ), (
        "import { unindexDoc, type Db } from './db.ts';\n"
        "import type { Identity } from './auth.ts';\n"
        "import { rateLimit } from './auth.ts';\n"
        "import { AppError, nowIso } from './util.ts';\n"
        "import { withPromptStream } from './prompt-stream.ts';\n"
        "import { suggestAnswers, versionQuery } from './prompt-features.ts';\n"
        "import { appendPromptVersion, deletePromptVersions, listVersionsForPrompt } from './prompt-versions.ts';\n"
        "import type { VibeClient } from './vibe.ts';\n"
        "import { engineChat, engineView, updateEngine } from './engine.ts';\n"
        'import {\n'
        '  answerOptimization, compressOptimization, createFolder, getOwned, listFolders, listOptimizations, ownFolder, reindex, rowToOptimization, runOptimization,\n'
        "} from './optimizer.ts';\n"
        "import { OPT_LIMITS, answerRequestSchema, engineUpdateSchema, optimizeRequestSchema, promptIdSchema, promptRevisionSchema, OPT_WORKFLOWS } from '../../../shared/src/index.ts';\n"
        '\n'
        'export interface OptimizerRouteDeps { db: Db; vibe: VibeClient; me: (req: FastifyRequest) => Identity; admin: (req: FastifyRequest) => Identity; fetchImpl?: typeof fetch }\n'
        '\n'
        '/** Prompt optimizer: engine settings, four workflows, compression, library with folders. All routes are under /api/optimizer. */\n'
        'export function registerOptimizerRoutes(app: FastifyInstance, d: OptimizerRouteDeps): void {\n'
        '  const { db, me, admin } = d; const deps = { vibe: d.vibe, fetchImpl: d.fetchImpl };\n'
      )),
      ((
        '\n'
        '  // ---- engine settings (read for everyone, write for admins; the key is never returned) ----\n'
        "  app.get('/api/optimizer/engine', async () => engineView(db));\n"
        "  app.put('/api/optimizer/engine', async (req) => { admin(req); return updateEngine(db, engineUpdateSchema.parse(req.body)); });\n"
        "  app.post('/api/optimizer/engine/test', async (req) => {\n"
        '    const identity = admin(req);\n'
        '    limit(identity.userId);\n'
        '    const t0 = Date.now();\n'
        "    const r = await engineChat(db, deps, [{ role: 'user', content: 'Reply with the single word: ok' }], { maxTokens: 1024 });\n"
        '    return { ok: true, latency_ms: Date.now() - t0, provider: r.provider, model: r.model };\n'
        '  });\n'
        '\n'
        '  // ---- workflows ----\n'
        "  app.post('/api/optimizer/run', async (req) => { const id = me(req); limit(id.userId); return runOptimization(db, { userId: id.userId, deps }, optimizeRequestSchema.parse(req.body)); });\n"
        "  app.post('/api/optimizer/items/:id/answer', async (req) => { const id = me(req); limit(id.userId); return answerOptimization(db, { userId: id.userId, deps }, paramsSchema.parse(req.params).id, answerRequestSchema.parse(req.body)); });\n"
        "  app.post('/api/optimizer/items/:id/compress', async (req) => { const id = me(req); limit(id.userId); return compressOptimization(db, { userId: id.userId, deps }, paramsSchema.parse(req.params).id); });\n"
        '\n'
        '  // ---- library ----\n'
        "  app.get('/api/optimizer/items', async (req) => {\n"
        '    const id = me(req);\n'
        '    const q = z.object({ page: z.coerce.number().int().min(1).default(1), q: z.string().max(200).optional(), folder: z.string().max(60).optional(),\n'
        "      favorites: z.enum(['0', '1']).optional(), workflow: z.enum(OPT_WORKFLOWS).optional() }).parse(req.query);\n"
        "    return listOptimizations(db, id.userId, { q: q.q, folder: q.folder, favorites: q.favorites === '1', workflow: q.workflow, page: q.page });\n"
        '  });\n'
        "  app.get('/api/optimizer/items/:id', async (req) => rowToOptimization(getOwned(db, paramsSchema.parse(req.params).id, me(req).userId)));\n"
        "  app.patch('/api/optimizer/items/:id', async (req) => {\n"
        '    const id = me(req); const row = getOwned(db, paramsSchema.parse(req.params).id, id.userId);\n'
        '    const body = z.object({ is_favorite: z.boolean().optional(), folder_id: z.string().max(60).nullable().optional(),\n'
        '      var_values: z.record(z.string().max(60), z.string().max(OPT_LIMITS.variableValue)).optional(), tags: z.array(z.string().trim().min(1).max(30)).max(8).optional() }).parse(req.body);\n'
        '    if (body.folder_id != null) ownFolder(db, body.folder_id, id.userId);\n'
        '    return db.tx(() => {\n'
      ), (
        '\n'
        '  // ---- engine settings (read for everyone, write for admins; the key is never returned) ----\n'
        "  app.get('/api/optimizer/engine', async () => engineView(db));\n"
        "  app.put('/api/optimizer/engine', async (req) => { admin(req); return updateEngine(db, engineUpdateSchema.parse(req.body)); });\n"
        "  app.post('/api/optimizer/engine/test', async (req, reply) => {\n"
        '    const identity = admin(req);\n'
        '    limit(identity.userId);\n'
        '    const t0 = Date.now();\n'
        '    return withPromptStream(req, reply, async () => {\n'
        "      const r = await engineChat(db, deps, [{ role: 'user', content: 'Reply with the single word: ok' }], { maxTokens: 1024 });\n"
        '      return { ok: true, latency_ms: Date.now() - t0, provider: r.provider, model: r.model };\n'
        '    });\n'
        '  });\n'
        '\n'
        '  // ---- workflows ----\n'
        "  app.post('/api/optimizer/run', async (req, reply) => {\n"
        '    const { userId } = me(req);\n'
        '    limit(userId);\n'
        '    const input = optimizeRequestSchema.parse(req.body);\n'
        '    return withPromptStream(req, reply, () => runOptimization(db, { userId, deps }, input));\n'
        '  });\n'
        "  app.post('/api/optimizer/items/:id/answer', async (req, reply) => {\n"
        '    const { userId } = me(req);\n'
        '    limit(userId);\n'
        '    const { id } = promptIdSchema.parse(req.params);\n'
        '    const input = answerRequestSchema.parse(req.body);\n'
        '    return withPromptStream(req, reply, () => answerOptimization(db, { userId, deps }, id, input));\n'
        '  });\n'
        "  app.post('/api/optimizer/items/:id/compress', async (req, reply) => {\n"
        '    const { userId } = me(req);\n'
        '    limit(userId);\n'
        '    const { id } = promptIdSchema.parse(req.params);\n'
        '    return withPromptStream(req, reply, () => compressOptimization(db, { userId, deps }, id));\n'
        '  });\n'
        '\n'
        "  app.post('/api/optimizer/items/:id/suggest', async (req, reply) => {\n"
        '    const who = me(req);\n'
        '    const { id } = promptIdSchema.parse(req.params);\n'
        '    const item = rowToOptimization(getOwned(db, id, who.userId));\n'
        "    if (item.status !== 'draft_questions' || !item.clarifying_questions.length) {\n"
        "      throw new AppError(409, 'not_awaiting_answers', 'Уточнение уже завершено');\n"
        '    }\n'
        '    limit(who.userId);\n'
        '    return withPromptStream(req, reply, () => suggestAnswers(db, deps, item.raw_input, item.clarifying_questions));\n'
        '  });\n'
        '\n'
        '  const savedPrompt = (req: FastifyRequest) => {\n'
        '    const row = getOwned(db, promptIdSchema.parse(req.params).id, me(req).userId);\n'
        "    if (row.status !== 'ok') throw new AppError(409, 'not_ready', 'Сначала сформируйте промпт');\n"
        '    return row;\n'
        '  };\n'
        "  app.get('/api/optimizer/items/:id/versions', async (req) => {\n"
        '    const row = savedPrompt(req);\n'
        '    const source = { id: row.id, body: row.final_prompt, created_at: row.created_at };\n'
        "    return listVersionsForPrompt(db, 'optimization', source, versionQuery.parse(req.query).before);\n"
        '  });\n'
        "  app.put('/api/optimizer/items/:id/prompt', async (req) => {\n"
        '    const { body, expected_version } = promptRevisionSchema.parse(req.body);\n'
        '    return db.tx(() => {\n'
        '      const row = savedPrompt(req);\n'
        "      appendPromptVersion(db, 'optimization', { id: row.id, body: row.final_prompt, created_at: row.created_at }, body, expected_version);\n"
        '      if (body === row.final_prompt) return rowToOptimization(row);\n'
        '      db.run(`UPDATE optimizations SET final_prompt = ?, compressed_prompt = NULL, tokens_before = NULL, tokens_after = NULL,\n'
        "        initial_score = NULL, optimized_score = NULL, initial_critique = '', changelog = '[]', framework_used = '', updated_at = ? WHERE id = ?`,\n"
        '        body, nowIso(), row.id);\n'
        '      const next = savedPrompt(req);\n'
        '      reindex(db, next);\n'
        '      return rowToOptimization(next);\n'
        '    });\n'
        '  });\n'
        '\n'
        '  // ---- library ----\n'
        "  app.get('/api/optimizer/items', async (req) => {\n"
        '    const id = me(req);\n'
        '    const q = z.object({ page: z.coerce.number().int().min(1).default(1), q: z.string().max(200).optional(), folder: z.string().max(60).optional(),\n'
        "      favorites: z.enum(['0', '1']).optional(), workflow: z.enum(OPT_WORKFLOWS).optional() }).parse(req.query);\n"
        "    return listOptimizations(db, id.userId, { q: q.q, folder: q.folder, favorites: q.favorites === '1', workflow: q.workflow, page: q.page });\n"
        '  });\n'
        "  app.get('/api/optimizer/items/:id', async (req) => rowToOptimization(getOwned(db, promptIdSchema.parse(req.params).id, me(req).userId)));\n"
        "  app.patch('/api/optimizer/items/:id', async (req) => {\n"
        '    const id = me(req); const row = getOwned(db, promptIdSchema.parse(req.params).id, id.userId);\n'
        '    const body = z.object({ is_favorite: z.boolean().optional(), folder_id: z.string().max(60).nullable().optional(),\n'
        '      var_values: z.record(z.string().max(60), z.string().max(OPT_LIMITS.variableValue)).optional(), tags: z.array(z.string().trim().min(1).max(30)).max(8).optional() }).parse(req.body);\n'
        '    if (body.folder_id != null) ownFolder(db, body.folder_id, id.userId);\n'
        '    return db.tx(() => {\n'
      )),
      ((
        '      return rowToOptimization(next);\n'
        '    });\n'
        '  });\n'
        "  app.delete('/api/optimizer/items/:id', async (req) => {\n"
        '    const id = me(req); const row = getOwned(db, paramsSchema.parse(req.params).id, id.userId);\n'
        '    db.tx(() => {\n'
        "      db.run('DELETE FROM optimizations WHERE id = ?', row.id);\n"
        "      unindexDoc(db, 'opt', row.id);\n"
        '    });\n'
        '    return { ok: true };\n'
        '  });\n'
        '\n'
        '  // ---- folders ----\n'
        "  app.get('/api/optimizer/folders', async (req) => ({ items: listFolders(db, me(req).userId) }));\n"
        "  app.post('/api/optimizer/folders', async (req) => createFolder(db, me(req).userId, z.object({ name: z.string().max(OPT_LIMITS.folderName * 2) }).parse(req.body).name));\n"
        "  app.patch('/api/optimizer/folders/:id', async (req) => {\n"
        '    const id = me(req); const f = ownFolder(db, paramsSchema.parse(req.params).id, id.userId);\n'
        "    if (f.default_key) throw new AppError(409, 'folder_protected', 'Стандартную папку нельзя переименовать');\n"
        '    const name = z.object({ name: z.string().trim().min(1).max(OPT_LIMITS.folderName) }).parse(req.body).name;\n'
        "    if (db.get('SELECT 1 FROM folders WHERE user_id = ? AND name = ? AND id <> ?', id.userId, name, f.id)) throw new AppError(409, 'folder_exists', 'Папка с таким названием уже есть');\n"
        "    db.run('UPDATE folders SET name = ? WHERE id = ?', name, f.id);\n"
        '    return listFolders(db, id.userId).find((x) => x.id === f.id);\n'
        '  });\n'
        "  app.delete('/api/optimizer/folders/:id', async (req) => {\n"
        '    const id = me(req); const f = ownFolder(db, paramsSchema.parse(req.params).id, id.userId);\n'
        "    if (f.default_key) throw new AppError(409, 'folder_protected', 'Стандартную папку нельзя удалить');\n"
        "    db.tx(() => { db.run('UPDATE optimizations SET folder_id = NULL WHERE user_id = ? AND folder_id = ?', id.userId, f.id); db.run('DELETE FROM folders WHERE id = ?', f.id); });\n"
        '    return { ok: true };\n'
        '  });\n'
      ), (
        '      return rowToOptimization(next);\n'
        '    });\n'
        '  });\n'
        "  app.delete('/api/optimizer/items/:id', async (req) => {\n"
        '    const id = me(req); const row = getOwned(db, promptIdSchema.parse(req.params).id, id.userId);\n'
        '    db.tx(() => {\n'
        "      db.run('DELETE FROM optimizations WHERE id = ?', row.id);\n"
        "      unindexDoc(db, 'opt', row.id);\n"
        "      deletePromptVersions(db, 'optimization', row.id);\n"
        '    });\n'
        '    return { ok: true };\n'
        '  });\n'
        '\n'
        '  // ---- folders ----\n'
        "  app.get('/api/optimizer/folders', async (req) => ({ items: listFolders(db, me(req).userId) }));\n"
        "  app.post('/api/optimizer/folders', async (req) => createFolder(db, me(req).userId, z.object({ name: z.string().max(OPT_LIMITS.folderName * 2) }).parse(req.body).name));\n"
        "  app.patch('/api/optimizer/folders/:id', async (req) => {\n"
        '    const id = me(req); const f = ownFolder(db, promptIdSchema.parse(req.params).id, id.userId);\n'
        "    if (f.default_key) throw new AppError(409, 'folder_protected', 'Стандартную папку нельзя переименовать');\n"
        '    const name = z.object({ name: z.string().trim().min(1).max(OPT_LIMITS.folderName) }).parse(req.body).name;\n'
        "    if (db.get('SELECT 1 FROM folders WHERE user_id = ? AND name = ? AND id <> ?', id.userId, name, f.id)) throw new AppError(409, 'folder_exists', 'Папка с таким названием уже есть');\n"
        "    db.run('UPDATE folders SET name = ? WHERE id = ?', name, f.id);\n"
        '    return listFolders(db, id.userId).find((x) => x.id === f.id);\n'
        '  });\n'
        "  app.delete('/api/optimizer/folders/:id', async (req) => {\n"
        '    const id = me(req); const f = ownFolder(db, promptIdSchema.parse(req.params).id, id.userId);\n'
        "    if (f.default_key) throw new AppError(409, 'folder_protected', 'Стандартную папку нельзя удалить');\n"
        "    db.tx(() => { db.run('UPDATE optimizations SET folder_id = NULL WHERE user_id = ? AND folder_id = ?', id.userId, f.id); db.run('DELETE FROM folders WHERE id = ?', f.id); });\n"
        '    return { ok: true };\n'
        '  });\n'
      )),
    ),
    'apps/server/src/optimizer.ts': (
      ((
        "import type { Db } from './db.ts';\n"
        "import { acquireLock, indexDoc, releaseLock, searchDocs, unindexDoc } from './db.ts';\n"
        "import { AppError, jsonParse, nowIso, uid } from './util.ts';\n"
        "import { engineJson, type EngineDeps } from './engine.ts';\n"
        'import {\n'
        '  BRIDGE_CONSTRAINT, DEFAULT_FOLDERS, OPT_LIMITS, clarifierOutputSchema, compressOutputSchema, estimateTokens, extractBracketVars,\n'
      ), (
        "import type { Db } from './db.ts';\n"
        "import { acquireLock, indexDoc, releaseLock, searchDocs, unindexDoc } from './db.ts';\n"
        "import { deletePromptVersions } from './prompt-versions.ts';\n"
        "import { AppError, jsonParse, nowIso, uid } from './util.ts';\n"
        "import { engineJson, type EngineDeps } from './engine.ts';\n"
        'import {\n'
        '  BRIDGE_CONSTRAINT, DEFAULT_FOLDERS, OPT_LIMITS, clarifierOutputSchema, compressOutputSchema, estimateTokens, extractBracketVars,\n'
      )),
      ((
        "  friendly: 'Tone of the answer: friendly and empathetic.', concise: 'Tone of the answer: concise.',\n"
        "  no_yapping: 'Tone of the answer: no fluff. The target model must give the answer immediately, with no introduction, no conclusion, and no filler.',\n"
        '};\n'
        'const OUTPUT_SCHEMA = `Return ONE JSON object and nothing else:\n'
        '{"initial_score": number 1-10 (quality of the user\'s ORIGINAL request as a prompt), "initial_critique": string (one or two sentences, Russian, what is weak),\n'
        '"optimized_score": number 1-10 (quality of your final prompt), "changelog_explanation": string[] (3 to 7 items, Russian, each says WHAT was added and WHY it helps the target model),\n'
        '"final_prompt": string (the ready-to-use prompt), "framework_used": string (framework or goal applied, short)}`;\n'
        '\n'
        'export interface BuildCtx { req: OptimizeRequest; answers?: { q: string; a: string }[]; auto?: boolean }\n'
        "export function buildOptimizeMessages(c: BuildCtx): { role: 'system' | 'user'; content: string }[] {\n"
      ), (
        "  friendly: 'Tone of the answer: friendly and empathetic.', concise: 'Tone of the answer: concise.',\n"
        "  no_yapping: 'Tone of the answer: no fluff. The target model must give the answer immediately, with no introduction, no conclusion, and no filler.',\n"
        '};\n'
        'const OUTPUT_SCHEMA = `Return ONE JSON object and nothing else:\n'
        '{"initial_critique": string (one or two sentences, Russian, what is missing),\n'
        '"changelog_explanation": string[] (3 to 7 items, Russian, each says WHAT was added and WHY it helps the target model),\n'
        '"final_prompt": string (the ready-to-use prompt), "framework_used": string (framework or goal applied, short)}`;\n'
        '\n'
        'export interface BuildCtx { req: OptimizeRequest; answers?: { q: string; a: string }[]; auto?: boolean }\n'
        "export function buildOptimizeMessages(c: BuildCtx): { role: 'system' | 'user'; content: string }[] {\n"
      )),
      ((
        '    req.bridge\n'
        '      ? \'LANGUAGE BRIDGE: write "final_prompt" entirely in dense, natural English even though the input may be in Russian. Do NOT add any instruction about the answer language: the system appends it.\'\n'
        '      : \'Write "final_prompt" in the same language as the user input (Russian input gives a Russian prompt).\',\n'
        "    'Fields initial_critique and changelog_explanation are always in Russian. Never invent facts about the user; mark assumptions explicitly.',\n"
        '    OUTPUT_SCHEMA,\n'
        '  ].filter(Boolean);\n'
        '  let user = `<user_input>\\n${req.raw_input}\\n</user_input>`;\n'
        "  if (c.answers?.length) user += `\\n<user_answers>\\n${c.answers.map((x, i) => `${i + 1}. Q: ${x.q}\\n   A: ${x.a || '(no answer)'}`).join('\\n')}\\n</user_answers>`;\n"
      ), (
        '    req.bridge\n'
        '      ? \'LANGUAGE BRIDGE: write "final_prompt" entirely in dense, natural English even though the input may be in Russian. Do NOT add any instruction about the answer language: the system appends it.\'\n'
        '      : \'Write "final_prompt" in the same language as the user input (Russian input gives a Russian prompt).\',\n'
        "    'Fields initial_critique and changelog_explanation are always in Russian. Never invent facts about the user; mark assumptions explicitly.',\n"
        "    'Make role, context, constraints and output format explicit where applicable. Prefer short labelled lines if compatible with the selected framework. Never invent missing domain facts or assign numeric scores.',\n"
        '    OUTPUT_SCHEMA,\n'
        '  ].filter(Boolean);\n'
        '  let user = `<user_input>\\n${req.raw_input}\\n</user_input>`;\n'
        "  if (c.answers?.length) user += `\\n<user_answers>\\n${c.answers.map((x, i) => `${i + 1}. Q: ${x.q}\\n   A: ${x.a || '(no answer)'}`).join('\\n')}\\n</user_answers>`;\n"
      )),
      ((
        '  if (!bridge) return prompt;\n'
        "  const cleaned = prompt.split('\\n').filter((l) => !/CRITICAL INSTRUCTION:\\s*Perform all internal reasoning/i.test(l)).join('\\n').trimEnd();\n"
        '  return `${cleaned}\\n\\n${BRIDGE_CONSTRAINT}`;\n'
        '}\n'
        "function varsFor(workflow: OptWorkflow, prompt: string): string[] { return workflow === 'template' || workflow === 'reverse' ? extractBracketVars(prompt) : []; }\n"
        '\n'
        '// ---------- persistence ----------\n'
        'export function rowToOptimization(r: Row): OptimizationDTO {\n'
        "  const options = jsonParse<Record<string, any>>(r.options, {}); const prompt = String(r.final_prompt ?? '');\n"
      ), (
        '  if (!bridge) return prompt;\n'
        "  const cleaned = prompt.split('\\n').filter((l) => !/CRITICAL INSTRUCTION:\\s*Perform all internal reasoning/i.test(l)).join('\\n').trimEnd();\n"
        '  return `${cleaned}\\n\\n${BRIDGE_CONSTRAINT}`;\n'
        '}\n'
        'function varsFor(prompt: string): string[] { return extractBracketVars(prompt); }\n'
        '\n'
        '// ---------- persistence ----------\n'
        'export function rowToOptimization(r: Row): OptimizationDTO {\n'
        "  const options = jsonParse<Record<string, any>>(r.options, {}); const prompt = String(r.final_prompt ?? '');\n"
      )),
      ((
        "    options: { preset: options.preset ?? 'auto', output_format: options.output_format ?? 'none', tone: options.tone ?? 'none', bridge: !!options.bridge },\n"
        '    clarifying_questions: jsonParse(r.questions, []), answers: jsonParse(r.answers, []),\n'
        "    initial_score: r.initial_score ?? null, initial_critique: r.initial_critique ?? '', optimized_score: r.optimized_score ?? null,\n"
        "    changelog_explanation: jsonParse(r.changelog, []), final_prompt: prompt, framework_used: r.framework_used ?? '',\n"
        '    variables: varsFor(r.workflow, prompt), var_values: jsonParse(r.var_values, {}),\n'
        '    compressed_prompt: r.compressed_prompt ?? null, tokens_before: r.tokens_before ?? null, tokens_after: r.tokens_after ?? null,\n'
        "    is_favorite: !!r.is_favorite, folder_id: r.folder_id ?? null, tags: jsonParse(r.tags, []), provider: r.provider ?? '', model: r.model ?? '', created_at: r.created_at,\n"
        '  };\n'
        '}\n'
      ), (
        "    options: { preset: options.preset ?? 'auto', output_format: options.output_format ?? 'none', tone: options.tone ?? 'none', bridge: !!options.bridge },\n"
        '    clarifying_questions: jsonParse(r.questions, []), answers: jsonParse(r.answers, []),\n'
        "    initial_score: r.initial_score ?? null, initial_critique: r.initial_critique ?? '', optimized_score: r.optimized_score ?? null,\n"
        "    changelog_explanation: jsonParse(r.changelog, []), final_prompt: prompt, framework_used: r.framework_used ?? '',\n"
        '    variables: varsFor(prompt), var_values: jsonParse(r.var_values, {}),\n'
        '    compressed_prompt: r.compressed_prompt ?? null, tokens_before: r.tokens_before ?? null, tokens_after: r.tokens_after ?? null,\n'
        "    is_favorite: !!r.is_favorite, folder_id: r.folder_id ?? null, tags: jsonParse(r.tags, []), provider: r.provider ?? '', model: r.model ?? '', created_at: r.created_at,\n"
        '  };\n'
        '}\n'
      )),
      ((
        '}\n'
        'const RETENTION_CAP = 2000;\n'
        'function applyRetention(db: Db, userId: string): void {\n'
        '  const extra = db.all<{ id: string }>(`SELECT id FROM optimizations WHERE user_id = ? AND deleted_at IS NULL AND is_favorite = 0 AND folder_id IS NULL ORDER BY created_at DESC LIMIT -1 OFFSET ?`, userId, RETENTION_CAP);\n'
        "  for (const e of extra) { db.run('DELETE FROM optimizations WHERE id = ?', e.id); unindexDoc(db, 'opt', e.id); }\n"
        '}\n'
        '\n'
        'function ensureDefaultFolders(db: Db, userId: string): void {\n'
        "  const have = new Set(db.all<{ default_key: string }>('SELECT default_key FROM folders WHERE user_id = ? AND default_key IS NOT NULL', userId).map((r) => r.default_key));\n"
      ), (
        '}\n'
        'const RETENTION_CAP = 2000;\n'
        'function applyRetention(db: Db, userId: string): void {\n'
        '  const extra = db.all<{ id: string }>(`SELECT id FROM optimizations WHERE user_id = ? AND deleted_at IS NULL AND is_favorite = 0 AND folder_id IS NULL ORDER BY created_at DESC LIMIT -1 OFFSET ?`, userId, RETENTION_CAP);\n'
        '  for (const { id } of extra) {\n'
        "    db.run('DELETE FROM optimizations WHERE id = ?', id);\n"
        "    unindexDoc(db, 'opt', id);\n"
        "    deletePromptVersions(db, 'optimization', id);\n"
        '  }\n'
        '}\n'
        '\n'
        'function ensureDefaultFolders(db: Db, userId: string): void {\n'
        "  const have = new Set(db.all<{ default_key: string }>('SELECT default_key FROM folders WHERE user_id = ? AND default_key IS NOT NULL', userId).map((r) => r.default_key));\n"
      )),
      ((
        'function saveOptimization(db: Db, userId: string, id: string, ctx: BuildCtx, result: Awaited<ReturnType<typeof optimize>>): OptimizationDTO {\n'
        '  const { data } = result;\n'
        "  db.run(`UPDATE optimizations SET status = 'ok', answers = ?, initial_score = ?, initial_critique = ?, optimized_score = ?, changelog = ?,\n"
        '    final_prompt = ?, framework_used = ?, provider = ?, model = ?, tokens_used = tokens_used + ?, updated_at = ? WHERE id = ?`,\n'
        '    JSON.stringify((ctx.answers ?? []).map(({ a }) => a)), data.initial_score, data.initial_critique, data.optimized_score,\n'
        '    JSON.stringify(data.changelog_explanation), applyBridge(data.final_prompt, ctx.req.bridge), data.framework_used,\n'
        '    result.provider, result.model, result.tokens, nowIso(), id);\n'
        '  const row = getOwned(db, id, userId);\n'
        '  reindex(db, row);\n'
      ), (
        'function saveOptimization(db: Db, userId: string, id: string, ctx: BuildCtx, result: Awaited<ReturnType<typeof optimize>>): OptimizationDTO {\n'
        '  const { data } = result;\n'
        "  db.run(`UPDATE optimizations SET status = 'ok', answers = ?, initial_score = ?, initial_critique = ?, optimized_score = ?, changelog = ?,\n"
        '    final_prompt = ?, framework_used = ?, provider = ?, model = ?, tokens_used = tokens_used + ?, updated_at = ? WHERE id = ?`,\n'
        '    JSON.stringify((ctx.answers ?? []).map(({ a }) => a)), data.initial_score ?? null, data.initial_critique, data.optimized_score ?? null,\n'
        '    JSON.stringify(data.changelog_explanation), applyBridge(data.final_prompt, ctx.req.bridge), data.framework_used,\n'
        '    result.provider, result.model, result.tokens, nowIso(), id);\n'
        '  const row = getOwned(db, id, userId);\n'
        '  reindex(db, row);\n'
      )),
      ((
        '    const best = item.compressed_prompt ? estimateTokens(item.compressed_prompt) : before;\n'
        '    const result = await engineJson(db, m.deps, buildCompressMessages(item.final_prompt), compressOutputSchema, { maxTokens: 4500 });\n'
        '    const candidate = applyBridge(result.data.compressed_prompt, item.options.bridge);\n'
        '    const after = estimateTokens(candidate);\n'
        '    const candidateVars = varsFor(item.workflow, candidate);\n'
        '    const sameVars = candidateVars.length === item.variables.length && item.variables.every((v) => candidateVars.includes(v));\n'
        '    const improved = sameVars && after < best;\n'
        '    if (improved) {\n'
        "      db.run('UPDATE optimizations SET compressed_prompt = ?, tokens_before = ?, tokens_after = ?, tokens_used = tokens_used + ?, updated_at = ? WHERE id = ?',\n"
      ), (
        '    const best = item.compressed_prompt ? estimateTokens(item.compressed_prompt) : before;\n'
        '    const result = await engineJson(db, m.deps, buildCompressMessages(item.final_prompt), compressOutputSchema, { maxTokens: 4500 });\n'
        '    const candidate = applyBridge(result.data.compressed_prompt, item.options.bridge);\n'
        '    const after = estimateTokens(candidate);\n'
        '    const current = getOwned(db, id, m.userId);\n'
        '    if (current.final_prompt !== item.final_prompt) {\n'
        "      throw new AppError(409, 'version_conflict', 'Промпт изменился во время сжатия. Повторите для новой версии.');\n"
        '    }\n'
        '    const candidateVars = varsFor(candidate);\n'
        '    const sameVars = candidateVars.length === item.variables.length && item.variables.every((v) => candidateVars.includes(v));\n'
        '    const improved = sameVars && after < best;\n'
        '    if (improved) {\n'
        "      db.run('UPDATE optimizations SET compressed_prompt = ?, tokens_before = ?, tokens_after = ?, tokens_used = tokens_used + ?, updated_at = ? WHERE id = ?',\n"
      )),
    ),
    'apps/server/src/routes.ts': (
      ((
        "import { z, ZodError } from 'zod';\n"
        "import { diffLines } from 'diff';\n"
        'import {\n'
        '  generateRequestSchema, templateInputSchema, generalizeOutputSchema, settingsSchema, systemIdSchema, optionsSchema,\n'
        '  extractVariables, validateTemplateVariables, substituteVariables, LIMITS,\n'
        '  type SystemId, type TemplateDTO, type GenerationDTO,\n'
        "} from '../../../shared/src/index.ts';\n"
        "import { config } from './config.ts';\n"
        "import { type Db, type Row, getSettings, setSettings, indexDoc, unindexDoc, searchDocs } from './db.ts';\n"
        "import { VibeError, type VibeClient } from './vibe.ts';\n"
        "import { resolveIdentity, rateLimit, type Identity } from './auth.ts';\n"
        "import { registerOptimizerRoutes } from './optimizer-routes.ts';\n"
        "import { AppError, uid, nowIso, jsonParse, log, extractJson } from './util.ts';\n"
        "import { runGeneration, regenerateResult, rowToGeneration, rowToResult, type GenEvent } from './generation.ts';\n"
        "import { getCurrentVersion, listVersions, skillToDto, rowToVersion, getVersionById } from './skills.ts';\n"
        "import { runManual, isRefreshBusy, type RefreshDeps } from './refresh.ts';\n"
      ), (
        "import { z, ZodError } from 'zod';\n"
        "import { diffLines } from 'diff';\n"
        'import {\n'
        '  generateRequestSchema, templateInputSchema, generalizeOutputSchema, settingsSchema, systemIdSchema, optionsSchema,\n'
        '  extractVariables, validateTemplateVariables, substituteVariables, promptIdSchema, LIMITS,\n'
        '  type SystemId, type TemplateDTO, type GenerationDTO,\n'
        "} from '../../../shared/src/index.ts';\n"
        "import { config } from './config.ts';\n"
        "import { type Db, type Row, getSettings, setSettings, indexDoc, unindexDoc, searchDocs } from './db.ts';\n"
        "import { VibeError, type VibeClient } from './vibe.ts';\n"
        "import { resolveIdentity, rateLimit, type Identity } from './auth.ts';\n"
        "import { registerOptimizerRoutes } from './optimizer-routes.ts';\n"
        "import { registerPromptFeatures, versionQuery } from './prompt-features.ts';\n"
        "import { appendPromptVersion, deletePromptVersions, listVersionsForPrompt } from './prompt-versions.ts';\n"
        "import { registerTeamRoutes } from './team-routes.ts';\n"
        "import { AppError, uid, nowIso, jsonParse, log, extractJson } from './util.ts';\n"
        "import { runGeneration, regenerateResult, rowToGeneration, rowToResult, type GenEvent } from './generation.ts';\n"
        "import { getCurrentVersion, listVersions, skillToDto, rowToVersion, getVersionById } from './skills.ts';\n"
        "import { runManual, isRefreshBusy, type RefreshDeps } from './refresh.ts';\n"
      )),
      ((
        '  const me = (req: FastifyRequest): Identity => req.identity!;\n'
        "  const admin = (req: FastifyRequest): Identity => { const i = me(req); if (!i.isAdmin) throw new AppError(403, 'admin_required', 'Требуются права администратора'); return i; };\n"
        '  const sysId = (v: unknown): SystemId => systemIdSchema.parse(v);\n'
        '  registerOptimizerRoutes(app, { db, vibe, me, admin });\n'
        '\n'
        '  // ---- SSE helper ----\n'
        '  function openSse(reply: FastifyReply, generationId?: string): { send: (e: GenEvent) => void; close: () => void } {\n'
        '    reply.hijack();\n'
      ), (
        '  const me = (req: FastifyRequest): Identity => req.identity!;\n'
        "  const admin = (req: FastifyRequest): Identity => { const i = me(req); if (!i.isAdmin) throw new AppError(403, 'admin_required', 'Требуются права администратора'); return i; };\n"
        '  const sysId = (v: unknown): SystemId => systemIdSchema.parse(v);\n'
        '  registerOptimizerRoutes(app, { db, vibe, me, admin });\n'
        '  registerPromptFeatures(app, db, { vibe }, me);\n'
        '  registerTeamRoutes(app, db, me);\n'
        '\n'
        '  // ---- SSE helper ----\n'
        '  function openSse(reply: FastifyReply, generationId?: string): { send: (e: GenEvent) => void; close: () => void } {\n'
        '    reply.hijack();\n'
      )),
      ((
        '    return { items: rows.map(rowToTemplate) };\n'
        '  });\n'
        "  app.post('/api/templates', async (req) => { const id = insertTemplate(me(req).userId, templateInputSchema.parse(req.body)); return rowToTemplate(db.get('SELECT * FROM templates WHERE id = ?', id)!); });\n"
        "  app.get('/api/templates/:id', async (req) => rowToTemplate(ownTemplate((req.params as any).id, me(req).userId)));\n"
        "  app.patch('/api/templates/:id', async (req) => {\n"
        '    const t = ownTemplate((req.params as any).id, me(req).userId);\n'
        "    if (t.is_seed || t.user_id !== me(req).userId) throw new AppError(403, 'seed_readonly', 'Стартовые шаблоны можно только дублировать');\n"
        '    const p = templateInputSchema.partial().parse(req.body);\n'
        '    const merged = { title: p.title ?? t.title, description: p.description ?? t.description, body: p.body ?? t.body, language: p.language ?? t.language,\n'
        '      default_systems: p.default_systems ?? jsonParse(t.default_systems, []), tags: p.tags ?? jsonParse(t.tags, []) };\n'
        "    const v = validateTemplateVariables(merged.body); if (!v.ok) throw new AppError(400, 'too_many_variables', v.error!);\n"
        "    db.run('UPDATE templates SET title = ?, description = ?, body = ?, language = ?, default_systems = ?, tags = ?, updated_at = ? WHERE id = ?',\n"
        '      merged.title, merged.description, merged.body, merged.language, JSON.stringify(merged.default_systems), JSON.stringify(merged.tags), nowIso(), t.id);\n'
        "    indexDoc(db, 'tpl', t.id, t.user_id, `${merged.title} ${merged.description} ${merged.body}`);\n"
        "    return rowToTemplate(db.get('SELECT * FROM templates WHERE id = ?', t.id)!);\n"
        '  });\n'
        "  app.delete('/api/templates/:id', async (req) => {\n"
        '    const t = ownTemplate((req.params as any).id, me(req).userId);\n'
        "    if (t.is_seed || t.user_id !== me(req).userId) throw new AppError(403, 'seed_readonly', 'Стартовые шаблоны нельзя удалить');\n"
        "    db.run('UPDATE templates SET deleted_at = ? WHERE id = ?', nowIso(), t.id); unindexDoc(db, 'tpl', t.id);\n"
        '    return { ok: true };\n'
        '  });\n'
        "  app.post('/api/templates/:id/duplicate', async (req) => {\n"
        '    const t = ownTemplate((req.params as any).id, me(req).userId);\n'
      ), (
        '    return { items: rows.map(rowToTemplate) };\n'
        '  });\n'
        "  app.post('/api/templates', async (req) => { const id = insertTemplate(me(req).userId, templateInputSchema.parse(req.body)); return rowToTemplate(db.get('SELECT * FROM templates WHERE id = ?', id)!); });\n"
        "  app.get('/api/templates/:id', async (req) => rowToTemplate(ownTemplate((req.params as any).id, me(req).userId)));\n"
        "  app.get('/api/templates/:id/versions', async (req) => {\n"
        '    const t = ownTemplate(promptIdSchema.parse(req.params).id, me(req).userId);\n'
        "    if (t.is_seed) throw new AppError(403, 'seed_readonly', 'Стартовый шаблон доступен только для чтения');\n"
        "    return listVersionsForPrompt(db, 'template', { id: t.id, body: t.body, created_at: t.created_at }, versionQuery.parse(req.query).before);\n"
        '  });\n'
        "  app.patch('/api/templates/:id', async (req) => {\n"
        '    const t = ownTemplate((req.params as any).id, me(req).userId);\n'
        "    if (t.is_seed || t.user_id !== me(req).userId) throw new AppError(403, 'seed_readonly', 'Стартовые шаблоны можно только дублировать');\n"
        '    const p = templateInputSchema.partial().extend({ expected_version: z.number().int().positive().optional() }).parse(req.body);\n'
        '    const merged = { title: p.title ?? t.title, description: p.description ?? t.description, body: p.body ?? t.body, language: p.language ?? t.language,\n'
        '      default_systems: p.default_systems ?? jsonParse(t.default_systems, []), tags: p.tags ?? jsonParse(t.tags, []) };\n'
        "    const v = validateTemplateVariables(merged.body); if (!v.ok) throw new AppError(400, 'too_many_variables', v.error!);\n"
        '    return db.tx(() => {\n'
        "      appendPromptVersion(db, 'template', { id: t.id, body: t.body, created_at: t.created_at }, merged.body, p.expected_version);\n"
        "      db.run('UPDATE templates SET title = ?, description = ?, body = ?, language = ?, default_systems = ?, tags = ?, updated_at = ? WHERE id = ?',\n"
        '        merged.title, merged.description, merged.body, merged.language, JSON.stringify(merged.default_systems), JSON.stringify(merged.tags), nowIso(), t.id);\n'
        "      indexDoc(db, 'tpl', t.id, t.user_id, `${merged.title} ${merged.description} ${merged.body}`);\n"
        "      return rowToTemplate(db.get('SELECT * FROM templates WHERE id = ?', t.id)!);\n"
        '    });\n'
        '  });\n'
        "  app.delete('/api/templates/:id', async (req) => {\n"
        '    const t = ownTemplate((req.params as any).id, me(req).userId);\n'
        "    if (t.is_seed || t.user_id !== me(req).userId) throw new AppError(403, 'seed_readonly', 'Стартовые шаблоны нельзя удалить');\n"
        '    db.tx(() => {\n'
        "      db.run('UPDATE templates SET deleted_at = ? WHERE id = ?', nowIso(), t.id);\n"
        "      unindexDoc(db, 'tpl', t.id);\n"
        "      deletePromptVersions(db, 'template', t.id);\n"
        '    });\n'
        '    return { ok: true };\n'
        '  });\n'
        "  app.post('/api/templates/:id/duplicate', async (req) => {\n"
        '    const t = ownTemplate((req.params as any).id, me(req).userId);\n'
      )),
      ((
        "  app.post('/api/templates/:id/use', async (req) => {\n"
        '    const t = ownTemplate((req.params as any).id, me(req).userId);\n'
        '    const { values } = z.object({ values: z.record(z.string(), z.string().max(8000)) }).parse(req.body);\n'
        '    const text = substituteVariables(t.body, values);\n'
        '    const missing = extractVariables(text);\n'
        "    db.run('UPDATE templates SET usage_count = usage_count + 1 WHERE id = ?', t.id);\n"
        '    return { text, missing, language: t.language, systems: jsonParse(t.default_systems, []) };\n'
        '  });\n'
        "  app.post('/api/templates/generalize', async (req) => {\n"
      ), (
        "  app.post('/api/templates/:id/use', async (req) => {\n"
        '    const t = ownTemplate((req.params as any).id, me(req).userId);\n'
        '    const { values } = z.object({ values: z.record(z.string(), z.string().max(8000)) }).parse(req.body);\n'
        '    const text = substituteVariables(t.body, values);\n'
        '    const missing = extractVariables(t.body).filter((name) => !Object.hasOwn(values, name) || !values[name]?.trim());\n'
        "    db.run('UPDATE templates SET usage_count = usage_count + 1 WHERE id = ?', t.id);\n"
        '    return { text, missing, language: t.language, systems: jsonParse(t.default_systems, []) };\n'
        '  });\n'
        "  app.post('/api/templates/generalize', async (req) => {\n"
      )),
    ),
    'apps/web/src/App.tsx': (
      ((
        "import { t } from './strings.ru.ts';\n"
        "import { get, onWake, ApiError } from './api.ts';\n"
        "import { AppCtx, type AgentStatus, type Me, type Prefill, type Screen, type AppState } from './context.tsx';\n"
        "import { ToastProvider, Spinner, Modal } from './ui.tsx';\n"
        "import { GeneratorScreen } from './screens/Generator.tsx';\n"
        "import { HistoryScreen } from './screens/History.tsx';\n"
        "import { TemplatesScreen } from './screens/Templates.tsx';\n"
        "import { FavoritesScreen } from './screens/Favorites.tsx';\n"
      ), (
        "import { t } from './strings.ru.ts';\n"
        "import { get, onWake, ApiError } from './api.ts';\n"
        "import { AppCtx, type AgentStatus, type Me, type Prefill, type Screen, type AppState } from './context.tsx';\n"
        "import { ToastProvider, Spinner, Modal } from './ui.tsx';\n"
        "import { HomeScreen } from './screens/Home.tsx';\n"
        "import { GeneratorScreen } from './screens/Generator.tsx';\n"
        "import { HistoryScreen } from './screens/History.tsx';\n"
        "import { TemplatesScreen } from './screens/Templates.tsx';\n"
        "import { FavoritesScreen } from './screens/Favorites.tsx';\n"
      )),
      ((
        "import { OptimizerScreen } from './screens/Optimizer.tsx';\n"
        "import { LibraryScreen } from './screens/Library.tsx';\n"
        '\n'
        'interface NavDef { id: Screen; label: string; icon: typeof Wand2; adminOnly?: boolean }\n'
        "const WORK: NavDef[] = [{ id: 'optimizer', label: t.nav.optimizer, icon: Sparkles }, { id: 'library', label: t.nav.library, icon: Library }, { id: 'history', label: t.nav.history, icon: History }, { id: 'favorites', label: t.nav.favorites, icon: Star }, { id: 'templates', label: t.nav.templates, icon: LayoutTemplate }];\n"
        "const SYSTEM: NavDef[] = [{ id: 'skills', label: t.nav.skills, icon: Cpu }, { id: 'reports', label: t.nav.reports, icon: ScrollText }, { id: 'analytics', label: t.analytics.nav, icon: BarChart3, adminOnly: true }];\n"
        "const NEW_PROMPT: NavDef = { id: 'generator', label: t.nav.new, icon: Plus };\n"
        "const SETTINGS: NavDef = { id: 'settings', label: t.nav.settings, icon: Cog };\n"
        "const ALL_SCREENS: Screen[] = ['generator', 'optimizer', 'library', 'history', 'favorites', 'templates', 'skills', 'reports', 'analytics', 'settings'];\n"
        "const parseHash = (): Screen => { const s = location.hash.replace('#/', '') as Screen; return ALL_SCREENS.includes(s) ? s : 'generator'; };\n"
        'const store = { get: (k: string) => { try { return localStorage.getItem(k); } catch { return null; } }, set: (k: string, v: string) => { try { localStorage.setItem(k, v); } catch { /* storage may be blocked in iframes */ } } };\n'
        '\n'
        'const themeFromStorage = () => {\n'
        "  const theme = settingsSchema.shape.theme.safeParse(store.get('theme'));\n"
      ), (
        "import { OptimizerScreen } from './screens/Optimizer.tsx';\n"
        "import { LibraryScreen } from './screens/Library.tsx';\n"
        '\n'
        'interface NavDef { id: Screen; label: string; icon: typeof Wand2; adminOnly?: boolean }\n'
        "const WORK: NavDef[] = [{ id: 'optimizer', label: t.nav.optimizer, icon: Sparkles }, { id: 'library', label: t.nav.library, icon: Library }, { id: 'history', label: t.nav.history, icon: History }, { id: 'generator', label: t.nav.generator, icon: Wand2 }, { id: 'favorites', label: t.nav.favorites, icon: Star }, { id: 'templates', label: t.nav.templates, icon: LayoutTemplate }];\n"
        "const SYSTEM: NavDef[] = [{ id: 'skills', label: t.nav.skills, icon: Cpu }, { id: 'reports', label: t.nav.reports, icon: ScrollText }, { id: 'analytics', label: t.analytics.nav, icon: BarChart3, adminOnly: true }];\n"
        "const NEW_PROMPT: NavDef = { id: 'home', label: t.nav.new, icon: Plus };\n"
        "const SETTINGS: NavDef = { id: 'settings', label: t.nav.settings, icon: Cog };\n"
        "const ALL_SCREENS: Screen[] = ['home', 'generator', 'optimizer', 'library', 'history', 'favorites', 'templates', 'skills', 'reports', 'analytics', 'settings'];\n"
        "const parseHash = (): Screen => { const s = location.hash.replace('#/', '') as Screen; return ALL_SCREENS.includes(s) ? s : 'home'; };\n"
        'const store = { get: (k: string) => { try { return localStorage.getItem(k); } catch { return null; } }, set: (k: string, v: string) => { try { localStorage.setItem(k, v); } catch { /* storage may be blocked in iframes */ } } };\n'
        '\n'
        'const themeFromStorage = () => {\n'
        "  const theme = settingsSchema.shape.theme.safeParse(store.get('theme'));\n"
      )),
      ((
        '    return () => ro.disconnect();\n'
        '  }, [authErr]);\n'
        '  const isAdmin = !!me?.is_admin; const meLoaded = me !== null;\n'
        "  useEffect(() => { const h = () => { const s = parseHash(); if (s === 'analytics' && !isAdmin) return; setScreen(s); }; window.addEventListener('hashchange', h); return () => window.removeEventListener('hashchange', h); }, [isAdmin]);\n"
        "  useEffect(() => { if (meLoaded && !isAdmin && screen === 'analytics') go('generator'); }, [meLoaded, isAdmin, screen, go]); // admin-only section: non-admins fall back to the generator\n"
        '\n'
        '  const state: AppState = {\n'
        '    me, settings, agent, go, prefill, reload, theme,\n'
        "    setPrefill: (p, doGo = true) => { setPrefillState({ ...p, nonce: Date.now() }); if (doGo) go('generator'); },\n"
      ), (
        '    return () => ro.disconnect();\n'
        '  }, [authErr]);\n'
        '  const isAdmin = !!me?.is_admin; const meLoaded = me !== null;\n'
        "  useEffect(() => { const h = () => { const s = parseHash(); if (s === 'analytics' && !isAdmin) return; setScreen(s); }; window.addEventListener('hashchange', h); return () => window.removeEventListener('hashchange', h); }, [isAdmin]);\n"
        "  useEffect(() => { if (meLoaded && !isAdmin && screen === 'analytics') go('home'); }, [meLoaded, isAdmin, screen, go]); // admin-only section: non-admins fall back to the generator\n"
        '\n'
        '  const state: AppState = {\n'
        '    me, settings, agent, go, prefill, reload, theme,\n'
        "    setPrefill: (p, doGo = true) => { setPrefillState({ ...p, nonce: Date.now() }); if (doGo) go('generator'); },\n"
      )),
      ((
        "  const collapsed = !compact && (sidebarPref ? sidebarPref === 'collapsed' : bodyW < 1024);\n"
        "  const toggleSidebar = () => { const next = collapsed ? 'expanded' : 'collapsed'; setSidebarPref(next); store.set('sidebar', next); };\n"
        '  const themeLabel = `${t.nav.themeLabel}: ${t.settings.theme[theme]}`; const userName = me?.name ?? t.nav.userFallback;\n'
        "  const cycleTheme = () => state.setTheme(theme === 'dark' ? 'light' : theme === 'light' ? 'system' : 'dark');\n"
        '  const navButton = (n: NavDef, extra = \'\') => <button key={n.id} className={`nav-item ${extra} ${screen === n.id ? \'on\' : \'\'}`} onClick={() => go(n.id)} aria-current={screen === n.id ? \'page\' : undefined} aria-label={collapsed ? n.label : undefined} title={n.label}><n.icon size={n.id === \'generator\' ? 16 : 18} aria-hidden /><span className="nav-label">{n.label}</span></button>;\n'
        '\n'
        '  if (authErr) return <ToastProvider><div ref={shellRef} style={{ padding: \'var(--space-10)\' }}><div className="empty surface"><Logo /><h3 style={{ marginTop: \'var(--space-3)\' }}>{t.appName}</h3><p className="tx2">{t.auth.required}</p></div></div></ToastProvider>;\n'
        '\n'
        '  return (\n'
      ), (
        "  const collapsed = !compact && (sidebarPref ? sidebarPref === 'collapsed' : bodyW < 1024);\n"
        "  const toggleSidebar = () => { const next = collapsed ? 'expanded' : 'collapsed'; setSidebarPref(next); store.set('sidebar', next); };\n"
        '  const themeLabel = `${t.nav.themeLabel}: ${t.settings.theme[theme]}`; const userName = me?.name ?? t.nav.userFallback;\n'
        "  const cycleTheme = () => state.setTheme(theme === 'dark' ? 'light' : theme === 'light' ? 'system' : 'dark');\n"
        '  const navButton = (n: NavDef, extra = \'\') => <button key={n.id} className={`nav-item ${extra} ${screen === n.id ? \'on\' : \'\'}`} onClick={() => go(n.id)} aria-current={screen === n.id ? \'page\' : undefined} aria-label={collapsed ? n.label : undefined} title={n.label}><n.icon size={n.id === \'home\' ? 16 : 18} aria-hidden /><span className="nav-label">{n.label}</span></button>;\n'
        '\n'
        '  if (authErr) return <ToastProvider><div ref={shellRef} style={{ padding: \'var(--space-10)\' }}><div className="empty surface"><Logo /><h3 style={{ marginTop: \'var(--space-3)\' }}>{t.appName}</h3><p className="tx2">{t.auth.required}</p></div></div></ToastProvider>;\n'
        '\n'
        '  return (\n'
      )),
      ((
        '          {moreNav.length > 0 && <button className="nav-item" onClick={() => setMoreOpen(true)} aria-label={t.nav.more}><MoreHorizontal size={20} aria-hidden /><span>{t.nav.more}</span></button>}\n'
        '        </nav>}\n'
        '          <main className="content">\n'
        '            {agent?.paused_reason && <div className="banner err" role="alert"><span className="grow">{agent.paused_reason.startsWith(\'quota\') ? t.banner.quota : t.banner.paused}</span></div>}\n'
        '            {agent?.scheduler_mode === \'lazy\' && <div className="banner warn"><span className="grow">{t.banner.fallback}</span></div>}\n'
        '            <Boundary key={screen}>\n'
        "              {screen === 'generator' && <GeneratorScreen />}{screen === 'history' && <HistoryScreen />}{screen === 'templates' && <TemplatesScreen />}\n"
        "              {screen === 'favorites' && <FavoritesScreen />}{screen === 'skills' && <SkillsScreen />}{screen === 'reports' && <ReportsScreen />}{screen === 'settings' && <SettingsScreen />}\n"
        "              {screen === 'optimizer' && <OptimizerScreen />}{screen === 'library' && <LibraryScreen />}\n"
        "              {screen === 'analytics' && (meLoaded ? <AnalyticsScreen /> : <Spinner />)}\n"
        '            </Boundary>\n'
      ), (
        '          {moreNav.length > 0 && <button className="nav-item" onClick={() => setMoreOpen(true)} aria-label={t.nav.more}><MoreHorizontal size={20} aria-hidden /><span>{t.nav.more}</span></button>}\n'
        '        </nav>}\n'
        '          <main className="content">\n'
        '            {agent?.paused_reason && <div className="banner err" role="alert"><span className="grow">{agent.paused_reason.startsWith(\'quota\') ? t.banner.quota : t.banner.paused}</span></div>}\n'
        '            {screen !== \'home\' && agent?.scheduler_mode === \'lazy\' && <div className="banner warn"><span className="grow">{t.banner.fallback}</span></div>}\n'
        '            <Boundary key={screen}>\n'
        "              {screen === 'home' && <HomeScreen />}{screen === 'generator' && <GeneratorScreen />}{screen === 'history' && <HistoryScreen />}{screen === 'templates' && <TemplatesScreen />}\n"
        "              {screen === 'favorites' && <FavoritesScreen />}{screen === 'skills' && <SkillsScreen />}{screen === 'reports' && <ReportsScreen />}{screen === 'settings' && <SettingsScreen />}\n"
        "              {screen === 'optimizer' && <OptimizerScreen />}{screen === 'library' && <LibraryScreen />}\n"
        "              {screen === 'analytics' && (meLoaded ? <AnalyticsScreen /> : <Spinner />)}\n"
        '            </Boundary>\n'
      )),
    ),
    'apps/web/src/api.ts': (
      ((
        "export const put = <T>(p: string, body: unknown) => request<T>(p, { method: 'PUT', body });\n"
        "export const patch = <T>(p: string, body: unknown) => request<T>(p, { method: 'PATCH', body });\n"
        "export const del = <T>(p: string) => request<T>(p, { method: 'DELETE' });\n"
        '\n'
        '// ---- generation transport: SSE over fetch, with polling fallback ----\n'
        'export interface GenHandlers {\n'
        '  onStart?: (id: string) => void; onIntent?: () => void; onCardStart?: (s: SystemId) => void; onCard?: (r: ResultDTO) => void; onCardError?: (s: SystemId, e: string, r?: ResultDTO) => void;\n'
        '  onQuestions?: (list: string[], id: string) => void; onDone?: (id: string, status: string) => void; onFallback?: () => void; onError?: (e: ApiError) => void;\n'
      ), (
        "export const put = <T>(p: string, body: unknown) => request<T>(p, { method: 'PUT', body });\n"
        "export const patch = <T>(p: string, body: unknown) => request<T>(p, { method: 'PATCH', body });\n"
        "export const del = <T>(p: string) => request<T>(p, { method: 'DELETE' });\n"
        '\n'
        'async function* sseFrames(body: ReadableStream<Uint8Array>) {\n'
        '  const reader = body.getReader();\n'
        '  const decoder = new TextDecoder();\n'
        "  let buffer = '';\n"
        '  try {\n'
        '    for (;;) {\n'
        '      const { value, done } = await reader.read();\n'
        '      if (done) break;\n'
        '      buffer += decoder.decode(value, { stream: true });\n'
        '      let end: number;\n'
        "      while ((end = buffer.indexOf('\\n\\n')) >= 0) {\n"
        '        const frame = buffer.slice(0, end);\n'
        '        buffer = buffer.slice(end + 2);\n'
        '        const type = /^event: (.+)$/m.exec(frame)?.[1];\n'
        '        const data = /^data: (.+)$/m.exec(frame)?.[1];\n'
        '        if (type && data) yield { type, data };\n'
        '      }\n'
        '    }\n'
        '  } finally {\n'
        '    await reader.cancel().catch(() => {});\n'
        '    reader.releaseLock();\n'
        '  }\n'
        '}\n'
        '\n'
        'export async function postPrompt<T>(path: string, body: unknown = {}): Promise<T> {\n'
        '  let res: Response;\n'
        '  try {\n'
        "    res = await fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' }, body: JSON.stringify(body) });\n"
        "  } catch { throw new ApiError(0, 'network', t.common.error); }\n"
        '  if (!res.ok) {\n'
        '    const data = await res.json().catch(() => null);\n'
        "    throw new ApiError(res.status, data?.error?.code ?? 'error', data?.error?.message ?? t.common.error,\n"
        "      Number(res.headers.get('retry-after')) || undefined);\n"
        '  }\n'
        "  if (!res.body || !res.headers.get('content-type')?.includes('text/event-stream')) {\n"
        '    const data = await res.json().catch(() => null);\n'
        "    if (data === null) throw new ApiError(0, 'stream', t.prompt.streamInterrupted);\n"
        '    return data as T;\n'
        '  }\n'
        '  try {\n'
        '    for await (const frame of sseFrames(res.body)) {\n'
        "      if (frame.type === 'result') return JSON.parse(frame.data) as T;\n"
        "      if (frame.type === 'failure') {\n"
        '        const error = JSON.parse(frame.data);\n'
        '        throw new ApiError(error.status, error.code, error.message, error.retryAfter);\n'
        '      }\n'
        '    }\n'
        '  } catch (error) {\n'
        '    if (error instanceof ApiError) throw error;\n'
        '  }\n'
        "  throw new ApiError(0, 'stream', t.prompt.streamInterrupted);\n"
        '}\n'
        '\n'
        '// ---- generation transport: SSE over fetch, with polling fallback ----\n'
        'export interface GenHandlers {\n'
        '  onStart?: (id: string) => void; onIntent?: () => void; onCardStart?: (s: SystemId) => void; onCard?: (r: ResultDTO) => void; onCardError?: (s: SystemId, e: string, r?: ResultDTO) => void;\n'
        '  onQuestions?: (list: string[], id: string) => void; onDone?: (id: string, status: string) => void; onFallback?: () => void; onError?: (e: ApiError) => void;\n'
      )),
      ((
        '  }\n'
        "  genId = res.headers.get('x-generation-id') ?? '';\n"
        '  // If the proxy buffers the stream, no events arrive: fall back to polling after 5 seconds.\n'
        '  const watchdog = setTimeout(() => { if (!gotEvent && !finished) void poll(); }, 5000);\n'
        "  const reader = res.body.getReader(); const dec = new TextDecoder(); let buf = '';\n"
        '  try {\n'
        '    for (;;) {\n'
        '      const { value, done } = await reader.read(); if (done) break;\n'
        '      buf += dec.decode(value, { stream: true }); let i: number;\n'
        "      while ((i = buf.indexOf('\\n\\n')) >= 0) {\n"
        '        const frame = buf.slice(0, i); buf = buf.slice(i + 2);\n'
        '        const type = /^event: (.+)$/m.exec(frame)?.[1]; const data = /^data: (.+)$/m.exec(frame)?.[1];\n'
        '        if (type && data) { try { handle(type, JSON.parse(data)); } catch { /* ignore malformed frame */ } }\n'
        '      }\n'
        '    }\n'
        '  } catch { /* stream broke: fall back to polling below */ }\n'
        '  clearTimeout(watchdog);\n'
        "  if (!finished) { if (genId) await poll(); else h.onError?.(new ApiError(0, 'stream', t.common.error)); }\n"
      ), (
        '  }\n'
        "  genId = res.headers.get('x-generation-id') ?? '';\n"
        '  // If the proxy buffers the stream, no events arrive: fall back to polling after 5 seconds.\n'
        '  const watchdog = setTimeout(() => { if (!gotEvent && !finished) void poll(); }, 5000);\n'
        '  try {\n'
        '    for await (const frame of sseFrames(res.body)) {\n'
        '      if (finished) break;\n'
        '      try { handle(frame.type, JSON.parse(frame.data)); } catch { /* ignore malformed frame */ }\n'
        '    }\n'
        '  } catch { /* stream broke: fall back to polling below */ }\n'
        '  clearTimeout(watchdog);\n'
        "  if (!finished) { if (genId) await poll(); else h.onError?.(new ApiError(0, 'stream', t.common.error)); }\n"
      )),
    ),
    'apps/web/src/components/EngineSettings.tsx': (
      ((
        "import { useEffect, useState } from 'react';\n"
        "import { DEFAULT_ENGINE_MODEL, PROVIDERS, supportsCustomTemperature, type EngineView, type Provider } from '../../../../shared/src/index.ts';\n"
        "import { t } from '../strings.ru.ts';\n"
        "import { get, post, put, ApiError } from '../api.ts';\n"
        "import { Spinner, useToast } from '../ui.tsx';\n"
        '\n'
        "const CUSTOM = '__custom__';\n"
        'export function EngineSettings({ admin }: { admin: boolean }) {\n'
      ), (
        "import { useEffect, useState } from 'react';\n"
        "import { DEFAULT_ENGINE_MODEL, PROVIDERS, supportsCustomTemperature, type EngineView, type Provider } from '../../../../shared/src/index.ts';\n"
        "import { t } from '../strings.ru.ts';\n"
        "import { get, postPrompt, put, ApiError } from '../api.ts';\n"
        "import { Spinner, useToast } from '../ui.tsx';\n"
        '\n'
        "const CUSTOM = '__custom__';\n"
        'export function EngineSettings({ admin }: { admin: boolean }) {\n'
      )),
      ((
        '    setBusy(true);\n'
        "    try { apply(await put<EngineView>('/api/optimizer/engine', { provider, model, base_url: baseUrl, temperature: temp, ...(clearKey ? { api_key: '' } : key ? { api_key: key } : {}) })); toast(t.settings.saved, 'ok'); }\n"
        '    catch (e) { fail(e); } finally { setBusy(false); }\n'
        '  };\n'
        "  const test = async () => { setBusy(true); try { const r = await post<{ latency_ms: number; model: string }>('/api/optimizer/engine/test'); toast(`${t.engine.testOk}: ${r.model}, ${r.latency_ms} ${t.engine.ms}`, 'ok'); } catch (e) { fail(e); } finally { setBusy(false); } };\n"
        '  return (\n'
        '    <section className="surface card col" aria-label={t.engine.title}>\n'
        '      <h3>{t.engine.title}</h3>\n'
        '      {!admin && <div className="banner warn">{t.engine.adminOnly}</div>}\n'
      ), (
        '    setBusy(true);\n'
        "    try { apply(await put<EngineView>('/api/optimizer/engine', { provider, model, base_url: baseUrl, temperature: temp, ...(clearKey ? { api_key: '' } : key ? { api_key: key } : {}) })); toast(t.settings.saved, 'ok'); }\n"
        '    catch (e) { fail(e); } finally { setBusy(false); }\n'
        '  };\n'
        "  const test = async () => { setBusy(true); try { const r = await postPrompt<{ latency_ms: number; model: string }>('/api/optimizer/engine/test'); toast(`${t.engine.testOk}: ${r.model}, ${r.latency_ms} ${t.engine.ms}`, 'ok'); } catch (e) { fail(e); } finally { setBusy(false); } };\n"
        '  return (\n'
        '    <section className="surface card col" aria-label={t.engine.title}>\n'
        '      <h3>{t.engine.title}</h3>\n'
        '      {!admin && <div className="banner warn">{t.engine.adminOnly}</div>}\n'
      )),
    ),
    'apps/web/src/components/OptimizationView.tsx': (
      ((
        "import { useMemo, useState } from 'react';\n"
        "import { Minimize2 } from 'lucide-react';\n"
        "import { estimateTokens, OPT_LIMITS, substituteBracketVars, type FolderDTO, type OptimizationDTO } from '../../../../shared/src/index.ts';\n"
        "import { t } from '../strings.ru.ts';\n"
        "import { patch, post, ApiError } from '../api.ts';\n"
        "import { CopyButton, Spinner, StarButton, useToast } from '../ui.tsx';\n"
        '\n'
        'type Compressed = OptimizationDTO & { no_gain?: boolean; saved_pct?: number };\n'
        '\n'
        'const ScoreBar = ({ label, value }: { label: string; value: number | null }) => (\n'
        '  <div className="score-field">\n'
        '    <div className="row spread small"><span className="tx2">{label}</span><strong className="mono">{value === null ? \'—\' : value.toFixed(1)}/10</strong></div>\n'
        '    <div role="img" aria-label={`${label}: ${value ?? 0} / 10`} style={{ height: \'var(--space-2)\', borderRadius: \'var(--radius-full)\', background: \'var(--color-surface-secondary)\', border: \'1px solid var(--color-border)\', marginTop: \'var(--space-1)\' }}>\n'
        "      <div style={{ width: `${Math.round(((value ?? 0) / 10) * 100)}%`, height: '100%', borderRadius: 'var(--radius-full)', background: 'var(--color-accent)' }} />\n"
        '    </div>\n'
        '  </div>\n'
        ');\n'
        '\n'
        'export function OptimizationView({ item, folders, onChange }: { item: OptimizationDTO; folders: FolderDTO[]; onChange: (i: OptimizationDTO) => void }) {\n'
        '  const toast = useToast();\n'
        '  const [values, setValues] = useState<Record<string, string>>(item.var_values);\n'
        "  const [busy, setBusy] = useState(false); const [view, setView] = useState<'full' | 'compressed'>(item.compressed_prompt ? 'compressed' : 'full');\n"
        "  const [note, setNote] = useState<string>(''); const [tags, setTags] = useState(item.tags.join(', '));\n"
        "  const base = view === 'compressed' && item.compressed_prompt ? item.compressed_prompt : item.final_prompt;\n"
        '  const master = useMemo(() => substituteBracketVars(base, values), [base, values]);\n'
        "  const fail = (e: unknown) => toast((e as ApiError).message ?? t.common.error, 'err');\n"
        '  const save = async (body: Record<string, unknown>) => { try { onChange(await patch<OptimizationDTO>(`/api/optimizer/items/${item.id}`, body)); } catch (e) { fail(e); } };\n'
        '  const compress = async () => {\n'
        '    setBusy(true);\n'
        '    try {\n'
        '      const r = await post<Compressed>(`/api/optimizer/items/${item.id}/compress`); onChange(r);\n'
        "      setNote(r.no_gain ? t.opt.noGain : t.opt.compressed.replace('{a}', String(r.tokens_before)).replace('{b}', String(r.tokens_after)).replace('{p}', String(r.saved_pct)));\n"
        "      if (!r.no_gain) setView('compressed');\n"
        '    } catch (e) { fail(e); } finally { setBusy(false); }\n'
        '  };\n'
        '  return (\n'
        '    <div className="col">\n'
        '      <div className="surface card col" aria-label={t.opt.optimized}>\n'
        '        <div className="form-grid"><ScoreBar label={t.opt.initial} value={item.initial_score} /><ScoreBar label={t.opt.optimized} value={item.optimized_score} /></div>\n'
        '        {item.initial_critique && <p className="small tx2" style={{ margin: 0 }}>{item.initial_critique}</p>}\n'
        '        <p className="small tx3" style={{ margin: 0 }}>{t.opt.scoreNote}{item.framework_used ? ` · ${t.opt.framework}: ${item.framework_used}` : \'\'}</p>\n'
        '      </div>\n'
        '      <div className="surface card col">\n'
        '        <div className="row spread wrap">\n'
        '          <h3>{t.opt.finalPrompt}</h3>\n'
        '          <div className="row wrap">\n'
        '            {item.compressed_prompt && <div className="seg" role="group" aria-label={t.opt.finalPrompt}>\n'
        "              <button className={view === 'full' ? 'on' : ''} aria-pressed={view === 'full'} onClick={() => setView('full')}>{t.opt.showOriginal}</button>\n"
        "              <button className={view === 'compressed' ? 'on' : ''} aria-pressed={view === 'compressed'} onClick={() => setView('compressed')}>{t.opt.showCompressed}</button></div>}\n"
        '            <StarButton on={item.is_favorite} onClick={() => save({ is_favorite: !item.is_favorite })} />\n'
        '            <CopyButton text={master} primary />\n'
        '          </div>\n'
        '        </div>\n'
        '        <div className="prompt-box" tabIndex={0} aria-label={t.opt.finalPrompt}>{master}</div>\n'
        '        <div className="row wrap">\n'
        '          <button className="btn" onClick={compress} disabled={busy}>{busy ? <Spinner /> : <Minimize2 size={15} aria-hidden />}{busy ? t.opt.compressing : t.opt.compress}</button>\n'
        '          <span className="small tx3 mono">≈ {estimateTokens(master)} tok</span>\n'
        '          {note && <span className="small tx2" role="status">{note}</span>}\n'
        '        </div>\n'
        '      </div>\n'
        '      {item.variables.length > 0 && (\n'
        '        <div className="surface card col">\n'
        '          <h3>{t.opt.variables}</h3><p className="small tx2" style={{ margin: 0 }}>{t.opt.variablesHint}</p>\n'
        '          <div className="grid-cards">\n'
        '            {item.variables.map((v) => <div key={v}><label className="label" htmlFor={`var-${v}`}>{v}</label>\n'
        '              <input id={`var-${v}`} className="field" maxLength={OPT_LIMITS.variableValue} value={values[v] ?? \'\'} onChange={(e) => setValues({ ...values, [v]: e.target.value })} onBlur={() => { if (JSON.stringify(values) !== JSON.stringify(item.var_values)) void save({ var_values: values }); }} /></div>)}\n'
        '          </div>\n'
        '        </div>\n'
        '      )}\n'
        '      {item.changelog_explanation.length > 0 && (\n'
        '        <div className="surface card col"><h3>{t.opt.changelog}</h3><ul style={{ margin: 0, paddingLeft: \'var(--space-5)\' }}>{item.changelog_explanation.map((c, i) => <li key={i} className="small" style={{ marginBottom: \'var(--space-1)\' }}>{c}</li>)}</ul></div>\n'
        '      )}\n'
        '      <div className="surface card form-grid">\n'
        '        <div><label className="label" htmlFor={`folder-${item.id}`}>{t.opt.folder}</label>\n'
        '          <select id={`folder-${item.id}`} className="field" value={item.folder_id ?? \'\'} onChange={(e) => save({ folder_id: e.target.value || null })}>\n'
        '            <option value="">{t.opt.noFolder}</option>{folders.map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}</select></div>\n'
        '        <div className="grow"><label className="label" htmlFor={`tags-${item.id}`}>{t.opt.tags}</label>\n'
        '          <input id={`tags-${item.id}`} className="field" value={tags} onChange={(e) => setTags(e.target.value)} onBlur={() => { const list = tags.split(\',\').map((x) => x.trim()).filter(Boolean).slice(0, 8); if (JSON.stringify(list) !== JSON.stringify(item.tags)) void save({ tags: list }); }} /></div>\n'
        '        <span className="small tx3">{t.opt.engine}: <span className="mono">{item.model || \'—\'}</span></span>\n'
        '      </div>\n'
        '    </div>\n'
        '  );\n'
        '}\n'
      ), (
        "import { useMemo, useState } from 'react';\n"
        "import { diffWordsWithSpace } from 'diff';\n"
        "import { Minimize2 } from 'lucide-react';\n"
        "import { estimateTokens, fillPromptVariables, type FolderDTO, type OptimizationDTO } from '../../../../shared/src/index.ts';\n"
        "import { t } from '../strings.ru.ts';\n"
        "import { patch, postPrompt, put } from '../api.ts';\n"
        "import { Seg, Spinner, StarButton, useToast } from '../ui.tsx';\n"
        "import { PromptActions } from './PromptActions.tsx';\n"
        "import { PromptChecklist, PromptFields } from './PromptFields.tsx';\n"
        "import { PromptVersionEditor } from './PromptVersionEditor.tsx';\n"
        "import { PublishPrompt } from './PublishPrompt.tsx';\n"
        '\n'
        'type Compressed = OptimizationDTO & { no_gain: boolean; saved_pct: number };\n'
        "type View = 'original' | 'compressed' | 'diff';\n"
        '\n'
        'function PromptDiff({ original, compressed }: { original: string; compressed: string }) {\n'
        '  const parts = useMemo(() => diffWordsWithSpace(original, compressed, { timeout: 150 }), [original, compressed]);\n'
        '  return (\n'
        '    <div className="col">\n'
        '      <p className="small tx2">{t.prompt.diffHint}</p>\n'
        '      <div className="prompt-box prompt-diff" tabIndex={0} aria-label={t.prompt.showDiff}>\n'
        "        {!parts ? <><strong>{t.opt.showOriginal}</strong>{'\\n'}<del>{original}</del>{'\\n\\n'}\n"
        "          <strong>{t.opt.showCompressed}</strong>{'\\n'}<ins>{compressed}</ins></> : parts.map((part, index) =>\n"
        '          part.removed ? <del key={index}>{part.value}</del> : part.added ? <ins key={index}>{part.value}</ins> : <span key={index}>{part.value}</span>)}\n'
        '      </div>\n'
        '    </div>\n'
        '  );\n'
        '}\n'
        '\n'
        'export function OptimizationView({ item, folders, onChange }: { item: OptimizationDTO; folders: FolderDTO[]; onChange: (i: OptimizationDTO) => void }) {\n'
        '  const toast = useToast();\n'
        '  const [values, setValues] = useState<Record<string, string>>(item.var_values);\n'
        "  const [tags, setTags] = useState(item.tags.join(', '));\n"
        "  const [view, setView] = useState<View>(item.compressed_prompt ? 'compressed' : 'original');\n"
        '  const [compressing, setCompressing] = useState(false);\n'
        "  const [note, setNote] = useState('');\n"
        "  const [editor, setEditor] = useState<'versions' | 'publish' | null>(null);\n"
        '  const [savedValues, setSavedValues] = useState(item.var_values);\n'
        '  const valuesDirty = values !== savedValues;\n'
        '  const [saving, setSaving] = useState(false);\n'
        '  const url = `/api/optimizer/items/${item.id}`;\n'
        '  const original = fillPromptVariables(item.final_prompt, values);\n'
        "  const compressed = item.compressed_prompt ? fillPromptVariables(item.compressed_prompt, values) : '';\n"
        "  const prompt = view === 'compressed' && compressed ? compressed : original;\n"
        "  const fail = (error: unknown) => toast(error instanceof Error ? error.message : t.common.error, 'err');\n"
        '\n'
        '  const save = async (body: Record<string, unknown>) => {\n'
        '    if (saving || compressing) return false;\n'
        '    setSaving(true);\n'
        '    try { onChange(await patch<OptimizationDTO>(url, body)); return true; }\n'
        '    catch (error) { fail(error); return false; }\n'
        '    finally { setSaving(false); }\n'
        '  };\n'
        '  const saveValues = async () => {\n'
        '    if (await save({ var_values: values })) setSavedValues(values);\n'
        '  };\n'
        '  const compress = async () => {\n'
        '    setCompressing(true);\n'
        "    setNote('');\n"
        '    try {\n'
        '      const result = await postPrompt<Compressed>(`${url}/compress`);\n'
        '      onChange(result);\n'
        "      setNote(result.no_gain ? t.opt.noGain : t.opt.compressed.replace('{a}', String(result.tokens_before)).replace('{b}', String(result.tokens_after)).replace('{p}', String(result.saved_pct)));\n"
        "      if (!result.no_gain) setView('compressed');\n"
        '    } catch (error) { fail(error); }\n'
        '    finally { setCompressing(false); }\n'
        '  };\n'
        '  const saveTags = () => {\n'
        "    const list = tags.split(',').map((tag) => tag.trim()).filter(Boolean).slice(0, 8);\n"
        '    if (JSON.stringify(list) !== JSON.stringify(item.tags)) void save({ tags: list });\n'
        '  };\n'
        '\n'
        '  return (\n'
        '    <section className="surface card col prompt-result" aria-label={t.opt.finalPrompt}>\n'
        '      <div className="row spread wrap"><h2>{t.opt.finalPrompt}</h2>\n'
        '        <StarButton on={item.is_favorite} onClick={() => { void save({ is_favorite: !item.is_favorite }); }} />\n'
        '      </div>\n'
        '      <PromptFields names={item.variables} values={values} onChange={(name, value) => {\n'
        '        setValues((current) => ({ ...current, [name]: value }));\n'
        '      }} />\n'
        '      {valuesDirty && <button className="btn sm prompt-start" disabled={saving || compressing} onClick={() => { void saveValues(); }}>{t.prompt.saveValues}</button>}\n'
        '      {item.compressed_prompt && <div className="row wrap">\n'
        '        <Seg label={t.opt.finalPrompt} value={view} onChange={setView} options={[\n'
        "          { value: 'original', label: t.opt.showOriginal },\n"
        "          { value: 'compressed', label: t.opt.showCompressed },\n"
        "          { value: 'diff', label: t.prompt.showDiff },\n"
        '        ]} />\n'
        '      </div>}\n'
        "      {view === 'diff' && item.compressed_prompt ? <>\n"
        '        <PromptDiff original={item.final_prompt} compressed={item.compressed_prompt} />\n'
        '        <p className="small tx3">{t.prompt.copyOutsideDiff}</p>\n'
        '      </> : <>\n'
        '        <div className="prompt-box" tabIndex={0} aria-label={t.opt.finalPrompt}>{prompt}</div>\n'
        '        <PromptActions text={prompt} />\n'
        '      </>}\n'
        "      <PromptChecklist text={view === 'diff' ? compressed : prompt} />\n"
        '      <details className="result-details">\n'
        '        <summary>{t.prompt.details}</summary>\n'
        '        <div className="col">\n'
        '          <div className="row wrap">\n'
        '            <button className="btn" onClick={() => { void compress(); }} disabled={compressing || saving}>\n'
        '              {compressing ? <Spinner /> : <Minimize2 size={15} aria-hidden />}{compressing ? t.opt.compressing : t.opt.compress}\n'
        '            </button>\n'
        '            <span className="small tx3 mono">{t.prompt.tokenCount.replace(\'{count}\', String(estimateTokens(view === \'diff\' ? compressed : prompt)))}</span>\n'
        '          </div>\n'
        '          {note && <p className="small tx2" role="status">{note}</p>}\n'
        '          {item.initial_critique && <p className="small tx2">{item.initial_critique}</p>}\n'
        '          {item.changelog_explanation.length > 0 && <div className="col">\n'
        '            <h3>{t.opt.changelog}</h3><ul className="prompt-explanations">{item.changelog_explanation.map((item, i) => <li key={i}>{item}</li>)}</ul>\n'
        '          </div>}\n'
        '          <div className="form-grid">\n'
        '            <div><label className="label" htmlFor={`folder-${item.id}`}>{t.opt.folder}</label>\n'
        '              <select id={`folder-${item.id}`} className="field" disabled={saving || compressing} value={item.folder_id ?? \'\'}\n'
        '                onChange={(event) => { void save({ folder_id: event.target.value || null }); }}>\n'
        '                <option value="">{t.opt.noFolder}</option>{folders.map((folder) => <option key={folder.id} value={folder.id}>{folder.name}</option>)}\n'
        '              </select>\n'
        '            </div>\n'
        '            <div><label className="label" htmlFor={`tags-${item.id}`}>{t.opt.tags}</label>\n'
        '              <input id={`tags-${item.id}`} className="field" value={tags} disabled={saving || compressing} onChange={(event) => setTags(event.target.value)} onBlur={saveTags} />\n'
        '            </div>\n'
        '          </div>\n'
        '          <div className="row wrap">\n'
        '            <button className="btn sm" disabled={saving || compressing} onClick={() => setEditor(\'versions\')}>{t.prompt.editVersion}</button>\n'
        '            <button className="btn sm" disabled={saving || compressing} onClick={() => setEditor(\'publish\')}>{t.team.publish}</button>\n'
        '          </div>\n'
        '          {item.model && <p className="small tx3">{t.opt.engine} · <span className="mono">{item.model}</span></p>}\n'
        '        </div>\n'
        '      </details>\n'
        "      {editor === 'versions' && <PromptVersionEditor url={`${url}/versions`} onClose={() => setEditor(null)} onSave={async (body, expected_version) => {\n"
        '        onChange(await put<OptimizationDTO>(`${url}/prompt`, { body, expected_version }));\n'
        "        setNote('');\n"
        "        setView('original');\n"
        '      }} />}\n'
        "      {editor === 'publish' && <PublishPrompt body={item.final_prompt} onClose={() => setEditor(null)} />}\n"
        '    </section>\n'
        '  );\n'
        '}\n'
      )),
    ),
    'apps/web/src/components/ResultCard.tsx': (
      ((
        "import { useEffect, useState } from 'react';\n"
        "import { ChevronLeft, ChevronRight, RefreshCw, FilePlus2, ChevronDown } from 'lucide-react';\n"
        "import { SYSTEM_NAMES, type ResultDTO, type SystemId } from '../../../../shared/src/index.ts';\n"
        "import { t } from '../strings.ru.ts';\n"
        "import { CopyButton, StarButton, HighlightedPrompt, SystemDot, Spinner } from '../ui.tsx';\n"
        '\n'
        'export function groupBySystem(results: ResultDTO[]): Map<SystemId, ResultDTO[]> {\n'
        '  const m = new Map<SystemId, ResultDTO[]>();\n'
        '  for (const r of [...results].sort((a, b) => a.created_at.localeCompare(b.created_at))) { const l = m.get(r.skill_id) ?? []; l.push(r); m.set(r.skill_id, l); }\n'
      ), (
        "import { useEffect, useState } from 'react';\n"
        "import { ChevronLeft, ChevronRight, RefreshCw, FilePlus2, ChevronDown } from 'lucide-react';\n"
        "import { SYSTEM_NAMES, type ResultDTO, type SystemId } from '../../../../shared/src/index.ts';\n"
        "import { t } from '../strings.ru.ts';\n"
        "import { PromptActions } from './PromptActions.tsx';\n"
        "import { PromptChecklist } from './PromptFields.tsx';\n"
        "import { PublishPrompt } from './PublishPrompt.tsx';\n"
        "import { StarButton, HighlightedPrompt, SystemDot, Spinner } from '../ui.tsx';\n"
        '\n'
        'export function groupBySystem(results: ResultDTO[]): Map<SystemId, ResultDTO[]> {\n'
        '  const m = new Map<SystemId, ResultDTO[]>();\n'
        '  for (const r of [...results].sort((a, b) => a.created_at.localeCompare(b.created_at))) { const l = m.get(r.skill_id) ?? []; l.push(r); m.set(r.skill_id, l); }\n'
      )),
      ((
        'export function ResultCard({ system, variants, loading, error, onFavorite, onRegenerate, onTemplate, busy }: {\n'
        '  system: SystemId; variants: ResultDTO[]; loading?: boolean; error?: string | null; busy?: boolean;\n'
        '  onFavorite: (r: ResultDTO, v: boolean) => void; onRegenerate: (r: ResultDTO, feedback: string) => void; onTemplate: (r: ResultDTO) => void;\n'
        '}) {\n'
        "  const [idx, setIdx] = useState(Math.max(0, variants.length - 1)); const [expanded, setExpanded] = useState(false); const [fb, setFb] = useState(''); const [fbOpen, setFbOpen] = useState(false);\n"
        '  useEffect(() => { setIdx(Math.max(0, variants.length - 1)); }, [variants.length]);\n'
        '  const r = variants[Math.min(idx, variants.length - 1)];\n'
        '  if (loading && !r) return <div className="surface card col" aria-busy><div className="row"><SystemDot id={system} /><h3>{SYSTEM_NAMES[system]}</h3><Spinner /></div><div className="skeleton" style={{ height: 220 }} /></div>;\n'
      ), (
        'export function ResultCard({ system, variants, loading, error, onFavorite, onRegenerate, onTemplate, busy }: {\n'
        '  system: SystemId; variants: ResultDTO[]; loading?: boolean; error?: string | null; busy?: boolean;\n'
        '  onFavorite: (r: ResultDTO, v: boolean) => void; onRegenerate: (r: ResultDTO, feedback: string) => void; onTemplate: (r: ResultDTO) => void;\n'
        '}) {\n'
        '  const [publishing, setPublishing] = useState(false);\n'
        "  const [idx, setIdx] = useState(Math.max(0, variants.length - 1)); const [expanded, setExpanded] = useState(false); const [fb, setFb] = useState(''); const [fbOpen, setFbOpen] = useState(false);\n"
        '  useEffect(() => { setIdx(Math.max(0, variants.length - 1)); }, [variants.length]);\n'
        '  const r = variants[Math.min(idx, variants.length - 1)];\n'
        '  if (loading && !r) return <div className="surface card col" aria-busy><div className="row"><SystemDot id={system} /><h3>{SYSTEM_NAMES[system]}</h3><Spinner /></div><div className="skeleton" style={{ height: 220 }} /></div>;\n'
      )),
      ((
        "  const failed = r.status === 'failed';\n"
        '  return (\n'
        '    <article className="surface card col" aria-label={SYSTEM_NAMES[system]}>\n'
        '      <div className="row wrap spread">\n'
        '        <div className="row"><SystemDot id={system} /><h3>{SYSTEM_NAMES[system]}</h3>{!failed && <span className="badge info">{t.gen.skillBadge} v{r.skill_version}</span>}{!failed && <span className="badge">{(r.latency_ms / 1000).toFixed(1)} c</span>}</div>\n'
        '        {variants.length > 1 && <div className="row" aria-label={t.gen.variant}><button className="icon-btn" aria-label={t.common.prev} disabled={idx === 0} onClick={() => setIdx(idx - 1)}><ChevronLeft size={18} /></button><span className="small tx2">{t.gen.variant} {idx + 1}/{variants.length}</span><button className="icon-btn" aria-label={t.common.next} disabled={idx >= variants.length - 1} onClick={() => setIdx(idx + 1)}><ChevronRight size={18} /></button></div>}\n'
        '      </div>\n'
        '      {failed ? (\n'
        '        <div className="banner err" role="alert" style={{ margin: 0 }}><span className="grow">{t.gen.failed}{r.error ? `: ${r.error}` : \'\'}</span><button className="btn sm" disabled={busy} onClick={() => onRegenerate(r, \'\')}><RefreshCw size={14} />{t.common.retry}</button></div>\n'
        '      ) : (<>\n'
        "        <div className={`prompt-box ${expanded ? 'full' : ''}`} tabIndex={0}><HighlightedPrompt text={r.prompt_text} /></div>\n"
        '        {r.prompt_text.length > 700 && <button className="btn sm ghost" style={{ alignSelf: \'flex-start\' }} onClick={() => setExpanded(!expanded)}>{expanded ? t.common.collapse : t.common.expand}</button>}\n'
        '        <div className="row wrap">\n'
        '          <CopyButton text={r.prompt_text} primary /><StarButton on={r.is_favorite} onClick={() => onFavorite(r, !r.is_favorite)} />\n'
        '          <button className="btn sm" onClick={() => onTemplate(r)}><FilePlus2 size={15} />{t.common.toTemplate}</button>\n'
        '          <button className="btn sm" disabled={busy} onClick={() => setFbOpen(!fbOpen)} aria-expanded={fbOpen}>{busy ? <Spinner /> : <RefreshCw size={15} />}{t.gen.regenerate}</button>\n'
        '        </div>\n'
        '        {fbOpen && <div className="row"><input className="field" value={fb} maxLength={500} placeholder={t.gen.feedbackPlaceholder} onChange={(e) => setFb(e.target.value)} onKeyDown={(e) => { if (e.key === \'Enter\') { onRegenerate(r, fb); setFbOpen(false); setFb(\'\'); } }} aria-label={t.gen.feedbackPlaceholder} /><button className="btn primary sm" onClick={() => { onRegenerate(r, fb); setFbOpen(false); setFb(\'\'); }}>{t.gen.applyFeedback}</button></div>}\n'
        '        <details><summary><ChevronDown size={14} style={{ verticalAlign: -2 }} /> {t.gen.improved}</summary>\n'
        '          <ul className="tx2" style={{ margin: \'0 0 10px\', paddingLeft: 20 }}>{r.improvements.map((x, i) => <li key={i}>{x}</li>)}</ul>\n'
        '          {r.assumptions.length > 0 && <><span className="label">{t.gen.assumptionsTitle}</span><div className="row wrap" style={{ marginBottom: 10 }}>{r.assumptions.map((a, i) => <span key={i} className="chip static" style={{ whiteSpace: \'normal\' }}>{a}</span>)}</div></>}\n'
        '          {r.usage_notes && <><span className="label">{t.gen.usageNotes}</span><p className="tx2" style={{ margin: 0 }}>{r.usage_notes}</p></>}\n'
        '        </details>\n'
        '      </>)}\n'
        '      {error && !failed && <p className="small" style={{ color: \'var(--color-danger)\' }}>{error}</p>}\n'
        '    </article>\n'
        '  );\n'
      ), (
        "  const failed = r.status === 'failed';\n"
        '  return (\n'
        '    <article className="surface card col" aria-label={SYSTEM_NAMES[system]}>\n'
        '      <div className="row wrap spread">\n'
        '        <div className="row"><SystemDot id={system} /><h3>{SYSTEM_NAMES[system]}</h3>{!failed && <span className="badge info result-meta">{t.gen.skillBadge} v{r.skill_version}</span>}{!failed && <span className="badge result-meta">{(r.latency_ms / 1000).toFixed(1)} c</span>}</div>\n'
        '        {variants.length > 1 && <div className="row" aria-label={t.gen.variant}><button className="icon-btn" aria-label={t.common.prev} disabled={idx === 0} onClick={() => setIdx(idx - 1)}><ChevronLeft size={18} /></button><span className="small tx2">{t.gen.variant} {idx + 1}/{variants.length}</span><button className="icon-btn" aria-label={t.common.next} disabled={idx >= variants.length - 1} onClick={() => setIdx(idx + 1)}><ChevronRight size={18} /></button></div>}\n'
        '      </div>\n'
        '      {failed ? (\n'
        '        <div className="banner err" role="alert" style={{ margin: 0 }}><span className="grow">{t.gen.failed}{r.error ? `: ${r.error}` : \'\'}</span><button className="btn sm" disabled={busy} onClick={() => onRegenerate(r, \'\')}><RefreshCw size={14} />{t.common.retry}</button></div>\n'
        '      ) : (<>\n'
        "        <div className={`prompt-box ${expanded ? 'full' : ''}`} tabIndex={0}><HighlightedPrompt text={r.prompt_text} /></div>\n"
        '        {r.prompt_text.length > 700 && <button className="btn sm ghost" style={{ alignSelf: \'flex-start\' }} onClick={() => setExpanded(!expanded)}>{expanded ? t.common.collapse : t.common.expand}</button>}\n'
        '        <PromptActions key={r.id} text={r.prompt_text} />\n'
        '        <PromptChecklist text={r.prompt_text} />\n'
        '        <details className="result-details"><summary>{t.prompt.details}</summary>\n'
        '        <div className="row wrap">\n'
        '          <StarButton on={r.is_favorite} onClick={() => onFavorite(r, !r.is_favorite)} />\n'
        '          <button className="btn sm" onClick={() => setPublishing(true)}>{t.team.publish}</button>\n'
        '          <button className="btn sm" onClick={() => onTemplate(r)}><FilePlus2 size={15} />{t.common.toTemplate}</button>\n'
        '          <button className="btn sm" disabled={busy} onClick={() => setFbOpen(!fbOpen)} aria-expanded={fbOpen}>{busy ? <Spinner /> : <RefreshCw size={15} />}{t.gen.regenerate}</button>\n'
        '        </div>\n'
        '        {fbOpen && <div className="row"><input className="field" value={fb} maxLength={500} placeholder={t.gen.feedbackPlaceholder} onChange={(e) => setFb(e.target.value)} onKeyDown={(e) => { if (e.key === \'Enter\') { onRegenerate(r, fb); setFbOpen(false); setFb(\'\'); } }} aria-label={t.gen.feedbackPlaceholder} /><button className="btn primary sm" onClick={() => { onRegenerate(r, fb); setFbOpen(false); setFb(\'\'); }}>{t.gen.applyFeedback}</button></div>}\n'
        '        <details><summary><ChevronDown size={14} style={{ verticalAlign: -2 }} /> {t.gen.improved}</summary>\n'
        '          <ul className="tx2" style={{ margin: \'0 0 10px\', paddingLeft: 20 }}>{r.improvements.map((x, i) => <li key={i}>{x}</li>)}</ul>\n'
        '          {r.assumptions.length > 0 && <><span className="label">{t.gen.assumptionsTitle}</span><div className="row wrap" style={{ marginBottom: 10 }}>{r.assumptions.map((a, i) => <span key={i} className="chip static" style={{ whiteSpace: \'normal\' }}>{a}</span>)}</div></>}\n'
        '          {r.usage_notes && <><span className="label">{t.gen.usageNotes}</span><p className="tx2" style={{ margin: 0 }}>{r.usage_notes}</p></>}\n'
        '        </details></details>\n'
        '        {publishing && <PublishPrompt body={r.prompt_text} onClose={() => setPublishing(false)} />}\n'
        '      </>)}\n'
        '      {error && !failed && <p className="small" style={{ color: \'var(--color-danger)\' }}>{error}</p>}\n'
        '    </article>\n'
        '  );\n'
      )),
    ),
    'apps/web/src/context.tsx': (
      ((
        '\n'
        'export interface Me { user_id: string; name: string; role: string; is_admin: boolean }\n'
        "export interface AgentStatus { scheduler_mode: 'job' | 'lazy'; auto_refresh_enabled: boolean; paused_reason: string | null; busy: boolean; next_check_at: string | null; job_secret_configured: boolean; timezone: string }\n"
        "export interface Prefill { raw_input: string; systems?: SystemId[]; language?: 'ru' | 'en'; options?: Partial<GenOptions>; nonce: number }\n"
        "export type Screen = 'generator' | 'history' | 'templates' | 'favorites' | 'skills' | 'reports' | 'settings' | 'analytics' | 'optimizer' | 'library';\n"
        'export interface AppState {\n'
        "  me: Me | null; settings: Settings | null; agent: AgentStatus | null; go: (s: Screen) => void; prefill: Prefill | null; setPrefill: (p: Omit<Prefill, 'nonce'>, go?: boolean) => void;\n"
        "  reload: () => void; setSettings: (s: Settings) => void; openGeneration: (id: string) => void; openGenerationId: string | null; clearOpenGeneration: () => void; theme: 'dark' | 'light' | 'system'; setTheme: (t: 'dark' | 'light' | 'system') => void;\n"
        '}\n'
      ), (
        '\n'
        'export interface Me { user_id: string; name: string; role: string; is_admin: boolean }\n'
        "export interface AgentStatus { scheduler_mode: 'job' | 'lazy'; auto_refresh_enabled: boolean; paused_reason: string | null; busy: boolean; next_check_at: string | null; job_secret_configured: boolean; timezone: string }\n"
        "export interface Prefill { raw_input: string; systems?: SystemId[]; language?: 'ru' | 'en'; options?: Partial<GenOptions>; nonce: number }\n"
        "export type Screen = 'home' | 'generator' | 'history' | 'templates' | 'favorites' | 'skills' | 'reports' | 'settings' | 'analytics' | 'optimizer' | 'library';\n"
        'export interface AppState {\n'
        "  me: Me | null; settings: Settings | null; agent: AgentStatus | null; go: (s: Screen) => void; prefill: Prefill | null; setPrefill: (p: Omit<Prefill, 'nonce'>, go?: boolean) => void;\n"
        "  reload: () => void; setSettings: (s: Settings) => void; openGeneration: (id: string) => void; openGenerationId: string | null; clearOpenGeneration: () => void; theme: 'dark' | 'light' | 'system'; setTheme: (t: 'dark' | 'light' | 'system') => void;\n"
        '}\n'
      )),
    ),
    'apps/web/src/index.css': (
      ((
        '@media (max-width: 360px) {\n'
        '  .compact .bottom-tabs .nav-item { overflow-wrap: anywhere; }\n'
        '  .card { padding: var(--space-4); }\n'
        '}\n'
      ), (
        '@media (max-width: 360px) {\n'
        '  .compact .bottom-tabs .nav-item { overflow-wrap: anywhere; }\n'
        '  .card { padding: var(--space-4); }\n'
        '}\n'
        '\n'
        '/* Prompt workspace and shared library */\n'
        '.home-workspace, .library-workspace { gap: var(--space-6); }\n'
        '.prompt-start { align-self: flex-start; }\n'
        '.prompt-select { inline-size: auto; }\n'
        '.prompt-result p, .role-examples p, .prompt-diff p { margin: 0; }\n'
        '.result-details > summary { display: flex; align-items: center; gap: var(--space-2); min-block-size: var(--control-height-sm); }\n'
        ".result-details > summary::before { content: ''; flex: none; inline-size: var(--space-2); block-size: var(--space-2); border: solid var(--color-text-muted); border-width: 0 1px 1px 0; transform: rotate(-45deg); }\n"
        '.result-details[open] > summary::before { transform: rotate(45deg); }\n'
        '.result-details > :where(p, .row) { margin-block: var(--space-2); }\n'
        '.prompt-fields { padding: 0; margin: 0; border: 0; min-inline-size: 0; }\n'
        '.prompt-fields legend { padding: 0; }\n'
        '.prompt-fields .field { display: block; }\n'
        '.criterion-list, .prompt-history, .prompt-explanations { margin-block: 0 var(--space-2); }\n'
        '.criterion-list, .prompt-history { padding-inline-start: 0; list-style: none; }\n'
        '.criterion-list li { margin-block: var(--space-1); }\n'
        '.prompt-explanations { padding-inline-start: var(--space-5); }\n'
        '.prompt-diff del { color: var(--color-text-muted); background: var(--color-danger-bg); text-decoration: line-through; }\n'
        '.prompt-diff ins { color: var(--color-success-text); background: var(--color-success-bg); text-decoration: underline; }\n'
        '.publish-preview { max-block-size: calc(var(--space-16) * 3); }\n'
        '\n'
        '@media (max-width: 799px) {\n'
        '  .home-workspace, .library-workspace { gap: var(--space-4); }\n'
        '  .result-meta { display: none; }\n'
        '  .result-details > summary { min-block-size: var(--control-height); }\n'
        '}\n'
      )),
    ),
    'apps/web/src/screens/Generator.tsx': (
      ((
        "import { useEffect, useMemo, useRef, useState } from 'react';\n"
        "import { Wand2, ChevronDown } from 'lucide-react';\n"
        "import { SYSTEM_IDS, SYSTEM_NAMES, LIMITS, type GenOptions, type ResultDTO, type SystemId } from '../../../../shared/src/index.ts';\n"
        "import { t } from '../strings.ru.ts';\n"
        "import { streamGenerate, post, patch, ApiError } from '../api.ts';\n"
        "import { useApp } from '../context.tsx';\n"
        "import { Seg, Switch, Spinner, SystemDot, useToast } from '../ui.tsx';\n"
        "import { ResultCard } from '../components/ResultCard.tsx';\n"
        "import { TemplateSaveModal } from '../components/TemplateSaveModal.tsx';\n"
        '\n'
        "type CardState = { status: 'loading' | 'ok' | 'error'; variants: ResultDTO[]; error?: string };\n"
        '\n'
        'export function GeneratorScreen() {\n'
        '  const app = useApp(); const toast = useToast();\n'
        "  const [raw, setRaw] = useState(''); const [systems, setSystems] = useState<SystemId[]>([...SYSTEM_IDS]); const [language, setLanguage] = useState<'ru' | 'en'>('ru');\n"
        "  const [opts, setOpts] = useState<GenOptions>({ task_type: 'auto', detail: 'standard', assumptions_mode: 'assume', include_format: true });\n"
        "  const [running, setRunning] = useState(false); const [stage, setStage] = useState(''); const [cards, setCards] = useState<Record<string, CardState>>({}); const [order, setOrder] = useState<SystemId[]>([]);\n"
        "  const [active, setActive] = useState<SystemId | null>(null); const [genId, setGenId] = useState(''); const [questions, setQuestions] = useState<string[] | null>(null); const [answers, setAnswers] = useState<string[]>([]);\n"
        '  const [compare, setCompare] = useState(false); const [cmp, setCmp] = useState<SystemId[]>([]); const [tpl, setTpl] = useState<ResultDTO | null>(null); const [busyCard, setBusyCard] = useState<string | null>(null);\n'
        '  const [polling, setPolling] = useState(false); const [advOpen, setAdvOpen] = useState(false);\n'
        '  const ta = useRef<HTMLTextAreaElement>(null); const defaultsApplied = useRef(false);\n'
        '\n'
        '  useEffect(() => { // defaults from settings (once)\n'
        '    const s = app.settings; if (!s || defaultsApplied.current || app.prefill) return; defaultsApplied.current = true;\n'
        '    setLanguage(s.default_language); setSystems(s.default_systems); setOpts((o) => ({ ...o, detail: s.default_detail, assumptions_mode: s.default_assumptions_mode }));\n'
        '  }, [app.settings, app.prefill]);\n'
        '  useEffect(() => { // prefill from history/templates\n'
        '    const p = app.prefill; if (!p) return; defaultsApplied.current = true;\n'
        '    setRaw(p.raw_input); if (p.systems?.length) setSystems(p.systems); if (p.language) setLanguage(p.language); if (p.options) setOpts((o) => ({ ...o, ...p.options }));\n'
        '    setTimeout(() => ta.current?.focus(), 50);\n'
        '  }, [app.prefill?.nonce]); // eslint-disable-line react-hooks/exhaustive-deps\n'
        "  useEffect(() => { const el = ta.current; if (!el) return; el.style.height = 'auto'; const line = 24; el.style.height = `${Math.min(Math.max(el.scrollHeight, line * 4 + 24), line * 12 + 24)}px`; }, [raw]);\n"
      ), (
        "import { useEffect, useMemo, useRef, useState } from 'react';\n"
        "import { Wand2, ChevronDown } from 'lucide-react';\n"
        "import { SYSTEM_IDS, SYSTEM_NAMES, LIMITS, type GenerateRequest, type GenOptions, type ResultDTO, type SystemId } from '../../../../shared/src/index.ts';\n"
        "import { t } from '../strings.ru.ts';\n"
        "import { streamGenerate, post, patch, ApiError } from '../api.ts';\n"
        "import { useApp } from '../context.tsx';\n"
        "import { Seg, Switch, Spinner, SystemDot, useToast } from '../ui.tsx';\n"
        "import { ClarificationForm } from '../components/ClarificationForm.tsx';\n"
        "import { ResultCard } from '../components/ResultCard.tsx';\n"
        "import { TemplateSaveModal } from '../components/TemplateSaveModal.tsx';\n"
        '\n'
        "type CardState = { status: 'loading' | 'ok' | 'error'; variants: ResultDTO[]; error?: string };\n"
        '\n'
        'export function GeneratorScreen({ starter, onBusy }: { starter?: GenerateRequest; onBusy?: (busy: boolean) => void } = {}) {\n'
        '  const app = useApp(); const toast = useToast();\n'
        "  const [raw, setRaw] = useState(''); const [systems, setSystems] = useState<SystemId[]>(starter?.systems ?? [...SYSTEM_IDS]); const [language, setLanguage] = useState<'ru' | 'en'>(starter?.language ?? 'ru');\n"
        "  const [opts, setOpts] = useState<GenOptions>({ task_type: 'auto', detail: 'standard', assumptions_mode: 'assume', include_format: true });\n"
        "  const [running, setRunning] = useState(false); const [stage, setStage] = useState(''); const [cards, setCards] = useState<Record<string, CardState>>({}); const [order, setOrder] = useState<SystemId[]>([]);\n"
        "  const [active, setActive] = useState<SystemId | null>(null); const [genId, setGenId] = useState(''); const [questions, setQuestions] = useState<string[] | null>(null); const [answers, setAnswers] = useState<string[]>([]);\n"
        '  const [compare, setCompare] = useState(false); const [cmp, setCmp] = useState<SystemId[]>([]); const [tpl, setTpl] = useState<ResultDTO | null>(null); const [busyCard, setBusyCard] = useState<string | null>(null);\n'
        '  const [polling, setPolling] = useState(false); const [advOpen, setAdvOpen] = useState(false);\n'
        '  const ta = useRef<HTMLTextAreaElement>(null); const defaultsApplied = useRef(!!starter); const started = useRef(false);\n'
        '\n'
        '  useEffect(() => { // defaults from settings (once)\n'
        '    const s = app.settings; if (!s || defaultsApplied.current || app.prefill) return; defaultsApplied.current = true;\n'
        '    setLanguage(s.default_language); setSystems(s.default_systems); setOpts((o) => ({ ...o, detail: s.default_detail, assumptions_mode: s.default_assumptions_mode }));\n'
        '  }, [app.settings, app.prefill]);\n'
        '  useEffect(() => { // prefill from history/templates\n'
        '    const p = app.prefill; if (!p || starter) return; defaultsApplied.current = true;\n'
        '    setRaw(p.raw_input); if (p.systems?.length) setSystems(p.systems); if (p.language) setLanguage(p.language); if (p.options) setOpts((o) => ({ ...o, ...p.options }));\n'
        '    setTimeout(() => ta.current?.focus(), 50);\n'
        '  }, [app.prefill?.nonce]); // eslint-disable-line react-hooks/exhaustive-deps\n'
        "  useEffect(() => { const el = ta.current; if (!el) return; el.style.height = 'auto'; const line = 24; el.style.height = `${Math.min(Math.max(el.scrollHeight, line * 4 + 24), line * 12 + 24)}px`; }, [raw]);\n"
      )),
      ((
        '  const allOn = systems.length === SYSTEM_IDS.length;\n'
        '  const valid = raw.trim().length >= LIMITS.rawInputMin && raw.length <= LIMITS.rawInputMax;\n'
        '\n'
        "  const resetCards = (sys: SystemId[]) => { setOrder(sys); setCards(Object.fromEntries(sys.map((s) => [s, { status: 'loading', variants: [] } as CardState]))); setActive(sys[0] ?? null); setCmp([]); };\n"
        '  const run = async (path: string, body: unknown, sys: SystemId[]) => {\n'
        '    setRunning(true); setStage(t.gen.stages.analyze); setQuestions(null); setPolling(false); resetCards(sys);\n'
        '    await streamGenerate(path, body, {\n'
        '      onStart: setGenId, onIntent: () => setStage(t.gen.stages.transform), onFallback: () => setPolling(true),\n'
        "      onCard: (r) => setCards((c) => ({ ...c, [r.skill_id]: { status: 'ok', variants: [...(c[r.skill_id]?.variants ?? []), r] } })),\n"
        "      onCardError: (s, e, r) => setCards((c) => ({ ...c, [s]: { status: 'error', variants: r ? [...(c[s]?.variants ?? []), r] : c[s]?.variants ?? [], error: e } })),\n"
        "      onQuestions: (list, id) => { setQuestions(list); setAnswers(list.map(() => '')); setGenId(id); setCards({}); setOrder([]); },\n"
        "      onDone: () => { setRunning(false); setStage(''); },\n"
        "      onError: (e) => { setRunning(false); setStage(''); setCards({}); setOrder([]); toast(e.status === 429 ? `${e.message}${e.retryAfter ? ` (${e.retryAfter} c)` : ''}` : e.message, 'err'); },\n"
        '    });\n'
        '    setRunning(false);\n'
        '  };\n'
        "  const submit = () => { if (!valid || running) return; void run('/api/generate', { raw_input: raw.trim(), systems, language, options: opts }, systems); };\n"
        '  const answer = () => { if (!genId || running) return; void run(`/api/generate/${genId}/answer`, { answers }, systems); };\n'
        "  useEffect(() => { const h = (e: KeyboardEvent) => { if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') { e.preventDefault(); submit(); } }; window.addEventListener('keydown', h); return () => window.removeEventListener('keydown', h); });\n"
        '\n'
        '  const favorite = async (r: ResultDTO, v: boolean) => {\n'
        '    try { await patch(`/api/results/${r.id}/favorite`, { value: v }); setCards((c) => ({ ...c, [r.skill_id]: { ...c[r.skill_id]!, variants: c[r.skill_id]!.variants.map((x) => (x.id === r.id ? { ...x, is_favorite: v } : x)) } })); }\n'
        "    catch (e) { toast((e as ApiError).message, 'err'); }\n"
      ), (
        '  const allOn = systems.length === SYSTEM_IDS.length;\n'
        '  const valid = raw.trim().length >= LIMITS.rawInputMin && raw.length <= LIMITS.rawInputMax;\n'
        '\n'
        "  const resetCards = (sys: SystemId[]) => { setOrder(sys); setCards(Object.fromEntries(sys.map((s) => [s, { status: 'loading', variants: [] } as CardState]))); setActive(sys[0] ?? null); setCmp([]); };\n"
        '  const run = async (path: string, body: unknown, sys: SystemId[], continueDraft = false) => {\n'
        '    onBusy?.(true);\n'
        '    setRunning(true); setStage(t.gen.stages.analyze); if (!continueDraft) setQuestions(null); setPolling(false); resetCards(sys);\n'
        '    await streamGenerate(path, body, {\n'
        '      onStart: setGenId, onIntent: () => setStage(t.gen.stages.transform), onFallback: () => setPolling(true),\n'
        "      onCard: (r) => { setQuestions(null); setCards((c) => ({ ...c, [r.skill_id]: { status: 'ok', variants: [...(c[r.skill_id]?.variants ?? []), r] } })); },\n"
        "      onCardError: (s, e, r) => setCards((c) => ({ ...c, [s]: { status: 'error', variants: r ? [...(c[s]?.variants ?? []), r] : c[s]?.variants ?? [], error: e } })),\n"
        "      onQuestions: (list, id) => { setQuestions(list); setAnswers(list.map(() => '')); setGenId(id); setCards({}); setOrder([]); },\n"
        "      onDone: (_id, status) => { if (status !== 'draft_questions') setQuestions(null); setRunning(false); setStage(''); },\n"
        "      onError: (e) => { setRunning(false); setStage(''); setCards({}); setOrder([]); toast(e.status === 429 ? `${e.message}${e.retryAfter ? ` (${e.retryAfter} c)` : ''}` : e.message, 'err'); },\n"
        '    });\n'
        '    setRunning(false);\n'
        '    onBusy?.(false);\n'
        '  };\n'
        "  const submit = () => { if (!valid || running) return; void run('/api/generate', { raw_input: raw.trim(), systems, language, options: opts }, systems); };\n"
        '  const answer = () => { if (!genId || running) return; void run(`/api/generate/${genId}/answer`, { answers }, systems, true); };\n'
        '  useEffect(() => {\n'
        '    if (!starter || started.current) return;\n'
        '    started.current = true;\n'
        "    void run('/api/generate', starter, starter.systems);\n"
        '  }, [starter]); // A Home submission starts one run, including under StrictMode.\n'
        "  useEffect(() => { if (starter) return; const h = (e: KeyboardEvent) => { if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') { e.preventDefault(); submit(); } }; window.addEventListener('keydown', h); return () => window.removeEventListener('keydown', h); });\n"
        '\n'
        '  const favorite = async (r: ResultDTO, v: boolean) => {\n'
        '    try { await patch(`/api/results/${r.id}/favorite`, { value: v }); setCards((c) => ({ ...c, [r.skill_id]: { ...c[r.skill_id]!, variants: c[r.skill_id]!.variants.map((x) => (x.id === r.id ? { ...x, is_favorite: v } : x)) } })); }\n'
        "    catch (e) { toast((e as ApiError).message, 'err'); }\n"
      )),
      ((
        "  const done = useMemo(() => order.filter((s) => cards[s]?.status === 'ok'), [order, cards]);\n"
        '  const cmpSet = cmp.length === 2 ? cmp : done.slice(0, 2);\n'
        '\n'
        '  return (\n'
        '    <div className="col" style={{ gap: 18 }}>\n'
        '      <section className="surface card col" aria-labelledby="gen-title" style={{ padding: 24 }}>\n'
        '        <h1 id="gen-title">{t.gen.title}</h1>\n'
        '        <div><textarea ref={ta} className="field" value={raw} maxLength={LIMITS.rawInputMax} placeholder={t.gen.placeholder} onChange={(e) => setRaw(e.target.value)} aria-label={t.gen.title} />\n'
        '          <div className="row spread small tx3" style={{ marginTop: 6 }}><span>{raw.length > 0 && raw.trim().length < LIMITS.rawInputMin ? t.gen.tooShort : \'\'}</span><span>{raw.length} / {LIMITS.rawInputMax} {t.gen.counter}</span></div></div>\n'
        '        <div className="row wrap" role="group" aria-label={t.gen.systems}>\n'
      ), (
        "  const done = useMemo(() => order.filter((s) => cards[s]?.status === 'ok'), [order, cards]);\n"
        '  const cmpSet = cmp.length === 2 ? cmp : done.slice(0, 2);\n'
        '\n'
        '  return (\n'
        '    <div className="col">\n'
        '      {!starter && <section className="surface card col" aria-labelledby="gen-title" style={{ padding: 24 }}>\n'
        '        <h1 id="gen-title">{t.gen.title}</h1>\n'
        '        <div><textarea ref={ta} className="field" value={raw} maxLength={LIMITS.rawInputMax} placeholder={t.gen.placeholder} onChange={(e) => setRaw(e.target.value)} aria-label={t.gen.title} />\n'
        '          <div className="row spread small tx3" style={{ marginTop: 6 }}><span>{raw.length > 0 && raw.trim().length < LIMITS.rawInputMin ? t.gen.tooShort : \'\'}</span><span>{raw.length} / {LIMITS.rawInputMax} {t.gen.counter}</span></div></div>\n'
        '        <div className="row wrap" role="group" aria-label={t.gen.systems}>\n'
      )),
      ((
        '            <div><span className="label">{t.gen.assumptions}</span><Seg label={t.gen.assumptions} value={opts.assumptions_mode} onChange={(v) => setOpts({ ...opts, assumptions_mode: v })} options={Object.entries(t.gen.modes).map(([value, label]) => ({ value: value as GenOptions[\'assumptions_mode\'], label }))} /></div>\n'
        '            <div className="row"><Switch on={opts.include_format} onChange={(v) => setOpts({ ...opts, include_format: v })} label={t.gen.includeFormat} /><span>{t.gen.includeFormat}</span></div>\n'
        '          </div>}</div>\n'
        '        <div className="row wrap"><button className="btn primary" disabled={!valid || running} onClick={submit}>{running ? <Spinner /> : <Wand2 size={17} />}{running ? stage : t.gen.submit}</button><span className="small tx3">{t.gen.hint}</span>{polling && <span className="small tx2">{t.gen.fallbackPoll}</span>}</div>\n'
        '      </section>\n'
        '\n'
        '      {questions && <section className="surface card col" aria-label={t.gen.questionsTitle}><h3>{t.gen.questionsTitle}</h3>\n'
        '        {questions.map((q, i) => <div key={i}><label className="label" htmlFor={`q${i}`}>{q}</label><input id={`q${i}`} className="field" value={answers[i] ?? \'\'} placeholder={t.gen.answerPlaceholder} onChange={(e) => setAnswers(answers.map((a, j) => (j === i ? e.target.value : a)))} /></div>)}\n'
        '        <button className="btn primary" style={{ alignSelf: \'flex-start\' }} onClick={answer}>{t.gen.questionsContinue}</button></section>}\n'
        '\n'
        '      {order.length > 0 && <section className="col" aria-live="polite">\n'
        '        <div className="row wrap" role="tablist">\n'
        '          {order.map((s) => { const c = cards[s]; const dot = !c || c.status === \'loading\' ? \'run\' : c.status === \'ok\' ? \'ok\' : \'err\'; return <button key={s} role="tab" aria-selected={active === s} className={`tab ${active === s ? \'on\' : \'\'}`} onClick={() => { setActive(s); if (compare) setCmp((x) => (x.includes(s) ? x.filter((y) => y !== s) : [...x, s].slice(-2))); }}><span className={`dot ${dot}`} />{SYSTEM_NAMES[s]}</button>; })}\n'
        '          {done.length > 1 && <><div className="grow" /><div className="row"><span className="small tx2">{t.gen.compare}</span><Switch on={compare} onChange={setCompare} label={t.gen.compare} /></div></>}\n'
        '        </div>\n'
        '        {compare && done.length > 1 ? <div className="grid-cards stagger" style={{ gridTemplateColumns: \'repeat(auto-fit, minmax(340px, 1fr))\' }}>{cmpSet.map(cardEl)}</div>\n'
        '          : <div className="stagger">{active && cardEl(active)}</div>}\n'
        '      </section>}\n'
        '      {tpl && <TemplateSaveModal prompt={tpl.prompt_text} language={language} systems={[tpl.skill_id]} onClose={() => setTpl(null)} />}\n'
        '    </div>\n'
      ), (
        '            <div><span className="label">{t.gen.assumptions}</span><Seg label={t.gen.assumptions} value={opts.assumptions_mode} onChange={(v) => setOpts({ ...opts, assumptions_mode: v })} options={Object.entries(t.gen.modes).map(([value, label]) => ({ value: value as GenOptions[\'assumptions_mode\'], label }))} /></div>\n'
        '            <div className="row"><Switch on={opts.include_format} onChange={(v) => setOpts({ ...opts, include_format: v })} label={t.gen.includeFormat} /><span>{t.gen.includeFormat}</span></div>\n'
        '          </div>}</div>\n'
        '        <div className="row wrap"><button className="btn primary" disabled={!valid || running} onClick={submit}>{running ? <Spinner /> : <Wand2 size={17} />}{running ? stage : t.gen.submit}</button><span className="small tx3">{t.gen.hint}</span>{polling && <span className="small tx2">{t.gen.fallbackPoll}</span>}</div>\n'
        '      </section>}\n'
        '\n'
        '      {questions && <ClarificationForm key={genId} questions={questions} answers={answers} setAnswers={setAnswers}\n'
        '        suggestUrl={`/api/generate/${genId}/suggest`} busy={running} onContinue={answer} />}\n'
        '\n'
        '      {starter && running && !order.length && <div role="status"><Spinner /> {stage}</div>}\n'
        '      {order.length > 0 && <section className="col" aria-live="polite">\n'
        '        {order.length > 1 && <div className="row wrap" role="group" aria-label={t.gen.systems}>\n'
        "          {order.map((s) => { const c = cards[s]; const dot = !c || c.status === 'loading' ? 'run' : c.status === 'ok' ? 'ok' : 'err'; return <button key={s} aria-pressed={active === s} className={`tab ${active === s ? 'on' : ''}`} onClick={() => { setActive(s); if (compare) setCmp((x) => (x.includes(s) ? x.filter((y) => y !== s) : [...x, s].slice(-2))); }}><span className={`dot ${dot}`} />{SYSTEM_NAMES[s]}</button>; })}\n"
        '          {done.length > 1 && <><div className="grow" /><div className="row"><span className="small tx2">{t.gen.compare}</span><Switch on={compare} onChange={setCompare} label={t.gen.compare} /></div></>}\n'
        '        </div>}\n'
        '        {compare && done.length > 1 ? <div className="grid-cards stagger" style={{ gridTemplateColumns: \'repeat(auto-fit, minmax(min(100%, 340px), 1fr))\' }}>{cmpSet.map(cardEl)}</div>\n'
        '          : <div className="stagger">{active && cardEl(active)}</div>}\n'
        '      </section>}\n'
        '      {tpl && <TemplateSaveModal prompt={tpl.prompt_text} language={language} systems={[tpl.skill_id]} onClose={() => setTpl(null)} />}\n'
        '    </div>\n'
      )),
    ),
    'apps/web/src/screens/Library.tsx': (
      ((
        "import { OPT_LIMITS, OPT_WORKFLOWS, type FolderDTO, type OptWorkflow, type OptimizationDTO } from '../../../../shared/src/index.ts';\n"
        "import { t } from '../strings.ru.ts';\n"
        "import { del, get, patch, post, ApiError } from '../api.ts';\n"
        "import { useApp } from '../context.tsx';\n"
        "import { OptimizationView } from '../components/OptimizationView.tsx';\n"
        "import { ConfirmModal, Empty, Modal, Skeletons, StarButton, fmtDate, useDebounced, useToast } from '../ui.tsx';\n"
        '\n'
        'interface Row { id: string; workflow: OptWorkflow; preview: string; prompt_preview: string; initial_score: number | null; optimized_score: number | null; is_favorite: boolean; folder_id: string | null; tags: string[]; created_at: string; has_variables: boolean }\n'
        '\n'
        'export function LibraryScreen() {\n'
        '  const toast = useToast(); const app = useApp();\n'
        "  const [folders, setFolders] = useState<FolderDTO[]>([]); const [folder, setFolder] = useState<string>('all'); const [wf, setWf] = useState<OptWorkflow | ''>('');\n"
        "  const [q, setQ] = useState(''); const dq = useDebounced(q); const [page, setPage] = useState(1);\n"
        '  const [rows, setRows] = useState<Row[] | null>(null); const [total, setTotal] = useState(0);\n'
      ), (
        "import { OPT_LIMITS, OPT_WORKFLOWS, type FolderDTO, type OptWorkflow, type OptimizationDTO } from '../../../../shared/src/index.ts';\n"
        "import { t } from '../strings.ru.ts';\n"
        "import { del, get, patch, post, ApiError } from '../api.ts';\n"
        "import { useApp } from '../context.tsx';\n"
        "import { TeamLibrary } from '../components/TeamLibrary.tsx';\n"
        "import { OptimizationView } from '../components/OptimizationView.tsx';\n"
        "import { ConfirmModal, Empty, Modal, Seg, Skeletons, StarButton, fmtDate, useDebounced, useToast } from '../ui.tsx';\n"
        '\n'
        'interface Row { id: string; workflow: OptWorkflow; preview: string; prompt_preview: string; is_favorite: boolean; folder_id: string | null; tags: string[]; created_at: string; has_variables: boolean }\n'
        '\n'
        'export function LibraryScreen() {\n'
        "  const [scope, setScope] = useState<'personal' | 'team'>('personal');\n"
        '  return <div className="col library-workspace">\n'
        '    <header className="row spread wrap">\n'
        '      <h1>{t.library.title}</h1>\n'
        '      <Seg label={t.library.title} value={scope} onChange={setScope} options={[\n'
        "        { value: 'personal', label: t.team.personal }, { value: 'team', label: t.team.scope },\n"
        '      ]} />\n'
        '    </header>\n'
        "    {scope === 'personal' ? <PersonalLibrary /> : <TeamLibrary />}\n"
        '  </div>;\n'
        '}\n'
        '\n'
        'function PersonalLibrary() {\n'
        '  const toast = useToast(); const app = useApp();\n'
        "  const [folders, setFolders] = useState<FolderDTO[]>([]); const [folder, setFolder] = useState<string>('all'); const [wf, setWf] = useState<OptWorkflow | ''>('');\n"
        "  const [q, setQ] = useState(''); const dq = useDebounced(q); const [page, setPage] = useState(1);\n"
        '  const [rows, setRows] = useState<Row[] | null>(null); const [total, setTotal] = useState(0);\n'
      )),
      ((
        '    </button>\n'
        '  );\n'
        '  return (\n'
        '    <div className="col" style={{ gap: \'var(--space-6)\' }}>\n'
        '      <h1>{t.library.title}</h1>\n'
        '      <div className="library-layout">\n'
        '        <nav className="surface card col library-folders" aria-label={t.library.folders}>\n'
        "          {folderButton('all', t.library.all)}\n"
        "          {folderButton('fav', t.library.favorites)}\n"
      ), (
        '    </button>\n'
        '  );\n'
        '  return (\n'
        '    <div className="col" style={{ gap: \'var(--space-6)\' }}>\n'
        '      <div className="library-layout">\n'
        '        <nav className="surface card col library-folders" aria-label={t.library.folders}>\n'
        "          {folderButton('all', t.library.all)}\n"
        "          {folderButton('fav', t.library.favorites)}\n"
      )),
      ((
        '              {rows.map((r) => (\n'
        '                <div key={r.id} className="surface card col" style={{ gap: \'var(--space-2)\' }}>\n'
        '                  <div className="row spread wrap">\n'
        '                    <div className="row wrap"><span className="badge">{t.opt.workflows[r.workflow]}</span>{r.has_variables && <span className="badge info">{t.library.template}</span>}\n'
        '                      {r.optimized_score !== null && <span className="badge ok">{r.initial_score?.toFixed(1)} → {r.optimized_score.toFixed(1)}</span>}<span className="small tx3">{fmtDate(r.created_at)}</span></div>\n'
        '                    <div className="row"><StarButton on={r.is_favorite} onClick={() => star(r)} /><button className="btn sm" onClick={() => openItem(r.id)}>{t.library.open}</button></div>\n'
        '                  </div>\n'
        '                  <div style={{ fontWeight: 500 }}>{r.preview}</div>\n'
        '                  <div className="small tx2" style={{ overflowWrap: \'anywhere\' }}>{r.prompt_preview}</div>\n'
      ), (
        '              {rows.map((r) => (\n'
        '                <div key={r.id} className="surface card col" style={{ gap: \'var(--space-2)\' }}>\n'
        '                  <div className="row spread wrap">\n'
        '                    <div className="row wrap"><span className="badge">{t.opt.workflows[r.workflow]}</span>{r.has_variables && <span className="badge info">{t.library.template}</span>}\n'
        '                      <span className="small tx3">{fmtDate(r.created_at)}</span></div>\n'
        '                    <div className="row"><StarButton on={r.is_favorite} onClick={() => star(r)} /><button className="btn sm" onClick={() => openItem(r.id)}>{t.library.open}</button></div>\n'
        '                  </div>\n'
        '                  <div style={{ fontWeight: 500 }}>{r.preview}</div>\n'
        '                  <div className="small tx2" style={{ overflowWrap: \'anywhere\' }}>{r.prompt_preview}</div>\n'
      )),
    ),
    'apps/web/src/screens/Optimizer.tsx': (
      ((
        "import { useEffect, useRef, useState } from 'react';\n"
        "import { Upload } from 'lucide-react';\n"
        "import { FRAMEWORK_PRESETS, GOAL_PRESETS, OPT_LIMITS, OPT_WORKFLOWS, OUTPUT_FORMATS, TONES, type FolderDTO, type OptPreset, type OptWorkflow, type OptimizationDTO } from '../../../../shared/src/index.ts';\n"
        "import { t } from '../strings.ru.ts';\n"
        "import { get, post, ApiError } from '../api.ts';\n"
        "import { OptimizationView } from '../components/OptimizationView.tsx';\n"
        "import { Seg, Spinner, Switch, useToast } from '../ui.tsx';\n"
        '\n'
        'const store = { get: (k: string) => { try { return localStorage.getItem(k); } catch { return null; } }, set: (k: string, v: string) => { try { localStorage.setItem(k, v); } catch { /* ignore */ } } };\n'
      ), (
        "import { useEffect, useRef, useState } from 'react';\n"
        "import { Upload } from 'lucide-react';\n"
        "import { FRAMEWORK_PRESETS, GOAL_PRESETS, OPT_LIMITS, OPT_WORKFLOWS, OUTPUT_FORMATS, TONES, type FolderDTO, type OptPreset, type OptWorkflow, type OptimizationDTO, type OptimizeRequest } from '../../../../shared/src/index.ts';\n"
        "import { t } from '../strings.ru.ts';\n"
        "import { get, postPrompt, ApiError } from '../api.ts';\n"
        "import { ClarificationForm } from '../components/ClarificationForm.tsx';\n"
        "import { OptimizationView } from '../components/OptimizationView.tsx';\n"
        "import { Seg, Spinner, Switch, useToast } from '../ui.tsx';\n"
        '\n'
        'const store = { get: (k: string) => { try { return localStorage.getItem(k); } catch { return null; } }, set: (k: string, v: string) => { try { localStorage.setItem(k, v); } catch { /* ignore */ } } };\n'
      )),
      ((
        'const Chip = ({ on, label, hint, onClick }: { on: boolean; label: string; hint?: string; onClick: () => void }) => (\n'
        "  <button className={`chip ${on ? 'on' : ''}`} aria-pressed={on} title={hint} onClick={onClick}>{label}</button>\n"
        ');\n'
        '\n'
        'export function OptimizerScreen() {\n'
        '  const toast = useToast(); const file = useRef<HTMLInputElement>(null);\n'
        "  const [workflow, setWorkflow] = useState<OptWorkflow>('magic');\n"
        "  const [mode, setMode] = useState<'beginner' | 'pro'>(() => (store.get('opt_mode') === 'pro' ? 'pro' : 'beginner'));\n"
        "  const [goal, setGoal] = useState<OptPreset | null>(null); const [framework, setFramework] = useState<OptPreset>('auto');\n"
        "  const [format, setFormat] = useState<(typeof OUTPUT_FORMATS)[number]>('none'); const [tone, setTone] = useState<(typeof TONES)[number]>('none');\n"
      ), (
        'const Chip = ({ on, label, hint, onClick }: { on: boolean; label: string; hint?: string; onClick: () => void }) => (\n'
        "  <button className={`chip ${on ? 'on' : ''}`} aria-pressed={on} title={hint} onClick={onClick}>{label}</button>\n"
        ');\n'
        '\n'
        'export function OptimizerScreen({ starter, onBusy }: { starter?: OptimizeRequest; onBusy?: (busy: boolean) => void } = {}) {\n'
        '  const toast = useToast(); const file = useRef<HTMLInputElement>(null); const started = useRef(false);\n'
        "  const [workflow, setWorkflow] = useState<OptWorkflow>('magic');\n"
        "  const [mode, setMode] = useState<'beginner' | 'pro'>(() => (store.get('opt_mode') === 'pro' ? 'pro' : 'beginner'));\n"
        "  const [goal, setGoal] = useState<OptPreset | null>(null); const [framework, setFramework] = useState<OptPreset>('auto');\n"
        "  const [format, setFormat] = useState<(typeof OUTPUT_FORMATS)[number]>('none'); const [tone, setTone] = useState<(typeof TONES)[number]>('none');\n"
      )),
      ((
        "  const preset: OptPreset = mode === 'pro' ? framework : goal ?? 'auto';\n"
        "  const fail = (e: unknown) => toast((e as ApiError).message ?? t.common.error, 'err');\n"
        "  const setModeSaved = (m: 'beginner' | 'pro') => { setMode(m); store.set('opt_mode', m); };\n"
        '  const canRun = input.trim().length >= OPT_LIMITS.rawMin && !busy;\n'
        '  const run = async () => {\n'
        '    setBusy(true); setItem(null);\n'
        "    try { const r = await post<OptimizationDTO>('/api/optimizer/run', { workflow, raw_input: input.trim(), preset, output_format: format, tone, bridge }); setItem(r); setAnswers(r.clarifying_questions.map(() => '')); if (r.status === 'ok') toast(t.opt.saved, 'ok'); }\n"
        '    catch (e) { fail(e); } finally { setBusy(false); }\n'
        '  };\n'
        '  const answer = async (auto: boolean) => {\n'
        '    if (!item) return; setBusy(true);\n'
        "    try { const r = await post<OptimizationDTO>(`/api/optimizer/items/${item.id}/answer`, { answers: auto ? [] : answers, auto }); setItem(r); toast(t.opt.saved, 'ok'); } catch (e) { fail(e); } finally { setBusy(false); }\n"
        '  };\n'
        '  const loadFile = async (f: File) => {\n'
        "    if (f.size > MAX_FILE) { toast(t.opt.fileTooBig, 'err'); return; }\n"
        '    try {\n'
      ), (
        "  const preset: OptPreset = mode === 'pro' ? framework : goal ?? 'auto';\n"
        "  const fail = (e: unknown) => toast((e as ApiError).message ?? t.common.error, 'err');\n"
        "  const setModeSaved = (m: 'beginner' | 'pro') => { setMode(m); store.set('opt_mode', m); };\n"
        '  const canRun = input.trim().length >= OPT_LIMITS.rawMin && !busy;\n'
        '  const run = async (request?: OptimizeRequest) => {\n'
        '    setBusy(true); onBusy?.(true); setItem(null);\n'
        "    try { const r = await postPrompt<OptimizationDTO>('/api/optimizer/run', request ?? { workflow, raw_input: input.trim(), preset, output_format: format, tone, bridge }); setItem(r); setAnswers(r.clarifying_questions.map(() => '')); if (r.status === 'ok') toast(t.opt.saved, 'ok'); }\n"
        '    catch (e) { fail(e); } finally { setBusy(false); onBusy?.(false); }\n'
        '  };\n'
        '  useEffect(() => {\n'
        '    if (!starter || started.current) return;\n'
        '    started.current = true;\n'
        '    void run(starter);\n'
        '  }, [starter]); // The Home entry is a single submitted task.\n'
        '  const answer = async (auto: boolean) => {\n'
        '    if (!item) return; setBusy(true); onBusy?.(true);\n'
        "    try { const r = await postPrompt<OptimizationDTO>(`/api/optimizer/items/${item.id}/answer`, { answers: auto ? [] : answers, auto }); setItem(r); toast(t.opt.saved, 'ok'); } catch (e) { fail(e); } finally { setBusy(false); onBusy?.(false); }\n"
        '  };\n'
        '  const loadFile = async (f: File) => {\n'
        "    if (f.size > MAX_FILE) { toast(t.opt.fileTooBig, 'err'); return; }\n"
        '    try {\n'
      )),
      ((
        '    } catch (error) { fail(error); }\n'
        '  };\n'
        '  return (\n'
        '    <div className="col" style={{ gap: \'var(--space-6)\' }}>\n'
        '      <div><h1>{t.opt.title}</h1><p className="tx2" style={{ margin: \'var(--space-1) 0 0\' }}>{t.opt.subtitle}</p></div>\n'
        '      <div className="workflow-picker" role="group" aria-label={t.opt.title}>\n'
        "        {OPT_WORKFLOWS.map((w) => <button key={w} aria-pressed={workflow === w} disabled={busy} className={`tab ${workflow === w ? 'on' : ''}`} onClick={() => { setWorkflow(w); setItem(null); }}>{t.opt.workflows[w]}</button>)}\n"
        '      </div>\n'
      ), (
        '    } catch (error) { fail(error); }\n'
        '  };\n'
        '  return (\n'
        '    <div className="col" style={{ gap: \'var(--space-6)\' }}>\n'
        '      {!starter && <>\n'
        '      <div><h1>{t.opt.title}</h1><p className="tx2" style={{ margin: \'var(--space-1) 0 0\' }}>{t.opt.subtitle}</p></div>\n'
        '      <div className="workflow-picker" role="group" aria-label={t.opt.title}>\n'
        "        {OPT_WORKFLOWS.map((w) => <button key={w} aria-pressed={workflow === w} disabled={busy} className={`tab ${workflow === w ? 'on' : ''}`} onClick={() => { setWorkflow(w); setItem(null); }}>{t.opt.workflows[w]}</button>)}\n"
        '      </div>\n'
      )),
      ((
        '        <textarea id="opt-input" className="field" rows={workflow === \'reverse\' ? 9 : 5} maxLength={OPT_LIMITS.rawMax} value={input} placeholder={t.opt.placeholders[workflow]} onChange={(e) => setInput(e.target.value)}\n'
        "          onKeyDown={(e) => { if ((e.ctrlKey || e.metaKey) && e.key === 'Enter' && canRun) void run(); }} />\n"
        '        {workflow === \'reverse\' && <div className="row wrap"><button className="btn sm" onClick={() => file.current?.click()}><Upload size={14} aria-hidden />{t.opt.fileHint}</button><span className="small tx3">{t.opt.imagesNote}</span>\n'
        '          <input ref={file} type="file" hidden accept=".txt,.md,.csv,.json,text/plain,text/markdown,application/json,text/csv" onChange={(e) => { const f = e.target.files?.[0]; if (f) void loadFile(f); e.target.value = \'\'; }} /></div>}\n'
        '        <div className="row spread wrap">\n'
        '          <div className="row wrap"><span className="label" style={{ margin: 0 }}>{t.opt.mode}</span>\n'
        "            <Seg label={t.opt.mode} value={mode} onChange={setModeSaved} options={[{ value: 'beginner', label: t.opt.beginner }, { value: 'pro', label: t.opt.pro }]} /></div>\n"
        '          <span className="small tx3">{input.length}/{OPT_LIMITS.rawMax}</span>\n'
      ), (
        '        <textarea id="opt-input" className="field" rows={workflow === \'reverse\' ? 9 : 5} maxLength={OPT_LIMITS.rawMax} value={input} placeholder={t.opt.placeholders[workflow]} onChange={(e) => setInput(e.target.value)}\n'
        "          onKeyDown={(e) => { if ((e.ctrlKey || e.metaKey) && e.key === 'Enter' && canRun) void run(); }} />\n"
        '        {workflow === \'reverse\' && <div className="row wrap"><button className="btn sm" onClick={() => file.current?.click()}><Upload size={14} aria-hidden />{t.opt.fileHint}</button><span className="small tx3">{t.opt.imagesNote}</span>\n'
        '          <input ref={file} type="file" hidden accept=".txt,.md,.csv,.json,text/plain,text/markdown,application/json,text/csv" onChange={(e) => { const f = e.target.files?.[0]; if (f) void loadFile(f); e.target.value = \'\'; }} /></div>}\n'
        '        <details className="result-details"><summary>{t.prompt.settings}</summary><div className="col">\n'
        '        <div className="row spread wrap">\n'
        '          <div className="row wrap"><span className="label" style={{ margin: 0 }}>{t.opt.mode}</span>\n'
        "            <Seg label={t.opt.mode} value={mode} onChange={setModeSaved} options={[{ value: 'beginner', label: t.opt.beginner }, { value: 'pro', label: t.opt.pro }]} /></div>\n"
        '          <span className="small tx3">{input.length}/{OPT_LIMITS.rawMax}</span>\n'
      )),
      ((
        '          <div><span className="label">{t.opt.formatTitle}</span><div className="row wrap">{OUTPUT_FORMATS.map((f) => <Chip key={f} on={format === f} label={t.opt.formats[f]} onClick={() => setFormat(f)} />)}</div></div>\n'
        '          <div><span className="label">{t.opt.toneTitle}</span><div className="row wrap">{TONES.map((x) => <Chip key={x} on={tone === x} label={t.opt.tones[x]} onClick={() => setTone(x)} />)}</div></div>\n'
        '        </div>\n'
        '        <div className="row"><Switch on={bridge} onChange={setBridge} label={t.opt.bridge} /><div><span>{t.opt.bridge}</span><div className="small tx3">{t.opt.bridgeHint}</div></div></div>\n'
        '        <div className="row"><button className="btn primary" disabled={!canRun} onClick={run}>{busy ? <Spinner /> : null}{busy ? t.opt.running : t.opt.run[workflow]}</button><kbd className="small tx3 shortcut">{t.opt.runShortcut}</kbd></div>\n'
        '      </section>\n'
        "      {item?.status === 'draft_questions' && (\n"
        '        <section className="surface card col" aria-label={t.opt.questionsTitle}>\n'
        '          <h3>{t.opt.questionsTitle}</h3>\n'
        '          {item.clarifying_questions.map((q, i) => <div key={i}><label className="label" htmlFor={`q-${i}`}>{i + 1}. {q}</label>\n'
        '            <input id={`q-${i}`} className="field" maxLength={OPT_LIMITS.answerMax} placeholder={t.opt.answerPlaceholder} value={answers[i] ?? \'\'} onChange={(e) => setAnswers(answers.map((a, j) => (j === i ? e.target.value : a)))} /></div>)}\n'
        '          <div className="row"><button className="btn primary" disabled={busy} onClick={() => answer(false)}>{busy ? <Spinner /> : null}{t.opt.answerContinue}</button><button className="btn" disabled={busy} onClick={() => answer(true)}>{t.opt.answerSkip}</button></div>\n'
        '        </section>\n'
        '      )}\n'
        "      {item?.status === 'ok' && <OptimizationView key={item.id} item={item} folders={folders} onChange={setItem} />}\n"
        '    </div>\n'
        '  );\n'
        '}\n'
      ), (
        '          <div><span className="label">{t.opt.formatTitle}</span><div className="row wrap">{OUTPUT_FORMATS.map((f) => <Chip key={f} on={format === f} label={t.opt.formats[f]} onClick={() => setFormat(f)} />)}</div></div>\n'
        '          <div><span className="label">{t.opt.toneTitle}</span><div className="row wrap">{TONES.map((x) => <Chip key={x} on={tone === x} label={t.opt.tones[x]} onClick={() => setTone(x)} />)}</div></div>\n'
        '        </div>\n'
        '        <div className="row"><Switch on={bridge} onChange={setBridge} label={t.opt.bridge} /><div><span>{t.opt.bridge}</span><div className="small tx3">{t.opt.bridgeHint}</div></div></div>\n'
        '        </div></details>\n'
        '        <div className="row"><button className="btn primary" disabled={!canRun} onClick={() => { void run(); }}>{busy ? <Spinner /> : null}{busy ? t.opt.running : t.opt.run[workflow]}</button><kbd className="small tx3 shortcut">{t.opt.runShortcut}</kbd></div>\n'
        '      </section>\n'
        '      </>}\n'
        '      {starter && busy && !item && <div role="status"><Spinner /> {t.opt.running}</div>}\n'
        "      {item?.status === 'draft_questions' && <ClarificationForm key={item.id} questions={item.clarifying_questions} answers={answers}\n"
        '        setAnswers={setAnswers} suggestUrl={`/api/optimizer/items/${item.id}/suggest`} busy={busy}\n'
        '        onContinue={() => { void answer(false); }} onSkip={() => { void answer(true); }} />}\n'
        "      {item?.status === 'ok' && <OptimizationView key={item.id} item={item} folders={folders} onChange={setItem} />}\n"
        '    </div>\n'
        '  );\n'
        '}\n'
      )),
    ),
    'apps/web/src/screens/Templates.tsx': (
      ((
        "import { useEffect, useMemo, useRef, useState } from 'react';\n"
        "import { Plus, MoreHorizontal, Sparkles } from 'lucide-react';\n"
        "import { SYSTEM_IDS, extractVariables, substituteVariables, LIMITS, type SystemId, type TemplateDTO } from '../../../../shared/src/index.ts';\n"
        "import { t } from '../strings.ru.ts';\n"
        "import { get, post, patch, del, ApiError } from '../api.ts';\n"
        "import { useApp } from '../context.tsx';\n"
        "import { Empty, Skeletons, Modal, ConfirmModal, SystemChip, Spinner, Seg, useToast, useDebounced } from '../ui.tsx';\n"
        '\n'
        'export function TemplatesScreen() {\n'
      ), (
        "import { useEffect, useMemo, useState } from 'react';\n"
        "import { Plus, MoreHorizontal } from 'lucide-react';\n"
        "import { SYSTEM_IDS, extractVariables, substituteVariables, LIMITS, type PromptVersions, type SystemId, type TemplateDTO } from '../../../../shared/src/index.ts';\n"
        "import { t } from '../strings.ru.ts';\n"
        "import { get, post, patch, del, ApiError } from '../api.ts';\n"
        "import { PromptActions } from '../components/PromptActions.tsx';\n"
        "import { PromptFields, PromptChecklist } from '../components/PromptFields.tsx';\n"
        "import { VersionHistory } from '../components/PromptVersionEditor.tsx';\n"
        "import { useApp } from '../context.tsx';\n"
        "import { Empty, Skeletons, Modal, ConfirmModal, SystemChip, Spinner, Seg, useToast, useDebounced } from '../ui.tsx';\n"
        '\n'
        'export function TemplatesScreen() {\n'
      )),
      ((
        '  const toast = useToast(); const [values, setValues] = useState<Record<string, string>>({}); const [busy, setBusy] = useState(false);\n'
        '  const preview = useMemo(() => substituteVariables(tp.body, values), [tp.body, values]);\n'
        "  const go = async () => { setBusy(true); try { const r = await post<{ text: string }>(`/api/templates/${tp.id}/use`, { values }); onGo(r.text); } catch (e) { toast((e as ApiError).message, 'err'); } finally { setBusy(false); } };\n"
        '  return <Modal title={`${t.templates.useTitle}: ${tp.title}`} wide onClose={onClose} footer={<><button className="btn" onClick={onClose}>{t.common.cancel}</button><button className="btn primary" disabled={busy} onClick={go}>{busy && <Spinner />}{t.templates.toGenerator}</button></>}>\n'
        '    {tp.variables.map((v) => <div key={v}><label className="label" htmlFor={`v-${v}`}>{v}</label>{/(notes|text|error|body|content)/.test(v)\n'
        '      ? <textarea id={`v-${v}`} className="field" rows={4} value={values[v] ?? \'\'} onChange={(e) => setValues({ ...values, [v]: e.target.value })} />\n'
        '      : <input id={`v-${v}`} className="field" value={values[v] ?? \'\'} onChange={(e) => setValues({ ...values, [v]: e.target.value })} />}</div>)}\n'
        '    <div><span className="label">{t.templates.preview}</span><div className="prompt-box">{preview}</div></div>\n'
        '  </Modal>;\n'
        '}\n'
        '\n'
        'function EditorModal({ tp, onClose, onSaved }: { tp: TemplateDTO | null; onClose: () => void; onSaved: () => void }) {\n'
        "  const toast = useToast(); const [title, setTitle] = useState(tp?.title ?? ''); const [description, setDescription] = useState(tp?.description ?? ''); const [body, setBody] = useState(tp?.body ?? '');\n"
        "  const [language, setLanguage] = useState<'ru' | 'en'>(tp?.language ?? 'ru'); const [systems, setSystems] = useState<SystemId[]>(tp?.default_systems ?? [...SYSTEM_IDS]); const [tags, setTags] = useState((tp?.tags ?? []).join(', ')); const [busy, setBusy] = useState(false);\n"
        '  const bd = useRef<HTMLDivElement>(null); const vars = extractVariables(body); const tooMany = vars.length > LIMITS.maxTemplateVars;\n'
        "  const hl = body.split(/(\\{\\{\\s*[a-z0-9_]+\\s*\\}\\})/g).map((p, i) => (/^\\{\\{/.test(p) ? <mark key={i} style={{ background: 'var(--color-accent-soft)', color: 'transparent', borderRadius: 4 }}>{p}</mark> : <span key={i}>{p}</span>));\n"
        '  const toggle = (id: SystemId) => setSystems((s) => (s.includes(id) ? (s.length > 1 ? s.filter((x) => x !== id) : s) : [...s, id]));\n'
        '  const save = async () => {\n'
        "    setBusy(true); const payload = { title, description, body, language, default_systems: systems, tags: tags.split(',').map((x) => x.trim()).filter(Boolean) };\n"
        "    try { tp ? await patch(`/api/templates/${tp.id}`, payload) : await post('/api/templates', payload); toast(t.templates.saved, 'ok'); onSaved(); } catch (e) { toast((e as ApiError).message, 'err'); } finally { setBusy(false); }\n"
        '  };\n'
        '  const mono = { fontFamily: "\'JetBrains Mono\', monospace", fontSize: 13, lineHeight: 1.6, padding: 12, whiteSpace: \'pre-wrap\' as const, wordBreak: \'break-word\' as const, border: \'1px solid transparent\' };\n'
        '  return <Modal title={t.templates.editor} wide onClose={onClose} footer={<><button className="btn" onClick={onClose}>{t.common.cancel}</button><button className="btn primary" disabled={busy || !title.trim() || !body.trim() || tooMany} onClick={save}>{busy && <Spinner />}{t.common.save}</button></>}>\n'
        '    <div><label className="label" htmlFor="e-title">{t.templates.titleField}</label><input id="e-title" className="field" value={title} maxLength={120} onChange={(e) => setTitle(e.target.value)} /></div>\n'
        '    <div><label className="label" htmlFor="e-desc">{t.templates.descField}</label><input id="e-desc" className="field" value={description} maxLength={400} onChange={(e) => setDescription(e.target.value)} /></div>\n'
        '    <div><label className="label" htmlFor="e-body">{t.templates.bodyField}</label>\n'
        "      <div style={{ position: 'relative', background: 'var(--color-surface-secondary)', borderRadius: 14, border: '1px solid var(--color-border)' }}>\n"
        "        <div ref={bd} aria-hidden style={{ ...mono, position: 'absolute', inset: 0, overflow: 'hidden', pointerEvents: 'none', color: 'transparent' }}>{hl}{'\\n'}</div>\n"
        '        <textarea id="e-body" rows={9} value={body} onChange={(e) => setBody(e.target.value)} onScroll={(e) => { if (bd.current) bd.current.scrollTop = e.currentTarget.scrollTop; }}\n'
        "          style={{ ...mono, position: 'relative', width: '100%', background: 'transparent', color: 'var(--color-text-primary)', outline: 'none', resize: 'vertical', borderRadius: 14, display: 'block' }} /></div>\n"
        '      <div className="row wrap small" style={{ marginTop: 6 }}><span className="tx3">{t.templates.variables}:</span>{vars.map((v) => <span key={v} className="badge">{`{{${v}}}`}</span>)}{tooMany && <span style={{ color: \'var(--color-danger)\' }}>{t.templates.maxVars}</span>}</div></div>\n'
        '    <div className="row wrap" style={{ gap: 16 }}><Seg label="language" value={language} onChange={setLanguage} options={[{ value: \'ru\', label: \'RU\' }, { value: \'en\', label: \'EN\' }]} />\n'
        '      <div className="row wrap">{SYSTEM_IDS.map((id) => <button key={id} type="button" className={`chip ${systems.includes(id) ? \'on\' : \'\'}`} aria-pressed={systems.includes(id)} onClick={() => toggle(id)}>{id}</button>)}</div></div>\n'
        '    <div><label className="label" htmlFor="e-tags">{t.templates.tagsField}</label><input id="e-tags" className="field" value={tags} onChange={(e) => setTags(e.target.value)} /></div>\n'
        '  </Modal>;\n'
        '}\n'
        'void Sparkles;\n'
      ), (
        '  const toast = useToast(); const [values, setValues] = useState<Record<string, string>>({}); const [busy, setBusy] = useState(false);\n'
        '  const preview = useMemo(() => substituteVariables(tp.body, values), [tp.body, values]);\n'
        "  const go = async () => { setBusy(true); try { const r = await post<{ text: string }>(`/api/templates/${tp.id}/use`, { values }); onGo(r.text); } catch (e) { toast((e as ApiError).message, 'err'); } finally { setBusy(false); } };\n"
        '  return <Modal title={`${t.templates.useTitle}: ${tp.title}`} wide onClose={onClose} footer={<><button className="btn" onClick={onClose}>{t.common.cancel}</button><button className="btn primary" disabled={busy} onClick={go}>{busy && <Spinner />}{t.templates.toGenerator}</button></>}>\n'
        '    <PromptFields names={tp.variables} values={values} onChange={(name, value) => setValues((current) => ({ ...current, [name]: value }))} />\n'
        '    <div><span className="label">{t.templates.preview}</span><div className="prompt-box" tabIndex={0}>{preview}</div></div>\n'
        '    <PromptActions text={preview} />\n'
        '    <PromptChecklist text={preview} />\n'
        '  </Modal>;\n'
        '}\n'
        '\n'
        'function EditorModal({ tp, onClose, onSaved }: { tp: TemplateDTO | null; onClose: () => void; onSaved: () => void }) {\n'
        "  const toast = useToast(); const [title, setTitle] = useState(tp?.title ?? ''); const [description, setDescription] = useState(tp?.description ?? ''); const [body, setBody] = useState(tp?.body ?? '');\n"
        "  const [language, setLanguage] = useState<'ru' | 'en'>(tp?.language ?? 'ru'); const [systems, setSystems] = useState<SystemId[]>(tp?.default_systems ?? [...SYSTEM_IDS]); const [tags, setTags] = useState((tp?.tags ?? []).join(', ')); const [busy, setBusy] = useState(false);\n"
        '  const vars = extractVariables(body);\n'
        '  const tooMany = vars.length > LIMITS.maxTemplateVars;\n'
        '  const [versions, setVersions] = useState<PromptVersions | null>(null);\n'
        "  const [problem, setProblem] = useState('');\n"
        '  const versionsUrl = tp ? `/api/templates/${tp.id}/versions` : undefined;\n'
        '  useEffect(() => {\n'
        '    if (!versionsUrl) return;\n'
        '    let live = true;\n'
        '    void get<PromptVersions>(versionsUrl).then((data) => {\n'
        '      if (!live) return;\n'
        '      setVersions(data);\n'
        '      if (data.items[0]) setBody(data.items[0].body);\n'
        '    }).catch((error) => { if (live) setProblem(error instanceof Error ? error.message : t.common.error); });\n'
        '    return () => { live = false; };\n'
        '  }, [versionsUrl]);\n'
        '  const toggle = (id: SystemId) => setSystems((s) => (s.includes(id) ? (s.length > 1 ? s.filter((x) => x !== id) : s) : [...s, id]));\n'
        '  const save = async () => {\n'
        '    setBusy(true);\n'
        "    setProblem('');\n"
        "    const payload = { title, description, body, language, default_systems: systems, tags: tags.split(',').map((x) => x.trim()).filter(Boolean),\n"
        '      expected_version: versions?.current_version };\n'
        "    try { tp ? await patch(`/api/templates/${tp.id}`, payload) : await post('/api/templates', payload); toast(t.templates.saved, 'ok'); onSaved(); } catch (error) { setProblem(error instanceof Error ? error.message : t.common.error); } finally { setBusy(false); }\n"
        '  };\n'
        '  return <Modal title={t.templates.editor} wide onClose={onClose} footer={<><button className="btn" onClick={onClose}>{t.common.cancel}</button><button className="btn primary" disabled={busy || !!tp && !versions || !title.trim() || !body.trim() || tooMany} onClick={save}>{busy && <Spinner />}{t.common.save}</button></>}>\n'
        '    {problem && <p className="banner err" role="alert">{problem}</p>}\n'
        '    <div><label className="label" htmlFor="e-title">{t.templates.titleField}</label><input id="e-title" className="field" value={title} maxLength={120} onChange={(e) => setTitle(e.target.value)} /></div>\n'
        '    <div><label className="label" htmlFor="e-desc">{t.templates.descField}</label><input id="e-desc" className="field" value={description} maxLength={400} onChange={(e) => setDescription(e.target.value)} /></div>\n'
        '    <div><label className="label" htmlFor="e-body">{t.templates.bodyField}</label>\n'
        '      <textarea id="e-body" className="field mono" rows={9} maxLength={LIMITS.template} value={body}\n'
        '        disabled={!!tp && !versions} onChange={(event) => setBody(event.target.value)} />\n'
        '      <div className="row wrap small">\n'
        '        <span className="tx3">{t.templates.variables}</span>{vars.map((variable) => <span key={variable} className="badge">{variable}</span>)}\n'
        '        {tooMany && <span className="badge err">{t.templates.maxVars}</span>}\n'
        '      </div>\n'
        '    </div>\n'
        '    {versions && versionsUrl && <VersionHistory url={versionsUrl} current={versions} onSelect={setBody} />}\n'
        '    <div className="row wrap" style={{ gap: 16 }}><Seg label="language" value={language} onChange={setLanguage} options={[{ value: \'ru\', label: \'RU\' }, { value: \'en\', label: \'EN\' }]} />\n'
        '      <div className="row wrap">{SYSTEM_IDS.map((id) => <button key={id} type="button" className={`chip ${systems.includes(id) ? \'on\' : \'\'}`} aria-pressed={systems.includes(id)} onClick={() => toggle(id)}>{id}</button>)}</div></div>\n'
        '    <div><label className="label" htmlFor="e-tags">{t.templates.tagsField}</label><input id="e-tags" className="field" value={tags} onChange={(e) => setTags(e.target.value)} /></div>\n'
        '  </Modal>;\n'
        '}\n'
      )),
    ),
    'apps/web/src/strings.ru.ts': (
      ((
        "  banner: { quota: 'Квота ИИ исчерпана — агент обновлений приостановлен. Возобновится автоматически после успешного пробного вызова.', paused: 'Агент обновлений приостановлен', fallback: 'Планировщик в режиме fallback: проверка при использовании.', resume: 'Возобновить' },\n"
        "  gen: { title: 'Опишите задачу своими словами', placeholder: 'Например: нужен план запуска подкаста на 8 недель для начинающих авторов, с бюджетом и чек-листом', counter: 'символов', systems: 'Целевые ИИ-системы', allSystems: 'Все', language: 'Язык промпта',\n"
        "    advanced: 'Тонкая настройка', taskType: 'Тип задачи', detail: 'Детальность', assumptions: 'Режим допущений', includeFormat: 'Формат вывода', submit: 'Сформировать промпт', hint: 'Ctrl+Enter',\n"
        "    stages: { analyze: 'Анализ задачи…', transform: 'Формирую промпты…', done: 'Готово' },\n"
        "    taskTypes: { auto: 'Авто', code: 'Код', writing: 'Текст', analysis: 'Анализ', research: 'Исследование', agent: 'Агент', creative: 'Креатив' },\n"
        "    details: { brief: 'Кратко', standard: 'Стандарт', detailed: 'Подробно' }, modes: { assume: 'Допущения с пометкой', questions: 'Сначала спросить' },\n"
        "    questionsTitle: 'Нужно уточнить', questionsContinue: 'Продолжить', answerPlaceholder: 'Ваш ответ', tooShort: 'Минимум 10 символов', compare: 'Сравнить',\n"
        "    improved: 'Что улучшено', assumptionsTitle: 'Допущения', usageNotes: 'Как использовать', regenerate: 'Повторить', feedbackPlaceholder: 'Что поправить: короче, добавь примеры…', applyFeedback: 'Пересоздать',\n"
        "    variant: 'Вариант', skillBadge: 'skill', failed: 'Не удалось сформировать', quotaCard: 'Квота ИИ исчерпана', noResults: 'Здесь появятся результаты', fallbackPoll: 'Соединение потоком недоступно, обновляю по таймеру…', saveTemplate: 'Сохранить как шаблон' },\n"
      ), (
        "  banner: { quota: 'Квота ИИ исчерпана — агент обновлений приостановлен. Возобновится автоматически после успешного пробного вызова.', paused: 'Агент обновлений приостановлен', fallback: 'Планировщик в режиме fallback: проверка при использовании.', resume: 'Возобновить' },\n"
        "  gen: { title: 'Опишите задачу своими словами', placeholder: 'Например: нужен план запуска подкаста на 8 недель для начинающих авторов, с бюджетом и чек-листом', counter: 'символов', systems: 'Целевые ИИ-системы', allSystems: 'Все', language: 'Язык промпта',\n"
        "    advanced: 'Тонкая настройка', taskType: 'Тип задачи', detail: 'Детальность', assumptions: 'Режим допущений', includeFormat: 'Формат вывода', submit: 'Сформировать промпт', hint: 'Ctrl+Enter',\n"
        "    stages: { analyze: 'Анализ задачи…', transform: 'Формирую промпты…', done: 'Готово' },\n"
        "    taskTypes: { auto: 'Авто', code: 'Код', writing: 'Текст', analysis: 'Анализ', research: 'Исследование', agent: 'Агент', creative: 'Креатив', hypothesis: 'Проверка гипотезы' },\n"
        "    details: { brief: 'Кратко', standard: 'Стандарт', detailed: 'Подробно' }, modes: { assume: 'Допущения с пометкой', questions: 'Сначала спросить' },\n"
        "    questionsTitle: 'Нужно уточнить', questionsContinue: 'Продолжить', answerPlaceholder: 'Ваш ответ', tooShort: 'Минимум 10 символов', compare: 'Сравнить',\n"
        "    improved: 'Что улучшено', assumptionsTitle: 'Допущения', usageNotes: 'Как использовать', regenerate: 'Повторить', feedbackPlaceholder: 'Что поправить: короче, добавь примеры…', applyFeedback: 'Пересоздать',\n"
        "    variant: 'Вариант', skillBadge: 'skill', failed: 'Не удалось сформировать', quotaCard: 'Квота ИИ исчерпана', noResults: 'Здесь появятся результаты', fallbackPoll: 'Соединение потоком недоступно, обновляю по таймеру…', saveTemplate: 'Сохранить как шаблон' },\n"
      )),
      ((
        "    formatTitle: 'Формат ответа', formats: { none: 'Не задавать', table: 'Таблица', json: 'JSON (схема)', markdown_list: 'Markdown-список', prose: 'Связный текст', code: 'Готовый код', slides: 'Структура слайдов' },\n"
        "    toneTitle: 'Тон', tones: { none: 'Не задавать', academic: 'Академичный', persuasive: 'Убеждающий', friendly: 'Дружелюбный', concise: 'Лаконичный', no_yapping: 'Без воды' },\n"
        "    bridge: 'Мост языков: ввод RU, промпт EN, ответ RU', bridgeHint: 'Промпт будет на английском, а в конец добавится жёсткая инструкция отвечать по-русски.',\n"
        "    questionsTitle: 'Уточните три момента', answerPlaceholder: 'Ваш ответ', answerContinue: 'Продолжить', answerSkip: 'Пропустить (авто)',\n"
        "    initial: 'Исходный запрос', optimized: 'После оптимизации', scoreNote: 'Оценка модели, не измерение', changelog: 'Что изменено и зачем', finalPrompt: 'Готовый промпт', framework: 'Применено',\n"
        "    compress: 'Сжать промпт', compressing: 'Сжимаю…', compressed: 'Примерно {a} → {b} токенов (−{p}%)', noGain: 'Более короткий вариант с теми же переменными получить не удалось.',\n"
        "    showOriginal: 'Исходный', showCompressed: 'Сжатый', variables: 'Переменные', variablesHint: 'Введите значения: промпт обновится, копируется итоговый текст.',\n"
        "    saved: 'Сохранено в библиотеку', folder: 'Папка', noFolder: 'Без папки', tags: 'Теги через запятую', engine: 'Движок',\n"
        "    fileTooBig: 'Файл больше 200 КБ', fileTruncated: 'Текст обрезан до лимита', fileHint: 'Загрузить .txt / .md / .csv / .json', imagesNote: 'Изображения и документы пока не поддерживаются: вставьте текст.',\n"
      ), (
        "    formatTitle: 'Формат ответа', formats: { none: 'Не задавать', table: 'Таблица', json: 'JSON (схема)', markdown_list: 'Markdown-список', prose: 'Связный текст', code: 'Готовый код', slides: 'Структура слайдов' },\n"
        "    toneTitle: 'Тон', tones: { none: 'Не задавать', academic: 'Академичный', persuasive: 'Убеждающий', friendly: 'Дружелюбный', concise: 'Лаконичный', no_yapping: 'Без воды' },\n"
        "    bridge: 'Мост языков: ввод RU, промпт EN, ответ RU', bridgeHint: 'Промпт будет на английском, а в конец добавится жёсткая инструкция отвечать по-русски.',\n"
        "    questionsTitle: 'Уточните три момента', answerPlaceholder: 'Ваш ответ', answerContinue: 'Продолжить', answerSkip: 'Пропустить (авто)',\n"
        "    changelog: 'Что изменено и зачем', finalPrompt: 'Готовый промпт', framework: 'Применено',\n"
        "    compress: 'Сжать промпт', compressing: 'Сжимаю…', compressed: 'Примерно {a} → {b} токенов (−{p}%)', noGain: 'Более короткий вариант с теми же переменными получить не удалось.',\n"
        "    showOriginal: 'Исходный', showCompressed: 'Сжатый', variables: 'Переменные', variablesHint: 'Введите значения: промпт обновится, копируется итоговый текст.',\n"
        "    saved: 'Сохранено в библиотеку', folder: 'Папка', noFolder: 'Без папки', tags: 'Теги через запятую', engine: 'Движок',\n"
        "    fileTooBig: 'Файл больше 200 КБ', fileTruncated: 'Текст обрезан до лимита', fileHint: 'Загрузить .txt / .md / .csv / .json', imagesNote: 'Изображения и документы пока не поддерживаются: вставьте текст.',\n"
      )),
      ((
        "    model: 'Модель', customModel: 'Своя модель (ID)', baseUrl: 'Custom Base URL', baseUrlHint: 'Только https. Внутренние адреса запрещены.', temperature: 'Температура', apiKey: 'Ключ API', apiKeyKept: 'Ключ сохранён', apiKeyNew: 'Введите новый ключ', apiKeyClear: 'Удалить ключ',\n"
        "    secretMissing: 'ENGINE_SECRET не задан на сервере: ключи API сохранять нельзя.', save: 'Сохранить движок', test: 'Проверить сохранённое подключение', testOk: 'Соединение работает', ms: 'мс',\n"
        "    adminOnly: 'Менять движок может только администратор', note: 'Ключ хранится на сервере в зашифрованном виде и не возвращается в браузер.',\n"
        '  },\n'
        "  empty: { glyph: '✦' },\n"
        '} as const;\n'
      ), (
        "    model: 'Модель', customModel: 'Своя модель (ID)', baseUrl: 'Custom Base URL', baseUrlHint: 'Только https. Внутренние адреса запрещены.', temperature: 'Температура', apiKey: 'Ключ API', apiKeyKept: 'Ключ сохранён', apiKeyNew: 'Введите новый ключ', apiKeyClear: 'Удалить ключ',\n"
        "    secretMissing: 'ENGINE_SECRET не задан на сервере: ключи API сохранять нельзя.', save: 'Сохранить движок', test: 'Проверить сохранённое подключение', testOk: 'Соединение работает', ms: 'мс',\n"
        "    adminOnly: 'Менять движок может только администратор', note: 'Ключ хранится на сервере в зашифрованном виде и не возвращается в браузер.',\n"
        '  },\n'
        '  home: {\n'
        "    title: 'Новый промпт', input: 'Опишите задачу или вставьте готовый промпт', placeholder: 'Например, подготовь письмо клиенту о переносе срока',\n"
        "    submit: 'Продолжить', modeLabel: 'Режим и модель', routingHint: 'В авторежиме готовый промпт оптимизируется, конкретная задача превращается в промпт, а идея с пробелами в исходных данных уточняется.',\n"
        "    inputLimit: 'Для этого режима максимум {limit} символов.', hypothesisLabel: 'Помоги проверить гипотезу',\n"
        "    hypothesis: 'Помоги проверить гипотезу: [опишите предположение и для кого оно важно]',\n"
        "    modes: { auto: 'Авто', generate: 'Генерация', magic: 'Оптимизация', clarify: 'Уточнение', template: 'Шаблон', reverse: 'Разбор стиля' },\n"
        "    examplesTitle: 'Примеры для вашей роли', before: 'Запрос', after: 'Фрагмент промпта', useExample: 'Подставить запрос',\n"
        "    roles: { marketing: 'Маркетолог', hr: 'HR', leader: 'Руководитель' },\n"
        '    examples: {\n'
        '      marketing: [\n'
        "        { before: 'Напиши пост про запуск CRM', after: 'Роль: B2B-копирайтер. Контекст: CRM для малого бизнеса. Формат: пост до 800 знаков с одним призывом.' },\n"
        "        { before: 'Перепиши письмо о новом тарифе', after: 'Контекст: письмо действующим клиентам. Ограничения: опирайся на [Условия тарифа]. Формат: тема и тело письма.' },\n"
        "        { before: 'Помоги проверить гипотезу: короткая демонстрация увеличит число заявок', after: 'Сравни две страницы с одинаковым трафиком. Укажи метрику, порог успеха и решение по итогам теста.' },\n"
        '      ],\n'
        '      hr: [\n'
        "        { before: 'Составь вопросы для собеседования маркетолога', after: 'Роль: нанимающий менеджер. Формат: таблица с вопросом, проверяемым навыком и признаком сильного ответа.' },\n"
        "        { before: 'Напиши план первой недели нового сотрудника', after: 'Контекст: [Должность сотрудника]. Формат: пять дней с задачей и ответственным. Ограничения: не выдумывай внутренние процессы.' },\n"
        "        { before: 'Подготовь письмо кандидату после собеседования', after: 'Роль: рекрутер. Ограничения: используй только [Итоги интервью]. Формат: короткое письмо со следующим шагом и сроком.' },\n"
        '      ],\n'
        '      leader: [\n'
        "        { before: 'Подготовь ответ на претензию клиента', after: 'Роль: руководитель поддержки. Контекст: [Текст претензии]. Ограничения: не обещай компенсацию без подтверждения. Формат: ответ и следующий шаг.' },\n"
        "        { before: 'Сделай повестку еженедельной встречи команды', after: 'Формат: таблица с темой, временем и решением. Ограничения: уложись в 30 минут, начни с блокирующих вопросов.' },\n"
        "        { before: 'Помоги проверить гипотезу: перенос созвона сократит время ответа клиентам', after: 'Предложи двухнедельную проверку. Опиши измерение времени ответа, допустимое отклонение и условие возврата.' },\n"
        '      ],\n'
        '    },\n'
        '  },\n'
        '  prompt: {\n'
        "    checklistReady: 'Промпт готов: 4 из 4 критериев', checklistCount: 'Чек-лист: {count} из 4 критериев',\n"
        "    criteria: { role: 'Роль задана', context: 'Контекст понятен', constraints: 'Ограничения есть', format: 'Формат вывода указан' },\n"
        "    present: 'Найдено', absent: 'Не найдено', checklistHint: 'Проверяем, явно ли эти элементы сформулированы в тексте.',\n"
        "    fields: 'Заполните переменные', saveValues: 'Сохранить значения', details: 'Детали результата', settings: 'Дополнительные настройки',\n"
        "    showDiff: 'Показать изменения', diffHint: 'Зачёркнуто — удалено. Подчёркнуто — добавлено. Проверьте важные условия перед использованием.',\n"
        "    copyOutsideDiff: 'Выберите исходный или сжатый вариант, чтобы скопировать его.', tokenCount: 'Примерно {count} токенов',\n"
        "    otherActions: 'Открыть в ИИ или выполнить здесь', copyOpen: 'Скопировать и открыть в {name}', openLink: 'Открыть сайт вручную',\n"
        "    clipboardError: 'Не удалось скопировать промпт. Выделите и скопируйте текст вручную.',\n"
        "    execute: 'Выполнить промпт здесь', executing: 'Выполняю…', executionHint: 'Промпт будет отправлен провайдеру, выбранному в настройках.',\n"
        "    streamInterrupted: 'Связь с моделью прервалась. Если запрос сохранился, результат появится в библиотеке или истории.',\n"
        "    tooLong: 'Промпт слишком длинный для запуска здесь.', answer: 'Ответ модели',\n"
        "    suggestAnswers: 'Ответь за меня', suggestionsHint: 'Модель заполнила пустые поля. Проверьте и поправьте предложения перед продолжением.',\n"
        "    editVersion: 'Редактировать и смотреть версии', editor: 'Версии промпта', history: 'История правок', version: 'Версия',\n"
        "    loadVersion: 'Вставить в редактор', older: 'Более ранние версии', saveVersion: 'Сохранить новую версию', text: 'Текст промпта',\n"
        '  },\n'
        '  team: {\n'
        "    personal: 'Личные', scope: 'Общие', readOnly: 'Только чтение', newFolder: 'Новая командная папка', manage: 'Настроить доступ',\n"
        "    emptyFolders: 'Нет доступных командных папок', emptyFoldersHint: 'Администратор портала может создать папку и назначить доступ.',\n"
        "    emptyPrompts: 'Пока нет промптов', emptyPromptsHint: 'Опубликуйте готовый промпт из оптимизатора или генератора.',\n"
        "    visibility: 'Кто может читать', restricted: 'Только назначенные сотрудники', portal: 'Все сотрудники портала',\n"
        "    readers: 'Читатели', editors: 'Редакторы', membersHint: 'Укажите ID сотрудников Bitrix24 через запятую. Редакторы могут публиковать и редактировать промпты, читатели — использовать.',\n"
        "    invalidMembers: 'Укажите числовые ID. У сотрудника должна быть одна роль в папке.',\n"
        "    promptTitle: 'Название промпта', publish: 'Опубликовать для команды', published: 'Промпт опубликован', noWritable: 'У вас нет командной папки с правом публикации.',\n"
        "    publishHint: 'Сотрудники с доступом увидят текст ниже. Значения из личных полей не передаются.',\n"
        "    confirmDelete: 'Удалить командный промпт и его историю правок?',\n"
        '  },\n'
        "  empty: { glyph: '✦' },\n"
        '} as const;\n'
      )),
    ),
    'design.md': (
      ((
        '\n'
        '### A10. Token values\n'
        '\n'
        "Superseded on 2026-11-21 by Part 0 §0.3. The source of truth is `apps/web/src/styles/tokens.css` (dark default on `:root[data-theme='dark']`, light on `:root`). The «Ноябрь» values that were listed here are retired.\n"
      ), (
        '\n'
        '### A10. Token values\n'
        '\n'
        "Superseded on 2026-11-21 by Part 0 §0.3. The source of truth is `apps/web/src/styles/tokens.css` (dark default on `:root[data-theme='dark']`, light on `:root`). The «Ноябрь» values that were listed here are retired.\n"
        '\n'
        '## Prompt workspace v1.2\n'
        '\n'
        'The [Prompt workspace specification](docs/prompt-workspace.md) records the default entry flow, routing rules, checklist, compression comparison, prompt fields, role examples and team access decisions for this version.\n'
        '\n'
        '- Use the existing Obsidian surfaces, spacing, controls and typography for the composer, result and library.\n'
        '- Keep the primary copy action adjacent to the prompt. Place model commentary, token estimates, prompt execution, external destinations and editing controls in expandable sections.\n'
        '- Put variable fields above the rendered prompt. Update the preview and copy action from the same value. Keep the original and compressed variant labels visible above the comparison.\n'
        '- Mark removed text with a strike and added text with an underline. Use the existing muted, danger and success tokens. Show the two alternatives if the diff cannot be calculated within its budget.\n'
        '- Keep shared folder visibility and user roles explicit in settings. Show a read-only indicator to readers. An editor selects a history entry and saves it as a new revision.\n'
        '- On narrow screens use the same keyboard-accessible accordions and wrapping grids. Keep the workspace in document flow for the Bitrix24 auto-height iframe.\n'
      )),
    ),
    'shared/src/index.ts': (
      ((
        "import { z } from 'zod';\n"
        '\n'
        '// ---------- constants ----------\n'
        "export const SYSTEM_IDS = ['claude', 'chatgpt', 'kimi', 'qwen', 'grok'] as const;\n"
        'export type SystemId = (typeof SYSTEM_IDS)[number];\n'
      ), (
        "import { z } from 'zod';\n"
        "import { extractPromptVariables, fillPromptVariables } from './prompt.ts';\n"
        '\n'
        '// ---------- constants ----------\n'
        "export const SYSTEM_IDS = ['claude', 'chatgpt', 'kimi', 'qwen', 'grok'] as const;\n"
        'export type SystemId = (typeof SYSTEM_IDS)[number];\n'
      )),
      ((
        '// ---------- zod schemas ----------\n'
        'export const systemIdSchema = z.enum(SYSTEM_IDS);\n'
        "export const languageSchema = z.enum(['ru', 'en']);\n"
        'export const optionsSchema = z.object({\n'
        "  task_type: z.enum(['auto', 'code', 'writing', 'analysis', 'research', 'agent', 'creative']).default('auto'),\n"
        "  detail: z.enum(['brief', 'standard', 'detailed']).default('standard'),\n"
        "  assumptions_mode: z.enum(['assume', 'questions']).default('assume'),\n"
        '  include_format: z.boolean().default(true),\n'
        '});\n'
      ), (
        '// ---------- zod schemas ----------\n'
        'export const systemIdSchema = z.enum(SYSTEM_IDS);\n'
        "export const languageSchema = z.enum(['ru', 'en']);\n"
        'export const optionsSchema = z.object({\n'
        "  task_type: z.enum(['auto', 'code', 'writing', 'analysis', 'research', 'agent', 'creative', 'hypothesis']).default('auto'),\n"
        "  detail: z.enum(['brief', 'standard', 'detailed']).default('standard'),\n"
        "  assumptions_mode: z.enum(['assume', 'questions']).default('assume'),\n"
        '  include_format: z.boolean().default(true),\n'
        '});\n'
      )),
      ((
        '  tags: string[]; is_seed: boolean; usage_count: number; variables: string[]; created_at: string; updated_at: string;\n'
        '}\n'
        '\n'
        '// ---------- template helpers ----------\n'
        'const VAR_RE = /\\{\\{\\s*([a-z0-9_]+)\\s*\\}\\}/g;\n'
        'export function extractVariables(body: string): string[] {\n'
        '  const seen = new Set<string>();\n'
        '  for (const m of body.matchAll(VAR_RE)) seen.add(m[1]!);\n'
        '  return [...seen];\n'
        '}\n'
        'export function validateTemplateVariables(body: string): { ok: boolean; error?: string; variables: string[] } {\n'
        '  const variables = extractVariables(body);\n'
        '  if (variables.length > LIMITS.maxTemplateVars) return { ok: false, error: `Too many variables (max ${LIMITS.maxTemplateVars})`, variables };\n'
        '  return { ok: true, variables };\n'
        '}\n'
        'export function substituteVariables(body: string, values: Record<string, string>): string {\n'
        "  return body.replace(VAR_RE, (_m, name: string) => (values[name] !== undefined && values[name] !== '' ? values[name]! : `{{${name}}}`));\n"
        '}\n'
        '\n'
        '// ---------- language heuristic ----------\n'
        'export function cyrillicRatio(text: string): number {\n'
        '  const letters = text.match(/[A-Za-zА-Яа-яЁё]/g) ?? [];\n'
      ), (
        '  tags: string[]; is_seed: boolean; usage_count: number; variables: string[]; created_at: string; updated_at: string;\n'
        '}\n'
        '\n'
        '// ---------- template helpers ----------\n'
        'export const extractVariables = extractPromptVariables;\n'
        'export function validateTemplateVariables(body: string): { ok: boolean; error?: string; variables: string[] } {\n'
        '  const variables = extractVariables(body);\n'
        '  if (variables.length > LIMITS.maxTemplateVars) return { ok: false, error: `Too many variables (max ${LIMITS.maxTemplateVars})`, variables };\n'
        '  return { ok: true, variables };\n'
        '}\n'
        'export const substituteVariables = fillPromptVariables;\n'
        '\n'
        '// ---------- language heuristic ----------\n'
        'export function cyrillicRatio(text: string): number {\n'
        '  const letters = text.match(/[A-Za-zА-Яа-яЁё]/g) ?? [];\n'
      )),
      ((
        "  return 'mixed';\n"
        '}\n'
        '\n'
        "export * from './optimizer.ts';\n"
      ), (
        "  return 'mixed';\n"
        '}\n'
        '\n'
        "export * from './optimizer.ts';\n"
        "export * from './prompt.ts';\n"
        "export * from './team.ts';\n"
      )),
    ),
    'shared/src/optimizer.ts': (
      ((
        "import { z } from 'zod';\n"
        '\n'
        '// ---------- constants ----------\n'
        "export const OPT_WORKFLOWS = ['magic', 'clarify', 'template', 'reverse'] as const;\n"
        'export type OptWorkflow = (typeof OPT_WORKFLOWS)[number];\n'
      ), (
        "import { z } from 'zod';\n"
        "import { extractPromptVariables, fillPromptVariables, PROMPT_BODY_MAX } from './prompt.ts';\n"
        '\n'
        '// ---------- constants ----------\n'
        "export const OPT_WORKFLOWS = ['magic', 'clarify', 'template', 'reverse'] as const;\n"
        'export type OptWorkflow = (typeof OPT_WORKFLOWS)[number];\n'
      )),
      ((
        'export const OPT_PRESETS = [...GOAL_PRESETS, ...FRAMEWORK_PRESETS] as const;\n'
        'export type OptPreset = (typeof OPT_PRESETS)[number];\n'
        "export const OUTPUT_FORMATS = ['none', 'table', 'json', 'markdown_list', 'prose', 'code', 'slides'] as const;\n"
        "export const TONES = ['none', 'academic', 'persuasive', 'friendly', 'concise', 'no_yapping'] as const;\n"
        'export const OPT_LIMITS = { rawMin: 3, rawMax: 12000, answerMax: 1000, promptMax: 20000, questions: 3, folderName: 60, variableValue: 2000, maxFolders: 40 } as const;\n'
        'export const DEFAULT_FOLDERS = [\n'
        "  { key: 'work', name: 'Работа' }, { key: 'marketing', name: 'Маркетинг' }, { key: 'coding', name: 'Код' },\n"
        '] as const;\n'
        '\n'
      ), (
        'export const OPT_PRESETS = [...GOAL_PRESETS, ...FRAMEWORK_PRESETS] as const;\n'
        'export type OptPreset = (typeof OPT_PRESETS)[number];\n'
        "export const OUTPUT_FORMATS = ['none', 'table', 'json', 'markdown_list', 'prose', 'code', 'slides'] as const;\n"
        "export const TONES = ['none', 'academic', 'persuasive', 'friendly', 'concise', 'no_yapping'] as const;\n"
        'export const OPT_LIMITS = { rawMin: 3, rawMax: 12000, answerMax: 1000, promptMax: PROMPT_BODY_MAX, questions: 3, folderName: 60, variableValue: 2000, maxFolders: 40 } as const;\n'
        'export const DEFAULT_FOLDERS = [\n'
        "  { key: 'work', name: 'Работа' }, { key: 'marketing', name: 'Маркетинг' }, { key: 'coding', name: 'Код' },\n"
        '] as const;\n'
        '\n'
      )),
      ((
        'const score = z.coerce.number().transform((n) => Math.min(10, Math.max(1, Math.round(n * 10) / 10)));\n'
        'const textList = z.array(z.string().trim().min(1).max(600)).max(12);\n'
        '/** What the engine must return for an optimization run (parsed and validated server-side). */\n'
        'export const optimizerOutputSchema = z.object({\n'
        "  initial_score: score, initial_critique: z.string().trim().max(600).default(''), optimized_score: score,\n"
        '  changelog_explanation: textList.min(1), final_prompt: z.string().trim().min(1).max(OPT_LIMITS.promptMax),\n'
        "  framework_used: z.string().trim().max(60).default(''),\n"
        '});\n'
        'export type OptimizerOutput = z.infer<typeof optimizerOutputSchema>;\n'
      ), (
        'const score = z.coerce.number().transform((n) => Math.min(10, Math.max(1, Math.round(n * 10) / 10)));\n'
        'const textList = z.array(z.string().trim().min(1).max(600)).max(12);\n'
        '/** What the engine must return for an optimization run (parsed and validated server-side). */\n'
        'export const optimizerOutputSchema = z.object({\n'
        "  initial_score: score.optional(), initial_critique: z.string().trim().max(600).default(''), optimized_score: score.optional(),\n"
        '  changelog_explanation: textList.min(1), final_prompt: z.string().trim().min(1).max(OPT_LIMITS.promptMax),\n'
        "  framework_used: z.string().trim().max(60).default(''),\n"
        '});\n'
        'export type OptimizerOutput = z.infer<typeof optimizerOutputSchema>;\n'
      )),
      ((
        '}\n'
        'export interface FolderDTO { id: string; name: string; is_default: boolean; count: number }\n'
        '\n'
        '// ---------- helpers shared by server and UI ----------\n'
        '/** Bracket variables as in the spec: [Insert Topic]. Links like [text](url) and nested or empty brackets are ignored. */\n'
        'const BR_RE = /(?<!\\[)\\[([^\\[\\]\\n]{2,60})\\](?![(\\]])/g;\n'
        'export function extractBracketVars(text: string): string[] {\n'
        '  const seen = new Set<string>();\n'
        '  for (const m of text.matchAll(BR_RE)) { const v = m[1]!.trim(); if (/\\p{L}/u.test(v)) seen.add(v); }\n'
        '  return [...seen].slice(0, 20);\n'
        '}\n'
        'export function substituteBracketVars(text: string, values: Record<string, string>): string {\n'
        '  return text.replace(BR_RE, (match, name: string) => {\n'
        '    const key = name.trim();\n'
        "    return Object.hasOwn(values, key) && values[key] !== '' ? values[key]! : match;\n"
        '  });\n'
        '}\n'
        '/** Rough token estimate without a tokenizer: about 4 Latin characters, or 2.5 Cyrillic characters, per token. Always shown as approximate. */\n'
        'export function estimateTokens(text: string): number {\n'
        '  let latin = 0; let cyr = 0; let other = 0;\n'
        '  for (const ch of text) {\n'
      ), (
        '}\n'
        'export interface FolderDTO { id: string; name: string; is_default: boolean; count: number }\n'
        '\n'
        '// ---------- helpers shared by server and UI ----------\n'
        '// Historical names kept for existing callers.\n'
        'export const extractBracketVars = (text: string) => extractPromptVariables(text).slice(0, 20);\n'
        'export const substituteBracketVars = fillPromptVariables;\n'
        '/** Rough token estimate without a tokenizer: about 4 Latin characters, or 2.5 Cyrillic characters, per token. Always shown as approximate. */\n'
        'export function estimateTokens(text: string): number {\n'
        '  let latin = 0; let cyr = 0; let other = 0;\n'
        '  for (const ch of text) {\n'
      )),
    ),
    'tests/core.test.ts': (
      ((
        "import { LIMITS } from '../shared/src/index.ts';\n"
        '\n'
        "describe('template variables', () => {\n"
        "  it('extracts unique names and tolerates spaces', () => {\n"
        "    expect(extractVariables('a {{ x }} b {{x}} c {{y_2}} {{Bad}}')).toEqual(['x', 'y_2']);\n"
        '  });\n'
        "  it('substitutes known values and keeps unknown placeholders', () => {\n"
        "    expect(substituteVariables('Hi {{name}}, {{ city }}', { name: 'Ann' })).toBe('Hi Ann, {{city}}');\n"
        '  });\n'
        "  it('rejects more than 12 variables', () => {\n"
        "    const body = Array.from({ length: 13 }, (_, i) => `{{v${i}}}`).join(' ');\n"
        '    expect(validateTemplateVariables(body).ok).toBe(false);\n'
      ), (
        "import { LIMITS } from '../shared/src/index.ts';\n"
        '\n'
        "describe('template variables', () => {\n"
        "  it('extracts unique names and tolerates spaces', () => {\n"
        "    expect(extractVariables('a {{ x }} b {{x}} c {{y_2}} {{Клиент}}')).toEqual(['x', 'y_2', 'Клиент']);\n"
        '  });\n'
        "  it('substitutes known values and keeps unknown placeholders', () => {\n"
        "    expect(substituteVariables('Hi {{name}}, {{ city }}', { name: 'Ann' })).toBe('Hi Ann, {{ city }}');\n"
        '  });\n'
        "  it('rejects more than 12 variables', () => {\n"
        "    const body = Array.from({ length: 13 }, (_, i) => `{{v${i}}}`).join(' ');\n"
        '    expect(validateTemplateVariables(body).ok).toBe(false);\n'
      )),
    ),
    'tests/optimizer.test.ts': (
      ((
        "    expect(r.body.variables).toEqual(['Article Topic', 'Target Audience']);\n"
        "    const p = await call('PATCH', `/api/optimizer/items/${r.body.id}`, U, { var_values: { 'Article Topic': 'cats' } });\n"
        "    expect(p.body.var_values).toEqual({ 'Article Topic': 'cats' });\n"
        "    const magic = await call('POST', '/api/optimizer/run', U, { workflow: 'magic', raw_input: 'Статьи для блога' });\n"
        '    expect(magic.body.variables).toEqual([]);\n'
        '  });\n'
        "  it('clarifier asks 3 questions, then synthesizes; skip uses auto-fill; cannot be answered twice', async () => {\n"
        '    const calls: Calls = { systems: [], users: [] }; const { call } = await mk({}, calls);\n'
        "    const q = await call('POST', '/api/optimizer/run', U, { workflow: 'clarify', raw_input: 'Составь план тренировок' });\n"
      ), (
        "    expect(r.body.variables).toEqual(['Article Topic', 'Target Audience']);\n"
        "    const p = await call('PATCH', `/api/optimizer/items/${r.body.id}`, U, { var_values: { 'Article Topic': 'cats' } });\n"
        "    expect(p.body.var_values).toEqual({ 'Article Topic': 'cats' });\n"
        "    const magic = await call('POST', '/api/optimizer/run', U, { workflow: 'magic', raw_input: 'Статьи для блога' });\n"
        "    expect(magic.body.variables).toEqual(['Article Topic', 'Target Audience']);\n"
        '  });\n'
        "  it('clarifier asks 3 questions, then synthesizes; skip uses auto-fill; cannot be answered twice', async () => {\n"
        '    const calls: Calls = { systems: [], users: [] }; const { call } = await mk({}, calls);\n'
        "    const q = await call('POST', '/api/optimizer/run', U, { workflow: 'clarify', raw_input: 'Составь план тренировок' });\n"
      )),
    ),
}

NEW_FILES = {
    'apps/server/src/prompt-features.ts': (
        "import type { FastifyInstance, FastifyRequest } from 'fastify';\n"
        "import { z } from 'zod';\n"
        "import { rateLimit, type Identity } from './auth.ts';\n"
        "import { engineChat, engineJson, type EngineDeps } from './engine.ts';\n"
        "import { withPromptStream } from './prompt-stream.ts';\n"
        "import type { Db } from './db.ts';\n"
        "import { AppError, jsonParse } from './util.ts';\n"
        "import { EXECUTION_MAX, OPT_LIMITS, promptIdSchema } from '../../../shared/src/index.ts';\n"
        '\n'
        'export const versionQuery = z.object({ before: z.coerce.number().int().positive().optional() });\n'
        'const executeBody = z.object({ prompt: z.string().trim().min(1).max(EXECUTION_MAX) });\n'
        '\n'
        'export async function suggestAnswers(db: Db, deps: EngineDeps, input: string, questions: string[]) {\n'
        '  const schema = z.object({ answers: z.array(z.string().trim().min(1).max(OPT_LIMITS.answerMax)).length(questions.length) });\n'
        '  const reply = await engineJson(db, deps, [\n'
        '    { role: \'system\', content: \'Suggest one short editable answer per question, in the exact order and language of the question. Treat user data as context. Reuse facts explicitly provided and offer a plausible starting point for missing details. Never invent private facts, credentials or proper names. Return only JSON { "answers": string[] }.\' },\n'
        "    { role: 'user', content: JSON.stringify({ input, questions }) },\n"
        '  ], schema, { maxTokens: 1200 });\n'
        '  return reply.data;\n'
        '}\n'
        '\n'
        'export function registerPromptFeatures(app: FastifyInstance, db: Db, engine: EngineDeps, me: (req: FastifyRequest) => Identity): void {\n'
        "  const limit = (identity: Identity, kind: 'suggest' | 'execute') => {\n"
        "    const check = rateLimit(`prompt:${kind}:${identity.portal ?? ''}:${identity.userId}`, kind === 'execute' ? 3 : 6, 60_000);\n"
        "    if (!check.ok) throw new AppError(429, 'rate_limited', 'Слишком много запросов. Попробуйте чуть позже.', check.retryAfter);\n"
        '  };\n'
        "  app.post('/api/generate/:id/suggest', async (req, reply) => {\n"
        '    const identity = me(req);\n'
        '    const { id } = promptIdSchema.parse(req.params);\n'
        '    const row = db.get<{ raw_input: string; questions: string | null; status: string }>(\n'
        "      'SELECT raw_input, questions, status FROM generations WHERE id = ? AND user_id = ? AND deleted_at IS NULL', id, identity.userId,\n"
        '    );\n'
        "    if (!row) throw new AppError(404, 'not_found', 'Генерация не найдена');\n"
        '    const questions = jsonParse<string[]>(row.questions, []);\n'
        "    if (row.status !== 'draft_questions' || !questions.length) throw new AppError(409, 'not_awaiting_answers', 'Уточнение уже завершено');\n"
        "    limit(identity, 'suggest');\n"
        '    return withPromptStream(req, reply, () => suggestAnswers(db, engine, row.raw_input, questions));\n'
        '  });\n'
        "  app.post('/api/prompts/execute', async (req, reply) => {\n"
        '    const { prompt } = executeBody.parse(req.body);\n'
        '    const identity = me(req);\n'
        "    if (identity.userId.startsWith('share:')) throw new AppError(403, 'member_required', 'Для запуска нужен аккаунт сотрудника');\n"
        "    limit(identity, 'execute');\n"
        '    return withPromptStream(req, reply, async () => {\n'
        "      const response = await engineChat(db, engine, [{ role: 'user', content: prompt }], { maxTokens: 3000 });\n"
        '      return { text: response.content, model: response.model };\n'
        '    });\n'
        '  });\n'
        '}\n'
    ),
    'apps/server/src/prompt-stream.ts': (
        "import type { FastifyReply, FastifyRequest } from 'fastify';\n"
        "import { AppError, log } from './util.ts';\n"
        "import { VibeError } from './vibe.ts';\n"
        '\n'
        '/** Slow LLM calls send an early event and heartbeats for the Bitrix24 Gateway. */\n'
        'export async function withPromptStream<T>(req: FastifyRequest, reply: FastifyReply, run: () => Promise<T>): Promise<T | void> {\n'
        "  if (!req.headers.accept?.includes('text/event-stream')) return run();\n"
        '  reply.hijack();\n'
        '  const stream = reply.raw;\n'
        '  stream.writeHead(200, {\n'
        "    'Content-Type': 'text/event-stream; charset=utf-8',\n"
        "    'Cache-Control': 'no-store, no-transform',\n"
        "    'X-Accel-Buffering': 'no',\n"
        "    'X-Content-Type-Options': 'nosniff',\n"
        '  });\n'
        '  const send = (event: string, payload: unknown) => {\n'
        '    if (!stream.destroyed && !stream.writableEnded) stream.write(`event: ${event}\\ndata: ${JSON.stringify(payload)}\\n\\n`);\n'
        '  };\n'
        "  send('working', {});\n"
        "  const heartbeat = setInterval(() => { send('working', {}); }, 8_000);\n"
        "  stream.once('close', () => clearInterval(heartbeat));\n"
        '  try {\n'
        "    send('result', await run());\n"
        '  } catch (error) {\n'
        '    if (error instanceof AppError) {\n'
        "      send('failure', { status: error.status, code: error.code, message: error.message, retryAfter: error.retryAfter });\n"
        '    } else if (error instanceof VibeError) {\n'
        "      const quota = error.kind === 'quota';\n"
        "      send('failure', { status: quota ? 402 : 502, code: quota ? 'ai_quota_exhausted' : 'upstream_error',\n"
        "        message: quota ? 'Квота ИИ исчерпана' : 'Сервис ИИ временно недоступен', retryAfter: error.retryAfter });\n"
        '    } else {\n'
        "      log.error('prompt stream failed', { requestId: req.id });\n"
        "      send('failure', { status: 500, code: 'internal_error', message: 'Внутренняя ошибка сервера' });\n"
        '    }\n'
        '  } finally {\n'
        '    clearInterval(heartbeat);\n'
        '    if (!stream.destroyed && !stream.writableEnded) stream.end();\n'
        '  }\n'
        '}\n'
    ),
    'apps/server/src/prompt-versions.ts': (
        "import type { Db } from './db.ts';\n"
        "import { AppError, nowIso } from './util.ts';\n"
        "import type { PromptVersion, PromptVersions } from '../../../shared/src/prompt.ts';\n"
        '\n'
        "type Scope = 'optimization' | 'template' | 'team';\n"
        'type Source = { id: string; body: string; created_at: string };\n'
        '\n'
        'export function currentVersion(db: Db, scope: Scope, id: string): number {\n'
        '  return db.get<{ version: number }>(\n'
        "    'SELECT version FROM prompt_versions WHERE scope = ? AND prompt_id = ? ORDER BY version DESC LIMIT 1', scope, id,\n"
        '  )?.version ?? 1;\n'
        '}\n'
        '\n'
        'export function listVersionsForPrompt(db: Db, scope: Scope, source: Source, before?: number): PromptVersions {\n'
        '  const version = currentVersion(db, scope, source.id);\n'
        '  if (version === 1) {\n'
        '    return { current_version: version, items: before === undefined || before > 1 ? [{ version, body: source.body, created_at: source.created_at }] : [] };\n'
        '  }\n'
        '  const items = db.all<PromptVersion>(\n'
        "    'SELECT version, body, created_at FROM prompt_versions WHERE scope = ? AND prompt_id = ? AND version < ? ORDER BY version DESC LIMIT 20',\n"
        '    scope, source.id, before ?? version + 1,\n'
        '  );\n'
        '  return { current_version: version, items };\n'
        '}\n'
        '\n'
        '/** Call inside the transaction that updates the current prompt. */\n'
        'export function appendPromptVersion(db: Db, scope: Scope, source: Source, body: string, expected?: number): number {\n'
        '  const version = currentVersion(db, scope, source.id);\n'
        '  if (expected !== undefined && expected !== version) {\n'
        "    throw new AppError(409, 'version_conflict', 'Промпт уже изменён. Откройте актуальную версию.');\n"
        '  }\n'
        '  if (body === source.body) return version;\n'
        "  const sql = 'INSERT INTO prompt_versions(scope, prompt_id, version, body, created_at) VALUES (?, ?, ?, ?, ?)';\n"
        '  if (version === 1) db.run(sql, scope, source.id, 1, source.body, source.created_at);\n'
        '  db.run(sql, scope, source.id, version + 1, body, nowIso());\n'
        '  return version + 1;\n'
        '}\n'
        '\n'
        'export function deletePromptVersions(db: Db, scope: Scope, id: string): void {\n'
        "  db.run('DELETE FROM prompt_versions WHERE scope = ? AND prompt_id = ?', scope, id);\n"
        '}\n'
    ),
    'apps/server/src/team-routes.ts': (
        "import type { FastifyInstance, FastifyRequest } from 'fastify';\n"
        "import { z } from 'zod';\n"
        "import type { Identity } from './auth.ts';\n"
        "import { config } from './config.ts';\n"
        "import type { Db } from './db.ts';\n"
        "import { versionQuery } from './prompt-features.ts';\n"
        "import { appendPromptVersion, currentVersion, deletePromptVersions, listVersionsForPrompt } from './prompt-versions.ts';\n"
        "import { AppError, nowIso, uid } from './util.ts';\n"
        "import { promptRevisionSchema, teamFolderInput, teamPromptInput, type TeamFolder, type TeamFolderInput, type TeamPrompt } from '../../../shared/src/index.ts';\n"
        '\n'
        'const folderParam = z.object({ folderId: z.string().min(1).max(60) });\n'
        'const itemParams = folderParam.extend({ id: z.string().min(1).max(60) });\n'
        'const pageSchema = z.object({ page: z.coerce.number().int().min(1).max(10000).default(1) });\n'
        'const portalId = z.uuid();\n'
        "const NOT_FOUND = () => new AppError(404, 'not_found', 'Папка или промпт не найдены');\n"
        'type Principal = { portal: string; user: string; admin: boolean };\n'
        "type FolderRow = { id: string; name: string; visibility: TeamFolder['visibility']; role: 'reader' | 'editor' | null };\n"
        "type PromptRow = Omit<TeamPrompt, 'version'> & { created_at: string };\n"
        '\n'
        'function principal(req: FastifyRequest, identity: Identity): Principal | undefined {\n'
        "  if (config.devAuthBypass) return { portal: 'dev.local', user: identity.userId, admin: true };\n"
        '  // The Gateway sends the portal UUID separately from the account domain.\n'
        "  const portal = portalId.safeParse(req.headers['x-vibe-portal-id']);\n"
        "  const user = req.headers['x-vibe-user-id'];\n"
        "  if (!portal.success || typeof user !== 'string' || !/^\\d{1,18}$/.test(user) || user !== identity.userId) return undefined;\n"
        "  return { portal: portal.data.toLowerCase(), user, admin: req.headers['x-vibe-user-role'] === 'ADMIN' };\n"
        '}\n'
        '\n'
        'function canRead(folder: FolderRow, who: Principal): boolean {\n'
        "  return who.admin || folder.visibility === 'portal' || folder.role !== null;\n"
        '}\n'
        'function canEdit(folder: FolderRow, who: Principal): boolean {\n'
        "  return who.admin || folder.role === 'editor';\n"
        '}\n'
        'function asFolder(folder: FolderRow, who: Principal): TeamFolder {\n'
        '  return { id: folder.id, name: folder.name, visibility: folder.visibility, can_edit: canEdit(folder, who) };\n'
        '}\n'
        '\n'
        'export function registerTeamRoutes(app: FastifyInstance, db: Db, me: (req: FastifyRequest) => Identity): void {\n'
        '  function requirePrincipal(req: FastifyRequest): Principal {\n'
        '    const who = principal(req, me(req));\n'
        "    if (!who) throw new AppError(403, 'portal_required', 'Откройте приложение как сотрудник портала Bitrix24');\n"
        '    return who;\n'
        '  }\n'
        '  function requireAdmin(req: FastifyRequest): Principal {\n'
        '    const who = requirePrincipal(req);\n'
        "    if (!who.admin) throw new AppError(403, 'admin_required', 'Требуются права администратора портала');\n"
        '    return who;\n'
        '  }\n'
        '  function folderRows(who: Principal, id?: string): FolderRow[] {\n'
        '    return db.all<FolderRow>(\n'
        '      `SELECT f.id, f.name, f.visibility, m.role FROM team_folders f\n'
        '       LEFT JOIN team_folder_members m ON m.folder_id = f.id AND m.user_id = ?\n'
        "       WHERE f.portal_id = ?${id ? ' AND f.id = ?' : ''} ORDER BY f.name, f.id`,\n"
        '      who.user, who.portal, ...(id ? [id] : []),\n'
        '    );\n'
        '  }\n'
        '  function folder(who: Principal, id: string, write = false): FolderRow {\n'
        '    const current = folderRows(who, id)[0];\n'
        '    if (!current || !canRead(current, who)) throw NOT_FOUND();\n'
        "    if (write && !canEdit(current, who)) throw new AppError(403, 'read_only', 'Папка доступна только для чтения');\n"
        '    return current;\n'
        '  }\n'
        '  function item(folderId: string, id: string): PromptRow {\n'
        "    const row = db.get<PromptRow>('SELECT id, title, body, created_at, updated_at FROM team_prompts WHERE id = ? AND folder_id = ?', id, folderId);\n"
        '    if (!row) throw NOT_FOUND();\n'
        '    return row;\n'
        '  }\n'
        '  function toPrompt(row: PromptRow): TeamPrompt {\n'
        "    return { id: row.id, title: row.title, body: row.body, updated_at: row.updated_at, version: currentVersion(db, 'team', row.id) };\n"
        '  }\n'
        '  function writeFolder(who: Principal, id: string, body: TeamFolderInput, create: boolean): TeamFolder {\n'
        '    return db.tx(() => {\n'
        "      if (db.get('SELECT 1 FROM team_folders WHERE portal_id = ? AND name = ? AND id <> ?', who.portal, body.name, id)) {\n"
        "        throw new AppError(409, 'folder_exists', 'Папка с таким названием уже есть');\n"
        '      }\n'
        '      if (create) {\n'
        "        const count = db.get<{ n: number }>('SELECT COUNT(*) AS n FROM team_folders WHERE portal_id = ?', who.portal)!.n;\n"
        "        if (count >= 100) throw new AppError(409, 'folder_limit', 'Достигнут лимит командных папок');\n"
        "        db.run('INSERT INTO team_folders(id, portal_id, name, visibility) VALUES (?, ?, ?, ?)', id, who.portal, body.name, body.visibility);\n"
        '      } else {\n'
        '        folder(who, id, true);\n'
        "        db.run('UPDATE team_folders SET name = ?, visibility = ? WHERE id = ? AND portal_id = ?', body.name, body.visibility, id, who.portal);\n"
        "        db.run('DELETE FROM team_folder_members WHERE folder_id = ?', id);\n"
        '      }\n'
        '      for (const member of body.members) {\n'
        "        db.run('INSERT INTO team_folder_members(folder_id, user_id, role) VALUES (?, ?, ?)', id, member.user_id, member.role);\n"
        '      }\n'
        '      return asFolder(folder(who, id), who);\n'
        '    });\n'
        '  }\n'
        '\n'
        "  app.get('/api/team/folders', async (req) => {\n"
        '    const who = principal(req, me(req));\n'
        '    return who ? { items: folderRows(who).filter((row) => canRead(row, who)).map((row) => asFolder(row, who)), can_manage: who.admin }\n'
        '      : { items: [], can_manage: false };\n'
        '  });\n'
        "  app.post('/api/team/folders', async (req) => writeFolder(requireAdmin(req), uid(), teamFolderInput.parse(req.body), true));\n"
        "  app.get('/api/team/folders/:folderId/settings', async (req) => {\n"
        '    const who = requireAdmin(req);\n'
        '    const row = folder(who, folderParam.parse(req.params).folderId);\n'
        "    const members = db.all<TeamFolderInput['members'][number]>('SELECT user_id, role FROM team_folder_members WHERE folder_id = ? ORDER BY user_id', row.id);\n"
        '    return { name: row.name, visibility: row.visibility, members };\n'
        '  });\n'
        "  app.put('/api/team/folders/:folderId/settings', async (req) =>\n"
        '    writeFolder(requireAdmin(req), folderParam.parse(req.params).folderId, teamFolderInput.parse(req.body), false));\n'
        '\n'
        "  app.get('/api/team/folders/:folderId/prompts', async (req) => {\n"
        '    const row = folder(requirePrincipal(req), folderParam.parse(req.params).folderId);\n'
        '    const { page } = pageSchema.parse(req.query);\n'
        '    const rows = db.all<{ id: string; title: string; preview: string; updated_at: string; version: number }>(\n'
        '      `SELECT p.id, p.title, substr(p.body, 1, 220) AS preview, p.updated_at,\n'
        "        COALESCE((SELECT MAX(v.version) FROM prompt_versions v WHERE v.scope = 'team' AND v.prompt_id = p.id), 1) AS version\n"
        '       FROM team_prompts p WHERE p.folder_id = ? ORDER BY p.updated_at DESC, p.id LIMIT 21 OFFSET ?`,\n'
        '      row.id, (page - 1) * 20,\n'
        '    );\n'
        '    return { items: rows.slice(0, 20), has_more: rows.length > 20 };\n'
        '  });\n'
        "  app.post('/api/team/folders/:folderId/prompts', async (req) => {\n"
        '    const row = folder(requirePrincipal(req), folderParam.parse(req.params).folderId, true);\n'
        '    const { title, body } = teamPromptInput.parse(req.body);\n'
        '    const id = uid();\n'
        '    const now = nowIso();\n'
        "    db.run('INSERT INTO team_prompts(id, folder_id, title, body, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)', id, row.id, title, body, now, now);\n"
        '    return toPrompt(item(row.id, id));\n'
        '  });\n'
        "  app.get('/api/team/folders/:folderId/prompts/:id', async (req) => {\n"
        '    const params = itemParams.parse(req.params);\n'
        '    folder(requirePrincipal(req), params.folderId);\n'
        '    return toPrompt(item(params.folderId, params.id));\n'
        '  });\n'
        "  app.get('/api/team/folders/:folderId/prompts/:id/versions', async (req) => {\n"
        '    const params = itemParams.parse(req.params);\n'
        '    folder(requirePrincipal(req), params.folderId, true);\n'
        "    return listVersionsForPrompt(db, 'team', item(params.folderId, params.id), versionQuery.parse(req.query).before);\n"
        '  });\n'
        "  app.put('/api/team/folders/:folderId/prompts/:id', async (req) => {\n"
        '    const params = itemParams.parse(req.params);\n'
        '    const who = requirePrincipal(req);\n'
        '    const { body, expected_version } = promptRevisionSchema.parse(req.body);\n'
        '    return db.tx(() => {\n'
        '      folder(who, params.folderId, true);\n'
        '      const old = item(params.folderId, params.id);\n'
        "      appendPromptVersion(db, 'team', old, body, expected_version);\n"
        "      if (old.body !== body) db.run('UPDATE team_prompts SET body = ?, updated_at = ? WHERE id = ?', body, nowIso(), old.id);\n"
        '      return toPrompt(item(params.folderId, params.id));\n'
        '    });\n'
        '  });\n'
        "  app.delete('/api/team/folders/:folderId/prompts/:id', async (req) => {\n"
        '    const params = itemParams.parse(req.params);\n'
        '    const who = requirePrincipal(req);\n'
        '    db.tx(() => {\n'
        '      folder(who, params.folderId, true);\n'
        '      const old = item(params.folderId, params.id);\n'
        "      deletePromptVersions(db, 'team', old.id);\n"
        "      db.run('DELETE FROM team_prompts WHERE id = ?', old.id);\n"
        '    });\n'
        '    return { ok: true };\n'
        '  });\n'
        '}\n'
    ),
    'apps/web/src/components/ClarificationForm.tsx': (
        "import { useId, useState, type Dispatch, type SetStateAction } from 'react';\n"
        "import { OPT_LIMITS } from '../../../../shared/src/optimizer.ts';\n"
        "import { postPrompt } from '../api.ts';\n"
        "import { t } from '../strings.ru.ts';\n"
        "import { Spinner } from '../ui.tsx';\n"
        '\n'
        'export function ClarificationForm({ questions, answers, setAnswers, suggestUrl, busy, onContinue, onSkip }: {\n'
        '  questions: string[];\n'
        '  answers: string[];\n'
        '  setAnswers: Dispatch<SetStateAction<string[]>>;\n'
        '  suggestUrl: string;\n'
        '  busy: boolean;\n'
        '  onContinue: () => void;\n'
        '  onSkip?: () => void;\n'
        '}) {\n'
        '  const prefix = useId();\n'
        '  const [suggesting, setSuggesting] = useState(false);\n'
        '  const [generated, setGenerated] = useState(false);\n'
        "  const [error, setError] = useState('');\n"
        '  async function suggest() {\n'
        '    setSuggesting(true);\n'
        "    setError('');\n"
        '    try {\n'
        '      const reply = await postPrompt<{ answers: string[] }>(suggestUrl);\n'
        "      setAnswers((current) => questions.map((_, index) => current[index]?.trim() ? current[index]! : reply.answers[index] ?? ''));\n"
        '      setGenerated(true);\n'
        '    } catch (problem) {\n'
        '      setError(problem instanceof Error ? problem.message : t.common.error);\n'
        '    } finally {\n'
        '      setSuggesting(false);\n'
        '    }\n'
        '  }\n'
        '  return (\n'
        '    <section className="surface card col" aria-labelledby={`${prefix}-heading`}>\n'
        '      <h2 id={`${prefix}-heading`}>{t.opt.questionsTitle}</h2>\n'
        '      {questions.map((question, index) => {\n'
        '        const id = `${prefix}-${index}`;\n'
        '        return <div key={id}>\n'
        '          <label className="label" htmlFor={id}>{question}</label>\n'
        '          <textarea id={id} className="field" rows={2} maxLength={OPT_LIMITS.answerMax} value={answers[index] ?? \'\'}\n'
        "            onChange={(event) => setAnswers(questions.map((_, j) => j === index ? event.target.value : answers[j] ?? ''))} />\n"
        '        </div>;\n'
        '      })}\n'
        '      {generated && <p className="small tx2" role="status">{t.prompt.suggestionsHint}</p>}\n'
        '      {error && <p className="banner err" role="alert">{error}</p>}\n'
        '      <div className="row wrap">\n'
        '        <button className="btn primary" disabled={busy || suggesting} onClick={onContinue}>{busy && <Spinner />}{t.opt.answerContinue}</button>\n'
        '        <button className="btn" disabled={busy || suggesting || !questions.some((_, i) => !answers[i]?.trim())} onClick={() => { void suggest(); }}>\n'
        '          {suggesting && <Spinner />}{t.prompt.suggestAnswers}\n'
        '        </button>\n'
        '        {onSkip && <button className="btn sm ghost" disabled={busy || suggesting} onClick={onSkip}>{t.opt.answerSkip}</button>}\n'
        '      </div>\n'
        '    </section>\n'
        '  );\n'
        '}\n'
    ),
    'apps/web/src/components/PromptActions.tsx': (
        "import { useState } from 'react';\n"
        "import { ExternalLink, Play } from 'lucide-react';\n"
        "import { EXECUTION_MAX, type PromptExecution } from '../../../../shared/src/prompt.ts';\n"
        "import { postPrompt } from '../api.ts';\n"
        "import { t } from '../strings.ru.ts';\n"
        "import { CopyButton, Spinner, copyText, useToast } from '../ui.tsx';\n"
        '\n'
        'const LINKS = {\n'
        "  ChatGPT: 'https://chatgpt.com/',\n"
        "  Claude: 'https://claude.ai/new',\n"
        "  Qwen: 'https://chat.qwen.ai/',\n"
        '} as const;\n'
        '\n'
        'export function PromptActions({ text }: { text: string }) {\n'
        '  const toast = useToast();\n'
        '  const [execution, setExecution] = useState<{ prompt: string; result: PromptExecution } | null>(null);\n'
        '  const [busy, setBusy] = useState(false);\n'
        "  const [problem, setProblem] = useState('');\n"
        '  const [fallback, setFallback] = useState<string | null>(null);\n'
        '  const [copying, setCopying] = useState(false);\n'
        '\n'
        '  const openAfterCopy = async (url: string) => {\n'
        '    const copied = copyText(text);\n'
        '    let tab: Window | null = null;\n'
        '    try {\n'
        "      tab = window.open('about:blank', '_blank');\n"
        '      if (tab) tab.opener = null;\n'
        '    } catch {\n'
        '      tab?.close();\n'
        '      tab = null;\n'
        '    }\n'
        '    setCopying(true);\n'
        '    setFallback(null);\n'
        '    try {\n'
        '      if (!await copied) {\n'
        '        tab?.close();\n'
        "        toast(t.prompt.clipboardError, 'err');\n"
        '        return;\n'
        '      }\n'
        '      if (tab && !tab.closed) {\n'
        '        try { tab.location.replace(url); }\n'
        '        catch { tab.close(); setFallback(url); }\n'
        '      } else {\n'
        '        setFallback(url);\n'
        '      }\n'
        "      toast(t.common.copied, 'ok');\n"
        '    } finally {\n'
        '      setCopying(false);\n'
        '    }\n'
        '  };\n'
        '\n'
        '  const execute = async () => {\n'
        '    setBusy(true);\n'
        "    setProblem('');\n"
        '    setExecution(null);\n'
        '    try {\n'
        "      const result = await postPrompt<PromptExecution>('/api/prompts/execute', { prompt: text });\n"
        '      setExecution({ prompt: text, result });\n'
        '    } catch (error) {\n'
        '      setProblem(error instanceof Error ? error.message : t.common.error);\n'
        '    } finally {\n'
        '      setBusy(false);\n'
        '    }\n'
        '  };\n'
        '\n'
        '  return (\n'
        '    <div className="col prompt-actions">\n'
        '      <div className="row wrap"><CopyButton text={text} primary /></div>\n'
        '      <details className="result-details">\n'
        '        <summary>{t.prompt.otherActions}</summary>\n'
        '        <div className="col">\n'
        '          <div className="row wrap">\n'
        '            {Object.entries(LINKS).map(([name, url]) => (\n'
        '              <button key={name} className="btn sm" disabled={copying} onClick={() => { void openAfterCopy(url); }}>\n'
        "                <ExternalLink size={14} aria-hidden />{t.prompt.copyOpen.replace('{name}', name)}\n"
        '              </button>\n'
        '            ))}\n'
        '            {fallback && <a className="btn sm" href={fallback} target="_blank" rel="noopener noreferrer">{t.prompt.openLink}</a>}\n'
        '          </div>\n'
        '          <div className="row wrap">\n'
        '            <button className="btn" disabled={busy || !text.trim() || text.length > EXECUTION_MAX} onClick={() => { void execute(); }}>\n'
        '              {busy ? <Spinner /> : <Play size={14} aria-hidden />}{busy ? t.prompt.executing : t.prompt.execute}\n'
        '            </button>\n'
        '            <span className="small tx3">{text.length > EXECUTION_MAX ? t.prompt.tooLong : t.prompt.executionHint}</span>\n'
        '          </div>\n'
        '          {problem && <p className="banner err" role="alert">{problem}</p>}\n'
        '          {execution?.prompt === text && <div className="col" aria-live="polite">\n'
        '            <div className="row wrap spread"><h3>{t.prompt.answer}</h3><span className="small tx3">{execution.result.model}</span></div>\n'
        '            <div className="prompt-box" tabIndex={0}>{execution.result.text}</div>\n'
        '            <div className="row"><CopyButton text={execution.result.text} /></div>\n'
        '          </div>}\n'
        '        </div>\n'
        '      </details>\n'
        '    </div>\n'
        '  );\n'
        '}\n'
    ),
    'apps/web/src/components/PromptFields.tsx': (
        "import { useId } from 'react';\n"
        "import { OPT_LIMITS } from '../../../../shared/src/optimizer.ts';\n"
        "import { promptChecklist } from '../../../../shared/src/prompt.ts';\n"
        "import { t } from '../strings.ru.ts';\n"
        '\n'
        'export function PromptFields({ names, values, onChange, onCommit }: {\n'
        '  names: string[];\n'
        '  values: Record<string, string>;\n'
        '  onChange: (name: string, value: string) => void;\n'
        '  onCommit?: () => void;\n'
        '}) {\n'
        '  const prefix = useId();\n'
        '  if (!names.length) return null;\n'
        '  return (\n'
        '    <fieldset className="col prompt-fields">\n'
        '      <legend className="label">{t.prompt.fields}</legend>\n'
        '      <div className="form-grid">{names.map((name, index) => {\n'
        '        const id = `${prefix}-${index}`;\n'
        '        return <div key={name}>\n'
        '          <label className="label" htmlFor={id}>{name.replaceAll(\'_\', \' \')}</label>\n'
        '          <textarea id={id} rows={2} className="field" maxLength={OPT_LIMITS.variableValue}\n'
        "            value={Object.hasOwn(values, name) ? values[name] : ''} onChange={(event) => onChange(name, event.target.value)} onBlur={onCommit} />\n"
        '        </div>;\n'
        '      })}</div>\n'
        '    </fieldset>\n'
        '  );\n'
        '}\n'
        '\n'
        'export function PromptChecklist({ text }: { text: string }) {\n'
        '  const criteria = promptChecklist(text);\n'
        '  const count = criteria.filter(({ present }) => present).length;\n'
        "  const summary = count === criteria.length ? t.prompt.checklistReady : t.prompt.checklistCount.replace('{count}', String(count));\n"
        '  return (\n'
        '    <details className="result-details prompt-checklist">\n'
        '      <summary>{summary}</summary>\n'
        '      <ul className="criterion-list">\n'
        '        {criteria.map(({ id, present }) => (\n'
        '          <li key={id} className="row spread">\n'
        "            <span>{t.prompt.criteria[id]}</span><span className={`badge ${present ? 'ok' : ''}`}>{present ? t.prompt.present : t.prompt.absent}</span>\n"
        '          </li>\n'
        '        ))}\n'
        '      </ul>\n'
        '      <p className="small tx3">{t.prompt.checklistHint}</p>\n'
        '    </details>\n'
        '  );\n'
        '}\n'
    ),
    'apps/web/src/components/PromptVersionEditor.tsx': (
        "import { useEffect, useId, useState } from 'react';\n"
        "import { PROMPT_BODY_MAX, type PromptVersions } from '../../../../shared/src/prompt.ts';\n"
        "import { get } from '../api.ts';\n"
        "import { t } from '../strings.ru.ts';\n"
        "import { fmtDate, Modal, Spinner } from '../ui.tsx';\n"
        '\n'
        'export function VersionHistory({ url, current, onSelect }: { url: string; current: PromptVersions; onSelect: (body: string) => void }) {\n'
        "  const [older, setOlder] = useState<PromptVersions['items']>([]);\n"
        '  const [busy, setBusy] = useState(false);\n'
        "  const [error, setError] = useState('');\n"
        '  const items = [...current.items, ...older];\n'
        '  const last = items.at(-1)?.version ?? 1;\n'
        '  const loadOlder = async () => {\n'
        '    setBusy(true);\n'
        "    setError('');\n"
        '    try {\n'
        '      const data = await get<PromptVersions>(`${url}?before=${last}`);\n'
        '      setOlder((previous) => [...previous, ...data.items]);\n'
        '    } catch (problem) {\n'
        '      setError(problem instanceof Error ? problem.message : t.common.error);\n'
        '    } finally {\n'
        '      setBusy(false);\n'
        '    }\n'
        '  };\n'
        '  return (\n'
        '    <details className="result-details">\n'
        '      <summary>{t.prompt.history}</summary>\n'
        '      <ul className="col prompt-history">\n'
        '        {items.map((item) => <li className="row spread wrap" key={item.version}>\n'
        '          <span className="small tx2">{t.prompt.version} {item.version} · {fmtDate(item.created_at)}</span>\n'
        '          <button className="btn sm" onClick={() => onSelect(item.body)}>{t.prompt.loadVersion}</button>\n'
        '        </li>)}\n'
        '      </ul>\n'
        '      {error && <p className="banner err" role="alert">{error}</p>}\n'
        '      {last > 1 && <button className="btn sm" disabled={busy} onClick={() => { void loadOlder(); }}>{busy && <Spinner />}{t.prompt.older}</button>}\n'
        '    </details>\n'
        '  );\n'
        '}\n'
        '\n'
        'export function PromptVersionEditor({ url, onSave, onClose }: {\n'
        '  url: string;\n'
        '  onSave: (body: string, expectedVersion: number) => Promise<void>;\n'
        '  onClose: () => void;\n'
        '}) {\n'
        '  const fieldId = useId();\n'
        '  const [current, setCurrent] = useState<PromptVersions | null>(null);\n'
        "  const [body, setBody] = useState('');\n"
        "  const [error, setError] = useState('');\n"
        '  const [busy, setBusy] = useState(false);\n'
        '  useEffect(() => {\n'
        '    let live = true;\n'
        '    void get<PromptVersions>(url).then((data) => {\n'
        '      if (!live) return;\n'
        '      setCurrent(data);\n'
        "      setBody(data.items[0]?.body ?? '');\n"
        '    }).catch((problem) => { if (live) setError(problem instanceof Error ? problem.message : t.common.error); });\n'
        '    return () => { live = false; };\n'
        '  }, [url]);\n'
        '  const save = async () => {\n'
        '    if (!current || busy) return;\n'
        '    setBusy(true);\n'
        "    setError('');\n"
        '    try { await onSave(body, current.current_version); onClose(); }\n'
        '    catch (problem) { setError(problem instanceof Error ? problem.message : t.common.error); }\n'
        '    finally { setBusy(false); }\n'
        '  };\n'
        '  return (\n'
        '    <Modal title={t.prompt.editor} wide onClose={onClose} footer={<>\n'
        '      <button className="btn" disabled={busy} onClick={onClose}>{t.common.cancel}</button>\n'
        '      <button className="btn primary" disabled={busy || !current || !body.trim() || body.trim() === current.items[0]?.body}\n'
        '        onClick={() => { void save(); }}>{busy && <Spinner />}{t.prompt.saveVersion}</button>\n'
        '    </>}>\n'
        '      {error && <p className="banner err" role="alert">{error}</p>}\n'
        '      {!current && !error && <Spinner />}\n'
        '      {current && <>\n'
        '        <div>\n'
        '          <label className="label" htmlFor={fieldId}>{t.prompt.text}</label>\n'
        '          <textarea id={fieldId} className="field mono" rows={10} maxLength={PROMPT_BODY_MAX} value={body} onChange={(event) => setBody(event.target.value)} />\n'
        '        </div>\n'
        '        <VersionHistory url={url} current={current} onSelect={setBody} />\n'
        '      </>}\n'
        '    </Modal>\n'
        '  );\n'
        '}\n'
    ),
    'apps/web/src/components/PublishPrompt.tsx': (
        "import { useEffect, useId, useState } from 'react';\n"
        "import type { TeamFolders } from '../../../../shared/src/team.ts';\n"
        "import { get, post } from '../api.ts';\n"
        "import { t } from '../strings.ru.ts';\n"
        "import { Modal, Spinner, useToast } from '../ui.tsx';\n"
        '\n'
        'export function PublishPrompt({ body, onClose }: { body: string; onClose: () => void }) {\n'
        '  const prefix = useId();\n'
        '  const toast = useToast();\n'
        "  const [folders, setFolders] = useState<TeamFolders['items'] | null>(null);\n"
        "  const [folderId, setFolderId] = useState('');\n"
        "  const [title, setTitle] = useState('');\n"
        "  const [error, setError] = useState('');\n"
        '  const [busy, setBusy] = useState(false);\n'
        '  useEffect(() => {\n'
        '    let live = true;\n'
        "    void get<TeamFolders>('/api/team/folders').then((data) => {\n"
        '      if (!live) return;\n'
        '      const editable = data.items.filter((item) => item.can_edit);\n'
        '      setFolders(editable);\n'
        "      setFolderId(editable[0]?.id ?? '');\n"
        '    }).catch((problem) => { if (live) setError(problem instanceof Error ? problem.message : t.common.error); });\n'
        '    return () => { live = false; };\n'
        '  }, []);\n'
        '  const publish = async () => {\n'
        '    setBusy(true);\n'
        "    setError('');\n"
        '    try {\n'
        '      await post(`/api/team/folders/${folderId}/prompts`, { title, body });\n'
        "      toast(t.team.published, 'ok');\n"
        '      onClose();\n'
        '    } catch (problem) {\n'
        '      setError(problem instanceof Error ? problem.message : t.common.error);\n'
        '    } finally {\n'
        '      setBusy(false);\n'
        '    }\n'
        '  };\n'
        '  return (\n'
        '    <Modal title={t.team.publish} onClose={onClose} footer={<>\n'
        '      <button className="btn" disabled={busy} onClick={onClose}>{t.common.cancel}</button>\n'
        '      <button className="btn primary" disabled={busy || !folderId || !title.trim()} onClick={() => { void publish(); }}>\n'
        '        {busy && <Spinner />}{t.team.publish}\n'
        '      </button>\n'
        '    </>}>\n'
        '      {error && <p className="banner err" role="alert">{error}</p>}\n'
        '      {!folders && !error && <Spinner />}\n'
        '      {folders?.length === 0 && <p className="tx2">{t.team.noWritable}</p>}\n'
        '      {!!folders?.length && <>\n'
        '        <div>\n'
        '          <label className="label" htmlFor={`${prefix}-folder`}>{t.opt.folder}</label>\n'
        '          <select className="field" id={`${prefix}-folder`} value={folderId} onChange={(event) => setFolderId(event.target.value)}>\n'
        '            {folders.map((folder) => <option key={folder.id} value={folder.id}>{folder.name}</option>)}\n'
        '          </select>\n'
        '        </div>\n'
        '        <div>\n'
        '          <label className="label" htmlFor={`${prefix}-title`}>{t.team.promptTitle}</label>\n'
        '          <input id={`${prefix}-title`} className="field" maxLength={120} value={title} onChange={(event) => setTitle(event.target.value)} />\n'
        '        </div>\n'
        '        <p className="small tx3">{t.team.publishHint}</p>\n'
        '        <div className="prompt-box publish-preview" tabIndex={0}>{body}</div>\n'
        '      </>}\n'
        '    </Modal>\n'
        '  );\n'
        '}\n'
    ),
    'apps/web/src/components/TeamLibrary.tsx': (
        "import { useEffect, useId, useState } from 'react';\n"
        "import { fillPromptVariables, extractPromptVariables } from '../../../../shared/src/prompt.ts';\n"
        "import { teamFolderInput, type TeamFolder, type TeamFolderInput, type TeamFolders, type TeamPrompt, type TeamPromptSummary } from '../../../../shared/src/team.ts';\n"
        "import { del, get, post, put } from '../api.ts';\n"
        "import { t } from '../strings.ru.ts';\n"
        "import { ConfirmModal, Empty, fmtDate, Modal, Skeletons, Spinner } from '../ui.tsx';\n"
        "import { PromptActions } from './PromptActions.tsx';\n"
        "import { PromptChecklist, PromptFields } from './PromptFields.tsx';\n"
        "import { PromptVersionEditor } from './PromptVersionEditor.tsx';\n"
        '\n'
        'const folderPath = (id: string) => `/api/team/folders/${id}`;\n'
        'const itemPath = (folder: string, item: string) => `${folderPath(folder)}/prompts/${item}`;\n'
        'const message = (error: unknown) => error instanceof Error ? error.message : t.common.error;\n'
        'type Listing = { items: TeamPromptSummary[]; has_more: boolean };\n'
        '\n'
        'export function TeamLibrary() {\n'
        '  const [folders, setFolders] = useState<TeamFolders | null>(null);\n'
        "  const [folderId, setFolderId] = useState('');\n"
        '  const [page, setPage] = useState(1);\n'
        '  const [list, setList] = useState<Listing | null>(null);\n'
        "  const [error, setError] = useState('');\n"
        '  const [readyItem, setReadyItem] = useState<{ folderId: string; itemId: string } | null>(null);\n'
        "  const [editor, setEditor] = useState<TeamFolder | 'create' | null>(null);\n"
        '  const [refresh, setRefresh] = useState(0);\n'
        '  const folder = folders?.items.find((item) => item.id === folderId) ?? folders?.items[0];\n'
        '  const currentId = folder?.id;\n'
        '  const reload = () => setRefresh((value) => value + 1);\n'
        '\n'
        '  useEffect(() => {\n'
        '    let live = true;\n'
        "    void get<TeamFolders>('/api/team/folders').then((data) => { if (live) setFolders(data); })\n"
        '      .catch((problem) => { if (live) setError(message(problem)); });\n'
        '    return () => { live = false; };\n'
        '  }, [refresh]);\n'
        '  useEffect(() => {\n'
        '    setList(null);\n'
        "    setError('');\n"
        '    if (!currentId) return;\n'
        '    let live = true;\n'
        '    void get<Listing>(`${folderPath(currentId)}/prompts?page=${page}`).then((data) => {\n'
        '      if (!live) return;\n'
        '      if (!data.items.length && page > 1) setPage(page - 1);\n'
        '      else setList(data);\n'
        '    }).catch((problem) => { if (live) setError(message(problem)); });\n'
        '    return () => { live = false; };\n'
        '  }, [currentId, page, refresh]);\n'
        '\n'
        '  return (\n'
        '    <div className="col">\n'
        '      {error && <p className="banner err" role="alert">{error}</p>}\n'
        '      {!folders && !error && <Skeletons />}\n'
        '      {folders && <div className="library-layout">\n'
        '        <nav className="surface card col library-folders" aria-label={t.team.scope}>\n'
        '          {folders.items.map((item) => <button key={item.id} className="nav-item" aria-current={item.id === currentId ? \'true\' : undefined}\n'
        '            onClick={() => { setFolderId(item.id); setPage(1); }}>\n'
        '            <span className="library-folder-name grow">{item.name}</span>\n'
        '          </button>)}\n'
        '          {folders.can_manage && <button className="btn sm" onClick={() => setEditor(\'create\')}>{t.team.newFolder}</button>}\n'
        '        </nav>\n'
        '        <div className="col">\n'
        '          {!folder && <Empty title={t.team.emptyFolders} hint={t.team.emptyFoldersHint} />}\n'
        '          {folder && <>\n'
        '            <header className="row wrap spread">\n'
        '              <div className="row wrap"><h2>{folder.name}</h2>{!folder.can_edit && <span className="badge">{t.team.readOnly}</span>}</div>\n'
        '              {folders.can_manage && <button className="btn sm" onClick={() => setEditor(folder)}>{t.team.manage}</button>}\n'
        '            </header>\n'
        '            {!list && !error && <Skeletons />}\n'
        '            {list?.items.length === 0 && <Empty title={t.team.emptyPrompts} hint={folder.can_edit ? t.team.emptyPromptsHint : undefined} />}\n'
        '            {list?.items.map((item) => <article className="surface card col" key={item.id}>\n'
        '              <div className="row wrap spread"><h3>{item.title}</h3><span className="small tx3">v{item.version} · {fmtDate(item.updated_at)}</span></div>\n'
        '              <p className="small tx2">{item.preview}</p>\n'
        '              <button className="btn sm prompt-start" onClick={() => setReadyItem({ folderId: folder.id, itemId: item.id })}>{t.library.open}</button>\n'
        '            </article>)}\n'
        '            {list && (page > 1 || list.has_more) && <div className="row wrap">\n'
        '              <button className="btn sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>{t.common.prev}</button>\n'
        '              <span className="small tx2">{t.common.page} {page}</span>\n'
        '              <button className="btn sm" disabled={!list.has_more} onClick={() => setPage(page + 1)}>{t.common.next}</button>\n'
        '            </div>}\n'
        '          </>}\n'
        '        </div>\n'
        '      </div>}\n'
        "      {editor && <FolderSettings folder={editor === 'create' ? undefined : editor} onClose={() => setEditor(null)}\n"
        '        onSaved={(id) => { setFolderId(id); setPage(1); reload(); }} />}\n'
        '      {readyItem && <TeamItem key={readyItem.itemId} path={itemPath(readyItem.folderId, readyItem.itemId)}\n'
        '        editable={folders?.items.find((item) => item.id === readyItem.folderId)?.can_edit ?? false}\n'
        '        onClose={() => setReadyItem(null)} onChanged={reload} />}\n'
        '    </div>\n'
        '  );\n'
        '}\n'
        '\n'
        'function FolderSettings({ folder, onClose, onSaved }: { folder?: TeamFolder; onClose: () => void; onSaved: (id: string) => void }) {\n'
        '  const prefix = useId();\n'
        "  const [name, setName] = useState(folder?.name ?? '');\n"
        "  const [visibility, setVisibility] = useState<TeamFolderInput['visibility']>(folder?.visibility ?? 'restricted');\n"
        "  const [readers, setReaders] = useState('');\n"
        "  const [editors, setEditors] = useState('');\n"
        '  const [loading, setLoading] = useState(!!folder);\n'
        '  const [busy, setBusy] = useState(false);\n'
        "  const [error, setError] = useState('');\n"
        '  const [failed, setFailed] = useState(false);\n'
        '  useEffect(() => {\n'
        '    if (!folder) return;\n'
        '    let live = true;\n'
        '    void get<TeamFolderInput>(`${folderPath(folder.id)}/settings`).then((data) => {\n'
        '      if (!live) return;\n'
        '      setName(data.name);\n'
        '      setVisibility(data.visibility);\n'
        "      setReaders(data.members.filter((member) => member.role === 'reader').map((member) => member.user_id).join(', '));\n"
        "      setEditors(data.members.filter((member) => member.role === 'editor').map((member) => member.user_id).join(', '));\n"
        '    }).catch((problem) => { if (live) { setError(message(problem)); setFailed(true); } })\n'
        '      .finally(() => { if (live) setLoading(false); });\n'
        '    return () => { live = false; };\n'
        '  }, [folder?.id]);\n'
        '  const save = async () => {\n'
        '    const split = (s: string) => [...new Set(s.split(/[\\s,;]+/).filter(Boolean))];\n'
        '    const members = [\n'
        "      ...split(readers).map((user_id) => ({ user_id, role: 'reader' as const })),\n"
        "      ...split(editors).map((user_id) => ({ user_id, role: 'editor' as const })),\n"
        '    ];\n'
        '    const parsed = teamFolderInput.safeParse({ name, visibility, members });\n'
        '    if (!parsed.success) { setError(t.team.invalidMembers); return; }\n'
        '    setBusy(true);\n'
        "    setError('');\n"
        '    try {\n'
        "      const saved = folder ? await put<TeamFolder>(`${folderPath(folder.id)}/settings`, parsed.data) : await post<TeamFolder>('/api/team/folders', parsed.data);\n"
        '      onSaved(saved.id);\n'
        '      onClose();\n'
        '    } catch (problem) { setError(message(problem)); }\n'
        '    finally { setBusy(false); }\n'
        '  };\n'
        '  return (\n'
        '    <Modal title={folder ? t.team.manage : t.team.newFolder} onClose={onClose} footer={<>\n'
        '      <button className="btn" disabled={busy} onClick={onClose}>{t.common.cancel}</button>\n'
        '      <button className="btn primary" disabled={busy || loading || failed || !name.trim()} onClick={() => { void save(); }}>{busy && <Spinner />}{t.common.save}</button>\n'
        '    </>}>\n'
        '      {error && <p className="banner err" role="alert">{error}</p>}\n'
        '      {loading ? <Spinner /> : <div className="col">\n'
        '        <div><label className="label" htmlFor={`${prefix}-name`}>{t.library.folderName}</label>\n'
        '          <input className="field" id={`${prefix}-name`} maxLength={60} value={name} onChange={(event) => setName(event.target.value)} /></div>\n'
        '        <div><label className="label" htmlFor={`${prefix}-visibility`}>{t.team.visibility}</label>\n'
        '          <select className="field" id={`${prefix}-visibility`} value={visibility} onChange={(event) => setVisibility(event.target.value === \'portal\' ? \'portal\' : \'restricted\')}>\n'
        '            <option value="restricted">{t.team.restricted}</option><option value="portal">{t.team.portal}</option>\n'
        '          </select>\n'
        '        </div>\n'
        '        <p className="small tx2">{t.team.membersHint}</p>\n'
        '        <div><label className="label" htmlFor={`${prefix}-readers`}>{t.team.readers}</label>\n'
        '          <textarea className="field" id={`${prefix}-readers`} rows={2} maxLength={4000} value={readers} onChange={(event) => setReaders(event.target.value)} /></div>\n'
        '        <div><label className="label" htmlFor={`${prefix}-editors`}>{t.team.editors}</label>\n'
        '          <textarea className="field" id={`${prefix}-editors`} rows={2} maxLength={4000} value={editors} onChange={(event) => setEditors(event.target.value)} /></div>\n'
        '      </div>}\n'
        '    </Modal>\n'
        '  );\n'
        '}\n'
        '\n'
        'function TeamItem({ path, editable, onClose, onChanged }: { path: string; editable: boolean; onClose: () => void; onChanged: () => void }) {\n'
        '  const [item, setItem] = useState<TeamPrompt | null>(null);\n'
        "  const [error, setError] = useState('');\n"
        '  const [values, setValues] = useState<Record<string, string>>({});\n'
        '  const [editing, setEditing] = useState(false);\n'
        '  const [confirm, setConfirm] = useState(false);\n'
        '  useEffect(() => {\n'
        '    let live = true;\n'
        '    void get<TeamPrompt>(path).then((data) => { if (live) setItem(data); })\n'
        '      .catch((problem) => { if (live) setError(message(problem)); });\n'
        '    return () => { live = false; };\n'
        '  }, [path]);\n'
        "  const text = item ? fillPromptVariables(item.body, values) : '';\n"
        '  const remove = async () => {\n'
        '    try { await del(path); onChanged(); onClose(); }\n'
        '    catch (problem) { setError(message(problem)); }\n'
        '  };\n'
        '  return <>\n'
        '    <Modal title={item?.title ?? t.team.scope} wide onClose={onClose} footer={editable && item ? <>\n'
        '      <button className="btn sm" onClick={() => setEditing(true)}>{t.prompt.editVersion}</button>\n'
        '      <button className="btn sm danger" onClick={() => setConfirm(true)}>{t.common.delete}</button>\n'
        '    </> : undefined}>\n'
        '      {error && <p className="banner err" role="alert">{error}</p>}\n'
        '      {!item && !error && <Spinner />}\n'
        '      {item && <>\n'
        '        <PromptFields names={extractPromptVariables(item.body).slice(0, 20)} values={values} onChange={(name, value) => setValues((current) => ({ ...current, [name]: value }))} />\n'
        '        <div className="prompt-box" tabIndex={0}>{text}</div>\n'
        '        <PromptActions text={text} />\n'
        '        <PromptChecklist text={text} />\n'
        '      </>}\n'
        '    </Modal>\n'
        '    {editing && <PromptVersionEditor url={`${path}/versions`} onClose={() => setEditing(false)}\n'
        '      onSave={async (body, expected_version) => { setItem(await put<TeamPrompt>(path, { body, expected_version })); onChanged(); }} />}\n'
        '    {confirm && <ConfirmModal title={t.common.delete} text={t.team.confirmDelete} danger onClose={() => setConfirm(false)} onConfirm={remove} />}\n'
        '  </>;\n'
        '}\n'
    ),
    'apps/web/src/screens/Home.tsx': (
        "import { useState, type FormEvent } from 'react';\n"
        'import {\n'
        '  LIMITS, OPT_LIMITS, SYSTEM_IDS, SYSTEM_NAMES, START_MODES, inferPromptRoute, isHypothesisTask,\n'
        '  type GenerateRequest, type OptimizeRequest, type StartMode, type SystemId,\n'
        "} from '../../../../shared/src/index.ts';\n"
        "import { useApp } from '../context.tsx';\n"
        "import { t } from '../strings.ru.ts';\n"
        "import { Spinner } from '../ui.tsx';\n"
        "import { GeneratorScreen } from './Generator.tsx';\n"
        "import { OptimizerScreen } from './Optimizer.tsx';\n"
        '\n'
        'type Role = keyof typeof t.home.examples;\n'
        "type Job = { id: number; mode: 'generate'; request: GenerateRequest } | { id: number; mode: 'optimize'; request: OptimizeRequest };\n"
        "const ROLES = ['marketing', 'hr', 'leader'] as const;\n"
        '\n'
        'export function HomeScreen() {\n'
        '  const { settings } = useApp();\n'
        "  const [input, setInput] = useState('');\n"
        "  const [mode, setMode] = useState<StartMode>('auto');\n"
        '  const [role, setRole] = useState<Role | null>(null);\n'
        '  const [system, setSystem] = useState<SystemId | null>(null);\n'
        '  const [job, setJob] = useState<Job | null>(null);\n'
        '  const [busy, setBusy] = useState(false);\n'
        "  const resolved = mode === 'auto' ? inferPromptRoute(input) : mode;\n"
        "  const selectedSystem = system ?? settings?.default_systems[0] ?? 'chatgpt';\n"
        "  const min = resolved === 'generate' ? LIMITS.rawInputMin : OPT_LIMITS.rawMin;\n"
        "  const max = resolved === 'generate' ? LIMITS.rawInputMax : OPT_LIMITS.rawMax;\n"
        '  const valid = input.trim().length >= min && input.trim().length <= max;\n'
        '  const submit = (event: FormEvent<HTMLFormElement>) => {\n'
        '    event.preventDefault();\n'
        '    if (!valid || busy) return;\n'
        '    const raw_input = input.trim();\n'
        '    const id = (job?.id ?? 0) + 1;\n'
        '    setBusy(true);\n'
        "    if (resolved === 'generate') {\n"
        "      setJob({ id, mode: 'generate', request: { raw_input, systems: [selectedSystem], language: settings?.default_language ?? 'ru',\n"
        "        options: { task_type: isHypothesisTask(raw_input) ? 'hypothesis' : 'auto', detail: settings?.default_detail ?? 'standard', assumptions_mode: 'assume', include_format: true } } });\n"
        '    } else {\n'
        "      setJob({ id, mode: 'optimize', request: { raw_input, workflow: resolved, preset: 'auto', output_format: 'none', tone: 'none', bridge: false } });\n"
        '    }\n'
        '  };\n'
        "  const pickExample = (value: string) => { setInput(value); setMode('auto'); };\n"
        '  return (\n'
        '    <div className="col home-workspace">\n'
        '      <form className="surface card col" onSubmit={submit}>\n'
        '        <h1>{t.home.title}</h1>\n'
        '        <div>\n'
        '          <label className="label" htmlFor="home-input">{t.home.input}</label>\n'
        '          <textarea className="field" id="home-input" rows={4} maxLength={OPT_LIMITS.rawMax} value={input}\n'
        '            placeholder={t.home.placeholder} onChange={(event) => setInput(event.target.value)} />\n'
        '        </div>\n'
        '        <div className="row wrap spread">\n'
        '          <div className="row wrap">\n'
        '            <button className="btn primary" type="submit" disabled={!valid || busy}>{busy && <Spinner />}{busy ? t.opt.running : t.home.submit}</button>\n'
        '            {input.trim().length >= min && <span className="small tx2">{t.home.modes[resolved]}</span>}\n'
        '          </div>\n'
        '          {input.trim().length > max && <span className="small tx2">{t.home.inputLimit.replace(\'{limit}\', String(max))}</span>}\n'
        '        </div>\n'
        '        <details className="result-details">\n'
        '          <summary>{t.home.modeLabel}</summary>\n'
        '          <div className="row wrap">\n'
        '            <select className="field prompt-select" aria-label={t.home.modeLabel} value={mode} onChange={(event) => setMode(event.target.value as StartMode)}>\n'
        '              {START_MODES.map((value) => <option key={value} value={value}>{t.home.modes[value]}</option>)}\n'
        '            </select>\n'
        '            {resolved === \'generate\' && <select className="field prompt-select" aria-label={t.gen.systems} value={selectedSystem}\n'
        '              onChange={(event) => setSystem(event.target.value as SystemId)}>\n'
        '              {SYSTEM_IDS.map((id) => <option key={id} value={id}>{SYSTEM_NAMES[id]}</option>)}\n'
        '            </select>}\n'
        '          </div>\n'
        '          <p className="small tx3">{t.home.routingHint}</p>\n'
        '          <button type="button" className="btn sm ghost prompt-start" onClick={() => pickExample(t.home.hypothesis)}>{t.home.hypothesisLabel}</button>\n'
        '        </details>\n'
        '      </form>\n'
        "      {job?.mode === 'generate' && <GeneratorScreen key={job.id} starter={job.request} onBusy={setBusy} />}\n"
        "      {job?.mode === 'optimize' && <OptimizerScreen key={job.id} starter={job.request} onBusy={setBusy} />}\n"
        '      {!job && <details className="surface card result-details role-examples">\n'
        '        <summary>{t.home.examplesTitle}</summary>\n'
        '        <div className="col">\n'
        '          <div className="row wrap" role="group" aria-label={t.home.examplesTitle}>\n'
        '            {ROLES.map((value) => <button key={value} type="button" className={`chip ${role === value ? \'on\' : \'\'}`}\n'
        '              aria-pressed={role === value} onClick={() => setRole(value)}>{t.home.roles[value]}</button>)}\n'
        '          </div>\n'
        '          {role && <div className="form-grid">{t.home.examples[role].map(({ before, after }) => (\n'
        '            <article key={before} className="col surface card">\n'
        '              <p className="small"><strong>{t.home.before}</strong> {before}</p>\n'
        '              <p className="small tx2"><strong>{t.home.after}</strong> {after}</p>\n'
        '              <button className="btn sm prompt-start" type="button" onClick={() => pickExample(before)}>{t.home.useExample}</button>\n'
        '            </article>\n'
        '          ))}</div>}\n'
        '        </div>\n'
        '      </details>}\n'
        '    </div>\n'
        '  );\n'
        '}\n'
    ),
    'docs/prompt-workspace.md': (
        '# Prompt workspace v1.2\n'
        '\n'
        '## Product decisions\n'
        '\n'
        'The default route and the **New prompt** action open one workspace. The user submits a task, a prompt, or an idea in the same composer. The detected mode appears by the submit button. The selector allows an override, including reusable template and style extraction. The old Generator and Optimizer deep links remain available.\n'
        '\n'
        '| Input | Default action |\n'
        '| --- | --- |\n'
        '| Concrete request, such as a task beginning with an imperative | Generate a prompt for one selected system through the existing skill pipeline |\n'
        '| A prompt with explicit sections or other strong structural cues | Optimize it through the configured engine |\n'
        '| An idea without an action, or a request with too little information for the Generator | Ask clarification questions through the Optimizer |\n'
        '| A request beginning with “Помоги проверить гипотезу” | Use the Generator’s Hypothesis validation preset |\n'
        '\n'
        'Auto mode is rule-based. It does not make a classification request or send the draft to a model before submission. The workspace uses the first configured Generator system by default and exposes the model choice in the mode panel. Prompts above the Generator’s length limit use the Optimizer in auto mode within its input limit. Distinct mode selections live under the composer. A manual Generator selection keeps existing validation and system settings.\n'
        '\n'
        'The hypothesis preset asks for a falsifiable proposition, the audience, the cheapest credible test, the resources and timeline, measurable success and stop thresholds, and a decision rule. It states assumptions where evidence is missing. The app provides the existing prompt-generation flow for this preset.\n'
        '\n'
        'Optional examples target Marketing, HR and Management. Each role has three illustrative before/after examples. Selecting an example fills the composer. “Answer for me” suggests one answer per existing question, fills empty fields and leaves manual answers intact. The user reviews and submits the form explicitly.\n'
        '\n'
        '## Results and visual system\n'
        '\n'
        'Obsidian / Linear Dark is the baseline. The unified composer uses the existing surface, controls and typography tokens. On a narrow screen, the composer and prompt text with its copy action remain primary. Mode options, examples, model commentary, token counts and secondary actions live in accordions. View choices and variable fields stay next to the prompt they affect.\n'
        '\n'
        'The checklist flags four explicit elements in the text using labels and useful phrasing in Russian and English: role, context, constraints, and output format. It is recomputed from the displayed text, including legacy saved prompts, and reports presence without a model score or another model call. A 4/4 result means all four elements were detected by the text rules.\n'
        '\n'
        'Compression comparison uses a word-level diff. Deletions are muted and struck through, additions are underlined. If the diff exceeds its time budget, the UI shows both texts for comparison. The number of tokens is an estimate. Copy and model execution operate on the selected original or compressed variant with the current fields filled. The diff itself is a review view.\n'
        '\n'
        "The field form recognizes both `[Insert source text]` and `{{Имя_клиента}}` in saved prompts. Unresolved placeholders remain as written and substitution runs once. Personal fields can be saved explicitly. Values in the team reader's form are local to that open item and are never added to the shared template.\n"
        '\n'
        'Buttons can copy a prompt and open ChatGPT, Claude or Qwen in a new tab. The browser clipboard holds the prompt. Destination URLs are fixed and contain no prompt text. If opening is blocked after the copy, a manual link appears. Native Bitrix24 mobile clients may impose additional clipboard or popup restrictions.\n'
        '\n'
        '“Run prompt here” passes only the rendered text selected by the user to the existing configured optimizer engine. The model response is displayed as text. The endpoint has no tools, CRM calls, external browser control or automatic follow-up. Output is transient. The selected provider processes the prompt and may account for it according to its plan. The endpoint is restricted to signed-in users and limited to three launches per user per minute.\n'
        '\n'
        '## Team library\n'
        '\n'
        '**Library → Общие** contains portal-scoped folders. An administrator creates a folder such as **Отдел продаж**, chooses its visibility, and assigns employee IDs from Bitrix24.\n'
        '\n'
        '| Role | See the current prompt and use it | Publish and edit | Manage folder access |\n'
        '| --- | --- | --- | --- |\n'
        '| Administrator | Yes, within their portal | Yes | Yes |\n'
        '| Editor assigned to a folder | Yes | Yes, including its editable history and removal of shared prompts | No |\n'
        '| Reader assigned to a folder | Yes | No | No |\n'
        '| Other employee of the same portal | When the folder is visible to the portal | No | No |\n'
        '| Other portal or guest | No | No | No |\n'
        '\n'
        'New folders default to restricted visibility. Folder membership uses Bitrix24 employee IDs assigned in the app. CRM records and organizational department membership are not queried. The server uses the trusted Alaio Gateway portal UUID and employee identity at each team request. Deploy the origin behind that Gateway. A publication is a separate copy of the current source prompt, with placeholders and no form values. Publishing, revising or deleting that copy does not change the personal item.\n'
        '\n'
        '## Versions and persistence\n'
        '\n'
        "SQLite migration v3 creates `prompt_versions`, `team_folders`, `team_folder_members` and `team_prompts`. Existing personal content stays in its original table. The first text edit snapshots the previous content as version 1. Future edits append a revision. Restoring an older body uses the same save path and creates another revision. Versions cover personal Optimizer results, editable personal templates, and shared prompt bodies. The Generator's generated variants retain their existing history. Store a generated result as a personal template to start editing its text manually.\n"
        '\n'
        'Writes use the current version as a conflict check for the editor, and personal text edits atomically clear any outdated compression and refresh the index. Deleting a prompt also removes its revision entries. Saved variable values, tags and favourites belong to the personal item and are not counted as text revisions.\n'
        '\n'
        '## HTTP and release checks\n'
        '\n'
        "- `POST /api/optimizer/items/:id/suggest`, `POST /api/generate/:id/suggest` suggest answers to the caller's draft.\n"
        '- `POST /api/prompts/execute` runs a single text prompt using the configured engine.\n'
        '- `GET /api/optimizer/items/:id/versions` and `PUT /api/optimizer/items/:id/prompt` support optimistic edits. Personal templates expose `GET /api/templates/:id/versions` and use their existing PATCH route to save.\n'
        '- `/api/team/folders` contains folder management and `/api/team/folders/:folderId/prompts` contains the prompt records and revisions.\n'
        '- Model requests from the browser use Server-Sent Events with an initial progress event and periodic heartbeats. The JSON interface is retained for existing clients. The Gateway sets a short deadline for ordinary HTTP responses while models can take longer.\n'
        '- Before deploying, back up the SQLite volume. On the actual Bitrix24 portal, verify administrator/editor/reader and guest roles, copy/open behavior inside the mobile iframe and one real engine call covering generation, optimization and execution. Review portal ACL and provider quota before wider rollout.\n'
        '\n'
        'References\n'
        '\n'
        '- [Alaio Gateway identity, headers and timeouts](https://vibecode.bitrix24.com/docs/infra/app-runtime)\n'
        '- [Qwen web chat](https://chat.qwen.ai/)\n'
        '- [Claude browser access](https://support.claude.com/en/articles/8114491-get-started-with-claude)\n'
    ),
    'shared/src/prompt.ts': (
        "import { z } from 'zod';\n"
        '\n'
        "export const PROMPT_CRITERIA = ['role', 'context', 'constraints', 'format'] as const;\n"
        'const HEADINGS: Record<(typeof PROMPT_CRITERIA)[number], RegExp> = {\n'
        '  role: /^(?:role|persona|роль|персона)\\s*(?:[:：-]|\\s*$)/iu,\n'
        '  context: /^(?:context|background|audience|контекст|исходные данные|аудитория)\\s*(?:[:：-]|\\s*$)/iu,\n'
        '  constraints: /^(?:constraints?|requirements?|rules?|ограничения?|требования|правила)\\s*(?:[:：-]|\\s*$)/iu,\n'
        '  format: /^(?:output(?: format)?|response(?: format)?|format|deliverables?|формат(?: (?:ответа|вывода))?|результат)\\s*(?:[:：-]|\\s*$)/iu,\n'
        '};\n'
        'const CUES = {\n'
        '  role: /(?:^|\\s)(?:you are|act as|assume the role of|ты —|ты[- ](?:эксперт|редактор|консультант)|выступи в роли|представь, что ты)\\s/iu,\n'
        '  context: /(?:^|\\s)(?:target audience|intended for|our team|known facts|для команды|целевая аудитория|исходные данные|у нас есть|для клиентов)(?=[\\s:,.]|$)/iu,\n'
        '  constraints: /(?:^|\\s)(?:no more than|at most|do not|must not|avoid|only use|не более|не длиннее|не добавляй|не используй|без вымысла|только по)(?=[\\s:,.]|$)/iu,\n'
        '  format: /(?:^|\\s)(?:as a table|in json|in markdown|as a checklist|in bullet points|в виде таблицы|в формате json|в markdown|в виде списка|структурируй ответ)(?=[\\s:,.]|$)/iu,\n'
        '};\n'
        "const linesOf = (text: string) => text.split('\\n').map((line) =>\n"
        "  line.trim().replace(/^(?:#{1,6}\\s*|[-*]\\s+|\\d+\\.\\s+)/, '').replace(/\\*\\*/g, ''));\n"
        'const TAG: Record<(typeof PROMPT_CRITERIA)[number], RegExp> = {\n'
        '  role: /<(?:role|identity)>\\s*[^<\\s]/iu,\n'
        '  context: /<(?:context|background)>\\s*[^<\\s]/iu,\n'
        '  constraints: /<(?:constraints|requirements)>\\s*[^<\\s]/iu,\n'
        '  format: /<(?:output_format|format|output)>\\s*[^<\\s]/iu,\n'
        '};\n'
        '\n'
        'export function promptChecklist(text: string) {\n'
        '  const lines = linesOf(text);\n'
        '  return PROMPT_CRITERIA.map((id) => ({\n'
        '    id, present: lines.some((line, index) => {\n'
        '      const title = HEADINGS[id].exec(line);\n'
        '      if (!title) return false;\n'
        '      if (line.slice(title[0].length).trim()) return true;\n'
        '      const next = lines.slice(index + 1).find(Boolean);\n'
        '      return !!next && !Object.values(HEADINGS).some((heading) => heading.test(next));\n'
        '    }) || CUES[id].test(text) || TAG[id].test(text),\n'
        '  }));\n'
        '}\n'
        '\n'
        "export const START_MODES = ['auto', 'generate', 'magic', 'clarify', 'template', 'reverse'] as const;\n"
        'export type StartMode = (typeof START_MODES)[number];\n'
        '\n'
        "export function inferPromptRoute(text: string): Exclude<StartMode, 'auto' | 'template' | 'reverse'> {\n"
        '  const trimmed = text.trim();\n'
        '  const structure = promptChecklist(trimmed).filter((criterion) => criterion.present).length;\n'
        "  if (structure >= 2 || (structure > 0 && trimmed.length >= 240) || trimmed.length > 8000) return 'magic';\n"
        "  if (isHypothesisTask(trimmed)) return 'generate';\n"
        '  const idea = /^(?:идея|гипотеза|мысль|предположение|планирую|хочу|думаю|предлагаю|мы можем|а что если|может быть|idea|hypothesis|what if|i (?:want|think|plan))(?=[\\s:,.?!]|$)/iu;\n'
        '  const task = /(?:^|[.!?\\n;:]\\s*)(?:помоги|напиши|перепиши|составь|объясни|придумай|сделай|разбери|проанализируй|оцени|подготовь|создай|переведи|разработай|предложи|write|rewrite|build|create|draft|summarize|analy[sz]e|translate|explain|generate|help)(?=[\\s:,.]|$)/iu;\n'
        "  if (idea.test(trimmed) && !task.test(trimmed)) return 'clarify';\n"
        "  if (trimmed.length < 10) return 'clarify';\n"
        "  return 'generate';\n"
        '}\n'
        '\n'
        'export const isHypothesisTask = (text: string) =>\n'
        '  /^(?:помоги проверить гипотезу|проверь гипотезу|validate (?:this|my) hypothesis)(?=[\\s:,.!?]|$)/iu.test(text.trim());\n'
        '\n'
        'const VARIABLE = /(?<![\\[{])(?:\\[([^\\[\\]\\n\\r]{2,60})\\](?![(\\]])|\\{\\{\\s*([\\p{L}\\p{M}\\p{N}_-]{1,60})\\s*\\}\\}(?!\\}))/gu;\n'
        'function variableName(bracket: string | undefined, brace: string | undefined) {\n'
        '  const name = brace ?? bracket?.trim();\n'
        '  return name && (brace || /\\p{L}/u.test(name)) ? name : undefined;\n'
        '}\n'
        'export function extractPromptVariables(text: string): string[] {\n'
        '  const names = new Set<string>();\n'
        '  for (const match of text.matchAll(VARIABLE)) {\n'
        '    const name = variableName(match[1], match[2]);\n'
        '    if (name) names.add(name);\n'
        '  }\n'
        '  return [...names];\n'
        '}\n'
        'export function fillPromptVariables(text: string, values: Readonly<Record<string, string>>): string {\n'
        '  return text.replace(VARIABLE, (match, bracket: string | undefined, brace: string | undefined) => {\n'
        '    const name = variableName(bracket, brace);\n'
        '    return name && Object.hasOwn(values, name) && values[name]?.trim() ? values[name]! : match;\n'
        '  });\n'
        '}\n'
        '\n'
        'export const PROMPT_BODY_MAX = 20_000;\n'
        'export const EXECUTION_MAX = 60_000;\n'
        'export const promptRevisionSchema = z.object({\n'
        '  body: z.string().trim().min(1).max(PROMPT_BODY_MAX),\n'
        '  expected_version: z.number().int().positive(),\n'
        '});\n'
        'export interface PromptVersion { version: number; body: string; created_at: string }\n'
        'export interface PromptVersions { current_version: number; items: PromptVersion[] }\n'
        'export interface PromptExecution { text: string; model: string }\n'
        'export const promptIdSchema = z.object({ id: z.string().min(1).max(60) });\n'
    ),
    'shared/src/team.ts': (
        "import { z } from 'zod';\n"
        "import { PROMPT_BODY_MAX } from './prompt.ts';\n"
        '\n'
        "export const TEAM_ACCESS = ['reader', 'editor'] as const;\n"
        "export const TEAM_VISIBILITY = ['portal', 'restricted'] as const;\n"
        'export const teamFolderInput = z.object({\n'
        '  name: z.string().trim().min(1).max(60),\n'
        '  visibility: z.enum(TEAM_VISIBILITY),\n'
        '  members: z.array(z.object({ user_id: z.string().regex(/^\\d{1,18}$/), role: z.enum(TEAM_ACCESS) })).max(200),\n'
        '}).refine((input) => new Set(input.members.map((member) => member.user_id)).size === input.members.length,\n'
        "  { message: 'Each employee may have only one folder role', path: ['members'] });\n"
        'export const teamPromptInput = z.object({\n'
        '  title: z.string().trim().min(1).max(120),\n'
        '  body: z.string().trim().min(1).max(PROMPT_BODY_MAX),\n'
        '});\n'
        'export type TeamFolderInput = z.infer<typeof teamFolderInput>;\n'
        "export interface TeamFolder { id: string; name: string; visibility: TeamFolderInput['visibility']; can_edit: boolean }\n"
        'export interface TeamFolders { items: TeamFolder[]; can_manage: boolean }\n'
        'export interface TeamPromptSummary { id: string; title: string; preview: string; version: number; updated_at: string }\n'
        'export interface TeamPrompt { id: string; title: string; body: string; version: number; updated_at: string }\n'
    ),
    'tests/product.test.ts': (
        "import { afterEach, describe, expect, it } from 'vitest';\n"
        "import { mkdtempSync, rmSync } from 'node:fs';\n"
        "import { join } from 'node:path';\n"
        "import { tmpdir } from 'node:os';\n"
        "import { openDb } from '../apps/server/src/db.ts';\n"
        "import { buildApp } from '../apps/server/src/routes.ts';\n"
        "import { clearIdentityCache, resetRateLimits } from '../apps/server/src/auth.ts';\n"
        "import type { ChatMessage, VibeClient } from '../apps/server/src/vibe.ts';\n"
        "import { buildTransformerUser } from '../apps/server/src/generation.ts';\n"
        "import { extractPromptVariables, fillPromptVariables, inferPromptRoute, optionsSchema, promptChecklist } from '../shared/src/index.ts';\n"
        "import { fakeVibe, freshDb } from './helpers.ts';\n"
        '\n'
        "const PORTAL = 'ee637767-f81d-4460-8c42-dd95262fb893';\n"
        "const OTHER_PORTAL = 'c7db9de1-55b8-4620-b683-1d8a0f9b67ee';\n"
        "const session = (id: string, role = 'MEMBER', portal = PORTAL) => ({\n"
        "  'x-vibe-user-id': id, 'x-vibe-user-role': role, 'x-vibe-portal-id': portal,\n"
        '});\n'
        "const ADMIN = session('1', 'ADMIN');\n"
        "const EDITOR = session('20');\n"
        "const READER = session('21');\n"
        "const EMPLOYEE = session('22');\n"
        "const BODY = 'Роль: редактор.\\nКонтекст: ответ на письмо {{Имя_клиента}}.\\nОграничения: не выдумывай факты.\\nФормат: письмо по [Текст письма].';\n"
        "const CHANGE = 'Роль: старший редактор.\\nФормат: короткий ответ.';\n"
        '\n'
        'const cleanups: (() => void | Promise<void>)[] = [];\n'
        'afterEach(async () => { for (const cleanup of cleanups.splice(0).reverse()) await cleanup(); });\n'
        '\n'
        "async function fixture(overrides?: VibeClient['chat']) {\n"
        '  resetRateLimits();\n'
        '  clearIdentityCache();\n'
        '  const db = freshDb();\n'
        '  const base = fakeVibe();\n'
        '  const calls: ChatMessage[][] = [];\n'
        "  const chat: VibeClient['chat'] = async (model, messages, options) => {\n"
        '    calls.push(messages);\n'
        '    if (overrides) return overrides(model, messages, options);\n'
        "    const system = messages[0]?.content ?? '';\n"
        "    const content = system.includes('prepare an interview') ? JSON.stringify({ clarifying_questions: ['Какая аудитория?', 'Какая цель?', 'Какие ресурсы?'] })\n"
        "      : system.includes('Suggest one short') ? JSON.stringify({ answers: ['Новые клиенты', 'Проверить интерес', 'Две недели'] })\n"
        "      : system.includes('prompt compressor') ? JSON.stringify({ compressed_prompt: 'Роль: редактор. {{Имя_клиента}}, [Текст письма].' })\n"
        "      : system.startsWith('You are a prompt engineer') ? JSON.stringify({ final_prompt: BODY, changelog_explanation: ['Уточнены условия.'] })\n"
        "      : '';\n"
        "    if (content) return { content, totalTokens: 4, model: 'test' };\n"
        "    if (messages.length === 1) return { content: 'Готовый ответ', totalTokens: 4, model: 'test' };\n"
        '    return base.chat(model, messages, options);\n'
        '  };\n'
        '  const app = await buildApp({ db, vibe: { ...base, chat } });\n'
        '  cleanups.push(() => db.raw.close(), () => app.close());\n'
        '  return {\n'
        '    db, app, calls,\n'
        "    async call(method: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE', url: string, headers = ADMIN, payload?: Record<string, unknown>) {\n"
        '      const result = await app.inject({ method, url, headers, payload });\n'
        '      return { status: result.statusCode, data: result.json() };\n'
        '    },\n'
        '  };\n'
        '}\n'
        '\n'
        "describe('shared prompt behavior', () => {\n"
        "  it('routes structured text, a concrete task, an idea and a hypothesis preset', () => {\n"
        "    expect(inferPromptRoute(BODY)).toBe('magic');\n"
        "    expect(inferPromptRoute('Напиши письмо клиенту о переносе встречи')).toBe('generate');\n"
        "    expect(inferPromptRoute('Идея: отправлять новые подборки клиентам по пятницам')).toBe('clarify');\n"
        "    expect(inferPromptRoute('Помоги проверить гипотезу: демо повысит конверсию')).toBe('generate');\n"
        "    const prompt = buildTransformerUser(null, 'Гипотеза: демо поможет клиентам', optionsSchema.parse({ task_type: 'hypothesis' }));\n"
        "    expect(prompt).toContain('success and stop thresholds');\n"
        '  });\n'
        "  it('checks text criteria and fills the two placeholder styles without evaluating links or the prototype', () => {\n"
        '    expect(promptChecklist(BODY).map(({ present }) => present)).toEqual([true, true, true, true]);\n'
        "    expect(promptChecklist('Напиши письмо клиенту').some(({ present }) => present)).toBe(false);\n"
        "    const text = BODY + ' [Справка](https://example.org) {{constructor}}';\n"
        "    expect(extractPromptVariables(text)).toEqual(['Имя_клиента', 'Текст письма', 'constructor']);\n"
        "    expect(fillPromptVariables(text, { 'Имя_клиента': 'Ирина', 'Текст письма': '[Оригинал]' }))\n"
        "      .toContain('Формат: письмо по [Оригинал]. [Справка](https://example.org) {{constructor}}');\n"
        '  });\n'
        '});\n'
        '\n'
        "describe('versions and model actions', () => {\n"
        "  it('offers draft answers without submitting the form and supports a single non-persisted execution', async () => {\n"
        '    const { app, call, db, calls } = await fixture();\n'
        "    const draft = await call('POST', '/api/optimizer/run', ADMIN, { workflow: 'clarify', raw_input: 'Идея: запустить рассылку' });\n"
        '    const url = `/api/optimizer/items/${draft.data.id}`;\n'
        "    expect((await call('POST', `${url}/suggest`, READER, {})).status).toBe(404);\n"
        "    expect((await call('POST', `${url}/suggest`, ADMIN, {})).data.answers).toEqual(['Новые клиенты', 'Проверить интерес', 'Две недели']);\n"
        "    expect((await call('GET', url, ADMIN)).data).toMatchObject({ status: 'draft_questions', answers: [] });\n"
        "    const result = await call('POST', `${url}/answer`, ADMIN, { answers: ['Мой вариант', 'Проверить интерес', 'Две недели'] });\n"
        "    expect(result.data).toMatchObject({ status: 'ok', optimized_score: null, final_prompt: BODY });\n"
        '\n'
        "    const response = await app.inject({ method: 'POST', url: '/api/prompts/execute', headers: { ...ADMIN, accept: 'text/event-stream' }, payload: { prompt: BODY } });\n"
        "    expect(response.headers['content-type']).toContain('text/event-stream');\n"
        '    expect(response.payload).toMatch(/^event: working[\\s\\S]*event: result\\ndata: /);\n'
        "    expect(response.payload).toContain('Готовый ответ');\n"
        "    expect(calls.at(-1)).toEqual([{ role: 'user', content: BODY }]);\n"
        "    expect(db.get('SELECT COUNT(*) AS total FROM optimizations')?.total).toBe(1);\n"
        "    expect((await app.inject({ method: 'POST', url: '/api/prompts/execute', payload: { prompt: BODY } })).statusCode).toBe(401);\n"
        "    await call('POST', '/api/prompts/execute', ADMIN, { prompt: BODY });\n"
        "    await call('POST', '/api/prompts/execute', ADMIN, { prompt: BODY });\n"
        "    expect((await call('POST', '/api/prompts/execute', ADMIN, { prompt: BODY })).status).toBe(429);\n"
        '  });\n'
        '\n'
        "  it('tracks revisions, clears stale compression, and restores an old version as a new edit', async () => {\n"
        '    const { call } = await fixture();\n'
        "    const created = await call('POST', '/api/optimizer/run', ADMIN, { workflow: 'template', raw_input: 'Подготовь шаблон письма' });\n"
        '    const url = `/api/optimizer/items/${created.data.id}`;\n'
        "    expect((await call('POST', `${url}/compress`, ADMIN, {})).data.compressed_prompt).toBeTruthy();\n"
        "    expect((await call('GET', `${url}/versions`, READER)).status).toBe(404);\n"
        "    expect((await call('PUT', `${url}/prompt`, ADMIN, { body: CHANGE, expected_version: 1 })).data)\n"
        '      .toMatchObject({ final_prompt: CHANGE, compressed_prompt: null });\n'
        "    expect((await call('PUT', `${url}/prompt`, ADMIN, { body: BODY, expected_version: 1 })).status).toBe(409);\n"
        "    const history = (await call('GET', `${url}/versions`, ADMIN)).data;\n"
        '    expect(history.items.map((row: { version: number }) => row.version)).toEqual([2, 1]);\n'
        "    expect((await call('PUT', `${url}/prompt`, ADMIN, { body: history.items[1].body, expected_version: 2 })).data.final_prompt).toBe(BODY);\n"
        "    expect((await call('GET', `${url}/versions?before=3`, ADMIN)).data.items.map((row: { version: number }) => row.version)).toEqual([2, 1]);\n"
        "    const template = await call('POST', '/api/templates', ADMIN, { title: 'Коммуникации', body: BODY });\n"
        '    const templateUrl = `/api/templates/${template.data.id}`;\n'
        "    expect((await call('PATCH', templateUrl, ADMIN, { body: CHANGE, expected_version: 1 })).status).toBe(200);\n"
        "    expect((await call('GET', `${templateUrl}/versions`, ADMIN)).data.current_version).toBe(2);\n"
        '  });\n'
        '\n'
        "  it('upgrades a database at schema v2 without changing any existing private optimizer data', () => {\n"
        "    const directory = mkdtempSync(join(tmpdir(), 'promptolog-v2-'));\n"
        '    cleanups.push(() => rmSync(directory, { recursive: true, force: true }));\n'
        "    const file = join(directory, 'legacy.db');\n"
        '    const initial = openDb(file);\n'
        "    initial.raw.exec('DROP TABLE prompt_versions; DROP TABLE team_prompts; DROP TABLE team_folder_members; DROP TABLE team_folders; PRAGMA user_version=2');\n"
        "    initial.run('INSERT INTO optimizations (id, user_id, workflow, status, raw_input, final_prompt, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',\n"
        "      'legacy', '20', 'template', 'ok', 'request', BODY, '2026-11-01', '2026-11-01');\n"
        '    initial.raw.close();\n'
        '    const migrated = openDb(file);\n'
        '    cleanups.push(() => migrated.raw.close());\n'
        "    expect(migrated.raw.prepare('PRAGMA user_version').get()).toMatchObject({ user_version: 3 });\n"
        "    expect(migrated.get('SELECT id, final_prompt FROM optimizations WHERE id = ?', 'legacy')).toMatchObject({ id: 'legacy', final_prompt: BODY });\n"
        "    expect(migrated.get('SELECT COUNT(*) AS n FROM prompt_versions')).toMatchObject({ n: 0 });\n"
        '  });\n'
        '});\n'
        '\n'
        "describe('team folders', () => {\n"
        "  it('scopes discovery, read, write and revision history to the correct portal and role', async () => {\n"
        '    const { call } = await fixture();\n'
        "    const input = { name: 'Отдел продаж', visibility: 'restricted', members: [{ user_id: '20', role: 'editor' }, { user_id: '21', role: 'reader' }] };\n"
        "    expect((await call('POST', '/api/team/folders', EDITOR, input)).status).toBe(403);\n"
        "    const created = await call('POST', '/api/team/folders', ADMIN, input);\n"
        '    expect(created.status).toBe(200);\n'
        '    const folderPath = `/api/team/folders/${created.data.id}`;\n'
        "    expect((await call('GET', '/api/team/folders', EMPLOYEE)).data.items).toEqual([]);\n"
        "    expect((await call('GET', '/api/team/folders', session('1', 'ADMIN', OTHER_PORTAL))).data.items).toEqual([]);\n"
        "    expect((await call('GET', '/api/team/folders', session('share:guest'))).data).toEqual({ items: [], can_manage: false });\n"
        "    expect((await call('GET', `${folderPath}/settings`, EDITOR)).status).toBe(403);\n"
        "    expect((await call('GET', `${folderPath}/prompts`, session('21', 'ADMIN', OTHER_PORTAL))).status).toBe(404);\n"
        "    expect((await call('POST', `${folderPath}/prompts`, READER, { title: 'Тон компании', body: BODY })).status).toBe(403);\n"
        "    const createdPrompt = await call('POST', `${folderPath}/prompts`, EDITOR, { title: 'Тон компании', body: BODY });\n"
        '    const itemPath = `${folderPath}/prompts/${createdPrompt.data.id}`;\n'
        "    expect((await call('GET', itemPath, READER)).data.body).toBe(BODY);\n"
        "    expect((await call('GET', `${itemPath}/versions`, READER)).status).toBe(403);\n"
        "    expect((await call('PUT', itemPath, READER, { body: CHANGE, expected_version: 1 })).status).toBe(403);\n"
        "    expect((await call('PUT', itemPath, EDITOR, { body: CHANGE, expected_version: 1 })).data).toMatchObject({ version: 2, body: CHANGE });\n"
        "    expect((await call('GET', `${itemPath}/versions`, EDITOR)).data.current_version).toBe(2);\n"
        "    expect((await call('DELETE', itemPath, READER)).status).toBe(403);\n"
        "    expect((await call('PUT', `${folderPath}/settings`, ADMIN, { ...input, visibility: 'portal', members: [] })).status).toBe(200);\n"
        "    expect((await call('GET', itemPath, EMPLOYEE)).status).toBe(200);\n"
        "    expect((await call('PUT', itemPath, EDITOR, { body: BODY, expected_version: 2 })).status).toBe(403);\n"
        '  });\n'
        '});\n'
    ),
}

AUDIT_SHA256 = '642b938a8d8c7e57541790b3c32234db19705fc31bf3bb4fc8b91948ccb097c7'
AUDIT_PAYLOAD = (
    'c-ri}+j1jEk|_ADuZUvT2nh*DkgO`T8oV7A$&%ROrG{il(^gdjCV>E%Vj>fjnIMZo!>ljo%$&99J!7_W9`<49tnJIbtgTtkO!t|-'
    'Osmc23s}D}Uvk_%A~GX0BLT23QmF)~TSR8Y)x+Jx!`;LE2e%r7C~Ta#euMiLtbY}s1^%7)=H}+s`+e_<#b=y741-=j4!q!$^~0bu'
    'Xvc2gGiT6oW7c(_^N7U(6<nNO{HVULP+weRA@2u~8wcT){oZ>IpaCk7zGYz$#5EQU{N{TM{*fKCz7x04T4_VAw8s|pX!oyJz1|70'
    '>QEPdx!vxKTc8SlzsK4xd;fj<g{_?oT(6^E#5{`ik5sqW4*WQDqWHb{4*0Wy8^YutQpfC$y|Bm}ze5v+GVOETfx)!Tol{=-g7&%n'
    'Wdy~#MOfJH9l>+obA0AT?85QfjuS)W6W$F%&MreYcKuVEZSt-&@M3lXjSl(|bKv8^@9>b>H0iqd(6HZIhvA0pGxq{oX$Jr?4}M0>'
    '^#ycz)UW|`?V#6#B@}-m7WlB<I0_$XbzP4~HsZm1@6nK3t?nQmguK;aZm%DNG0fEuVh7<Gz4xAa7oPT=FyiVNSI2Wt)FVPbGza52'
    'gAb~$hw!Kh0kC0(<U<5KB)<nIu$FBeMai41<Y&x#eH^rC9suaHJtvBA)^aH7)qC$fTtC|Qw6(p-R#;^WqEuwT&Gn<LY*F>)!S)V*'
    '=~e{N4OPP<z_H4E8~eMv+efY4t;56hPpAc;mL@xM!VdS5lz^&O(2w1o`;{YT3eX2ost+KA1!JCb6%692^4@!&KHB^25Ly@#=2q+u'
    'zd%fMT%U&x{eh6I(qtADWXw`OpcejT?)0o3+HR1k6g9fs!NrXlf{L08b4@m6a~JRp#sv>^h~9H-RD0rAZr0+d8=nnM>TS;zt&Van'
    '6q=j^tiJ>pJ%m+@pvL1n^YimHc5mT_cb*o?0u99*A@s#J0F42DI95s7Km92Yuj>O6dEQ*1ZhH{Lfr35uG%QZ;B5DU6Zu|yc`SY0j'
    'k*xiAj(3or0SI09)Yc#7YHaQ#bUI$!77f+`Ox~sIciK^eA1_>FH#UFX_kiTXxu=ERG_X}`?EAZ_@6a+<YwwBWltc|1FjRGVeUFz='
    'FmR&v*5>xXN~Ybt{mre`*52nUDFe%V{{h?fzvOM&QpAo9Tt0^N=-F&1XgeP3$ejh(#Lm=xxPNf8g0FKes(KgP3;I3o$71`i+*2QB'
    '-l44~8BMjxqI0*;K7j?jbgq~S{4aLnt87=BTc5YqA02(#y8n}h>xYLc`7ZbS*cS8}00M{51`E10n~lSVu&p{hUUz)h9bma4*zjN-'
    'G7UU9Sl``ht?zAY9Uko;9Ilkn)7t~%WWpewb(quX0O3V8dlYfDu=qoJ9{ycm&;{(WA#}|=>L=<2=bWUM$j&wR>Hgu-N>cS*UeP>h'
    '33k=E48rrS7hFb-wrgMYyfGW4_^0iFwA93H#K1S|B)&>Ha{Tv1x*T5&S8W`he+vdx)=*YFE?)|ehJC=yUZ({1C<+Icu-PzNERtD2'
    'apO-1Cu{>4ZUh1~h;%3?bvQ8Ds|d;M%<V<o>)LFc8kcy=SriOH_=BaT+)FqOgAQbM#Pb?H!e-;KbAFYhnJmKofGyhW5X8uHYEy`3'
    '<>l*a4~EQESJ>jBeUDlCR@!8XcVT^xuKN729lCv#bVIidgLwepbGujUUX305P`?>H^I%&!uCcFz4!di!1MUE^FMM2MpTm1-L+(NB'
    '4!Z<2XAVf1ey5Jd2H4hMq7jfVipn4&BRG$tEPrmpmIZBkgEr7zJ;XL^tmlMyYWa|D?(aSvgfI-79U&)aGP$+oCU_iyG|M}UC~P-G'
    'vvG9Xgd+vYT(A^k&=G*X=fK0}(LRe|%D}~roqj)RL_7r2r|KU-Jv_j0zoWih@{{D#F`P%C@#n|Piq5#_0q~9ou6)xEL57a;jDxQc'
    'lKyFAhXWi9vq1P`kG7e7jU{vl97pYt!}brozylnHK>9{3f@hmP!s0{?{6;*LeyLLwHm=TD^p45$)$wR_$7WKniAu_4Y5!d%3OF&('
    'sA5JH(^G}qMY3DQk6=V3`y7Ix0Q<`^s!<#d<dTS8h5$1my&T8kRilmLfdQVNMn=4MNz#D9vBSUI5kgOV76yaUGoTsX$CV^C1n<$#'
    'MQf*&G!X-NDFpe)?+@bfv-=1YI2zKG7rrm_K8}Bd3luxiIZ|SW9Sfv|z4MrL2OiSwLnn;cJkA%zrnch;zKdeq{z>F^T*qe(wgZIa'
    'glrR#SfRVs!3Qaj0=B!SXFzH0i3gZagSm9v(||ecHt~TN#7Uo6P8R*5_{xLD7M}@gs!L)#+swkz{QLiR{g2mQzxey>e|qt=7r*-V'
    'KeCh1<=rZAiS-T$jGaM`tpk7IeZ)c#Ea7BXqkbb8j0^OARb$*gg$Zy(QmXlv>mY7G$2FyEb3>rQXaJLjMHz6R7K;XbIIi*z?;zCM'
    'E*<XJ=E8sc>>oDoQ3;Tx0}nCO+FaC%H<=C_z=<O<eWlnVDx(HmJf|T_@XnI>Bq#>v;zE%DNa?^%K`<v>UKdUSfRnC+8Y%1e6ctfK'
    'S#TsiCfbX5T<^Nv>l|0v0EB6e_1x1CD+6-_0qfW-X&p1C8^gwc*g|W;+Q8^e`FLdfp^YlH_E|krY!)U6Ln*KH!1cH!@z(NB;Gg>L'
    'ZhdoewY401gVR;Je|3yFqBNVN-?eq!Xbn2)pvn&^%r4vMX0$w`<u^ymDFOSPgkF(S1!)s{97lt&3j&o!oml!<&?Zw_Wqg;ekrXE+'
    '0N-tT%^&D;5{uNE#Zk!tZ&W^J{+u-RBquS^4(hyfhfgfiWP5|&2@fr45Fp(d>QUI*8fjRn88zV?V<<Fk`4>&5*HBs=tX0ue9~G!Q'
    'r}x?T-~)CDb96y+27#Da7w!pfIeoWf+jf<dFzed@!vQQU0FI;lgVYD?2qkF{T>(u<KS_v#65T13hM!*sCx9>?G;+g*ra$9X+0lN!'
    'eSfR9{&2hX+15{J#KvLnuMbe%?e{&|WoE#AF<`)XAh_U^!}^CpKt@cEI$C6sNVfrEw4$y=#{(qluury*SmR=$(c{^{XSw;ewAN=q'
    '6lXz)nlA#`Jn6pXvyhvi$2W!^CIKGi1JgX@z>njHA-`~gL6n`^kN5Al4!1TAwvJj454Jwv-hXshKEo})9bUm{gQ4CKk04=i;i8ok'
    'U_+-_X02}>))()6RR3gS7q*2jV1BSP%#Fq8Hd!{=32X_@1@1Zp@QaO1j5s^et-VjS_qOC<%g4CxdBG*yAj<{24?-b(bb#^-wB=ra'
    'EW&&qi=#fB(>*vHv$HtvGfOCWq08qk$vOMoE}r(~CRaLE>hPgx+&JR(ot^zJ0J__sleKeYg;f@eLpSS*OZ361`uOq;wmO3ry=oXT'
    'G>%w$|EdprZFaOdm9iQr8tSd7NVm#vVU=_M1y+Faq1)bc!)(uoN9#x18)zB8Hqm}<OVm#~ZeMmRV1Sj58^w+O0A#RsrJ9A|XsLu('
    '&WPY`B?81PBWjIBq#3omZfcnzcXm$7WlkpL40--pVb2C|(zD}WC%EL{2B4l*wIkRPW2^D_ub({W4|hiR-@Vb(4;zE3-E}?Kxvl#_'
    ';Bf~QA%d}TYre)lt}f*y7Pkv0CUFe#0PA4qM4-=CVV{IEk<T7KHPwK@cjKsPFi(qt_ehPlq7E26r*Bztm94C@<GI_z7+?$J0Yhrc'
    'HQ?0ur1GRv9nF1kT(!RpT;F<9fmhj)&ZTXK!6kwOhTwSK@(>2vZJncVAyk8Gv}#ojw|2HRj?^di;9!4OiZLx1H~Zq#t%EK7#V$I+'
    'ur;=`y}NzH7C}g>)Wjrk7;~m6x*Z$^4n~373TcL+ExWY=*TOhLPGue69>QBx6pxz6)vAC<p*$^<ET@*^L$**YteRK_5PQPy4lS4u'
    'XL58Pfl-;)5k4%HEEa0&J9&t@9UY*BrC{t>gR$GmfVdO16^!vK>WZQHHMYLDiK1GF<<+ySzP-n++d~{ZL52WRS*u8dsMG*Is&KNE'
    'u&FUI^%?{54=NcJNlu&QR)n_ODS&j8o1=gYFt(8A5LpZkIPcbhbrN*0s(?11ZLxH;G_gu{P)UoPd(Iy^q0@`Z^zj!N`gr^ot*1yL'
    '6#&3r9G5g1J@cTgmspV7!#oP%-p87(l3S|Eh~{*ANbneGbaJc>DQ^ItF|kr6hOm7=6NC=R7J*>ivGsK*<3@djQN^|%CqzRNdI~M)'
    'UMX^VTI3KCfK#%DN|rTrYy&O=$PHE4kN1HE=;+#E`+Ks53<F6TT|oy+7>AWMtT<_n2{f?M`c+`0i&X<3gMYBuVk5{A)9!({R+<(3'
    'qXtk|3HYaMV-bWV7Cb{eH3KYwr-|h(epDMra4DEsa5-aVZ;qW!kl=)nUMj`SNk`rxYYW#vw-3F!7d82ex?%MugcC#1yMGm<ayg=-'
    '(BYNeW+UN$T_F=Py$-T0Ann8pg7ZN?TchJg4fNY}BOaOS!I4F;0FPzuOP!Z$-_{hTB{gVWHczxFLgp=<03gPCzrPiRL0BW->xbx@'
    't<@jIt~aKI&)pL)Ym-+u{oeBFcmTYP#<Owe#JeEQJE!Um*4pq~JnN)Ap?+yhPh#me2m*&>7gyGTM}4%-sCV+5wy}P+zO(;{>~Kq~'
    'oO$)R%P-}NhwA*B49RYY{~2uc=222RL-tkD#8*Klw|``K1|I(&(y>MzOySTioZr=8knn2C`^`D=xX`tUBXJ9l#4R`yFQJN%K_R#6'
    'f?(;KI_T2O_JRw#aY3yV4u)9;>*m&j^+!8Lt^4bTTiE1blO6DO5O$Wu##56U&}v=>i@HW1O=x|$4Rnvk@2J^mIDOYn-rMb<2jV^8'
    'gzvbyLgFQsXk08nq0=BZ^|)5(l>0n%&`ZH{{L=xTkuAzV?MT);;jvRVcsibY;+!~IQynKdi`vj*-SuM+Hdyy+;I~C1=)nNJ0Ep{7'
    'AWSisUI4&33*y|E)oa^vsa)xi6rGO=yoXyyN85X!9Fpo4&dUOID`leGH_XXy&S@m+h28^B;*31HZ>iT>TcT)v5PENnbMfbRohJS<'
    'FtB%&jYWe#wh#%zKjOVU(gc}MXB@7S!_8RR+ripOY&sr@LT4~stX0WNrg&aF@q&{oa)<Cra4G2S98U>cusPB!i&9IfrE_&4U1cAG'
    'G<y6WKl^`g56|UUwtlxdI!5sn-d2_Xi^)R-+D?Z7FGsn9hCGrD@tn}^0=}F%kx+o$x`mzBP$AyJCYsa`8t`yrEx|^CN;^%aZi{F-'
    '@nobcY~iCCj>Q4S)+`XeB%Rg?5(Dtjs9D5mmR*~iVO4JRPJ|mn7Z8K&dIMrPf=|HN99li83Fnq3`^t9xE)SQH;)AY%N3B+ybng=+'
    '-Q|?ktQOApV%6}N1Mn?2V-v%*sMo^TUDWk~y(e{b)+y`Kx}5S@=YcStD(R~BPw>)(jXY<|2Quf8C0}v*NGGsFqxkr|#x9=HN$Omv'
    'w$Vrn>q|QE3wniDD!b5Cr&?vBf+h?R7l&-C<*G90(s2>`aFmG;oi0bN2AgEASbp|NLkX`W?Yy|nM8mn2>j!z#CBW-4*&D69c!#Q@'
    'inKy;C$$3%pmP1+umAYs@0n<?e*NbcKfC_=`k$|Vef|6E-(3F|o_@`)|McRQ*Z=eSx7UBlTVcvhr?8B$R@S*vSO7Ge0I+jExbz9C'
    'u&;*$IOA^b9c~>QvF*L1eIS<@FR(@yX%fh@r^-HG-+8okXsy-QS`{@D8~b|?cD6T;uuzq4?z2Y^>E0#qA5jHy<ayg0pdS#ufJwq?'
    '{`hcz&lZDmyI0mlwPfTS?qx=v8SN$<jiE1jCKjWW2V$YPSi{Z=xX@@QI~(h|A^IFR3@9c-O-|MZ)&uaeuH$;@Qm^A*#b;Q~jhOUF'
    'wvFV090&%0XlzSdB}7TE6u4meyICv<2X=XC=YEE-Y6WcoNzW>R4yCl`Qll}%#kchBphmO{yjd}G*<TfbZ9##SUK+}A53noc{McT;'
    'RE<e~U!*+Ar+LDSkPD1si&<Hv!RpCB?C|j50fQ|$?2vOtP8`unn)qzOVckd?6W7JvEX(aD=!Gjmiq-<l6oen!ZnXXI;x5#wRttiO'
    'TK&f$ES@}t^>_PHwOg?(LTM$OVu1TZ?6FV3VLj;Y(^BodLo2i}k7_shd+~?q1HHH8hmU@QJV>nR;=Q|7{o4;0#W&j8#Lwjwc4r||'
    '=tqlb0}CI0ocT6CpEU5%-J}5+%y_+9vf*3^kYse<CI)+<+l(sBW*7cxR;sBLC%=LhQk3{%kr-r^3xVa$<^pLilSlEC>95<aR1I%C'
    '#<%?A`5f1sYL_o=JE3!_VWHZ@0j-O>H;QP3CNlgy@Pte@05Icz0|l_zsxDKF*^N4hEQ1?SZfj}6wgX$vAFjWC@iW+k;Ma>^z((|U'
    '*S}}5IsFD-z4&<ryUJm)Sb0aY;lt=Ma+hx3H(|p7_u4pU2cFpbg=8%DS}W5qywM7;sKSIgFFSDt`|j7*f0P?80O8j!{`UHJ^!FDp'
    'e)Zz#uvx$OIaAVlaR(MNK&`9q^hkjYLxknOgtN}8j0#pGJG2)+hX)}e{7*4B2H(EE{udlAyZ#-!{xiHrapI3JepN9_NIEbRVjGwR'
    'K=jr_LyL_+aB8V~`>&rodHmBSPoCbEI&SmUjyGc?!c@UjEo`WYmKywl_8CivXhNk+pKE}@Fvun#I*1mds!eE}Y;`Y>+%NtMAokB+'
    '{6fO@PfFmr{uAM}GF3a&kz>nSy~f2BfI-|Ne;0ftCPVYJqo4<Zb&h|%3VMPp_y-v6zXB<unD|>U2apo~8RbMk10>cz!N0%DkSa|1'
    'e+LTwnqB`Zy!<o0{NJeL*Ojt8eDIRnb|NY}9j6ZheKcXGhSM4+XKtlIIdh~!4CJj?amgiVXKBj)bBW<O+DkvHZkw8trQD5ccJBR#'
    '&b?AYA^IjX1_2*t(#+_~h|utLa*{$CD)jUiOQ?l@O6Exrv=UDA<VoYh+l?X<s=QqX@gb8EeUs5)3znAdEkv;XE27UOW5xC$3^^f-'
    ';izq{qJXtQ_ZQF(D7s1yw3*X1?y05%vghQbd6RH`)Q88^O}^tbiNm5H5SZmUH}Tjr0=kf2mW%?$RQiXc`wU25!<l}V;}7gxJmnjt'
    '?NV(=-Xbtg*-<f~Plrcv&L$W16oc|h3uKs*w<Xt6I3;TD#WB>ZnG(lmJPfbp4#1>nXr>5iM!fHw#-oxuwi`X&a&2S)oBL+q2gU<y'
    '3FiK&rgX+F1(lY#@g(r~A3>D-ISChE1J3>drOV#{0{;#$_78}>zXP%2-$<PJ9SEVngR;M}+4cXp{wEYLupr1Dzh$zCUt_TsfAiv('
    'Qc8saD4M_*DrQ#<j%}j?fXeh7Mo3OpWfUNls6jLp4f??p2%>s31yxbwlBe#%9A2kR<?R&Cj5o%|%?a<w_#AKLQE0qAh;ww)MP4JN'
    'yP1gqBq3)L(a^}~zN!$s(9?Sf<R8yNV8~0X>b7Z_y*?*9@B}o8<j~=8K$I}sgx@vR6NXE8tC=w$KdrF<<9(sUbS+Uw0sNfj;!^XP'
    'f+-0H!%;!fz}Ctn4G@<~gauikOA>8Avb$(Q-UdLTCpbMUB@TgdBv3T4(<dkgTi(2Bch#jdK|3nWQYE*UYR-J<6DYPV8W0(Aaeb*Z'
    'LZ=jlcrc7p18fr~YR9@oHW{ZdMmJ&T6xnfPAoWDXPOv((<<DAz*r6Q<AS0_rC4Pr$WGRBDb0xWWZnB<CZhztu$Y=bjK;9Cpw*(uT'
    '#KG}EAQjx2@BvKr@9<(UvEM(Dq5w{VW>Eys#CT5p4Hjm=;{W*KzrFZdx|L!T_ktROF2rW=_4OaBMfNQZPr|v-aC|bW)YGHF8#xms'
    'Fom|O->y8TNM^FJDpSe~x9AE9RS`;JQ|pnO(X&I~FM=e+)pV(+PQFXLS6+}$p7`*;O2RKfPHLd>&EL|S&rg=l(*+VVbB)BpUopwx'
    'YQ|qCj04qj=zwB%YwY;;5Fs@Z7aYZKkCAUwp4Z{{RY!B8Jb$JA)MeB~_=15%@6_i%s?RS}C{SY2?-d%8Y(QsG&hwVy85$GHaI0Os'
    'Y10GvF4Xdzt6GyW1Dg0(-!%~Q`dY!62cg}RP_L!jD_KR<WWm^RmIk($xT=e@m9-v*&Xw&(^w;__K?RV>lLvI8ewtcpVY74mD;mzp'
    'nk`&XapAB@g;{zT8$T%ADiWl^gj-ZhBg(`%$htSb2n)8g`|#)|t&RQNhahon@9!Z|?jrmpFNZzf4-`P~qi|p~_gG~A*nP_R<;CVN'
    '?E$XDnoS3ExyHB)&ZC!gzECiT^QDqa<B)_RC`-@yF~Of|W+zGUzqpl*2{t+toZh_PG?R*EQqeaj6;*Olk*;p(o|b^++ZSw<){=^?'
    'u#70TR;HuMN<w9-pQLs33C5D0uI0RB<$G+G%9nsS!uY=E__0#%^_ijPn#RIO)j5t1N!>Xd&E&W5ko;!bwxzHlvzB=`pCK)7xx8m;'
    '1YOu>a^FnuySdy~;?;Ze>Fx5^!Q=~T+J?Rn3}EH6bI>S78?f-0o-|tdrqPhD+BM}voq9so<ZjVq`%q+kyPo<@=VjKY<O1sic7m-m'
    'v{s0xU}%OQl+o#%?D#%+LSSOIhd@E2<6NBlxiQQmk;Ep-VP#B4N@VZ9&x-t1fUQCsjLbm6TPRdHaZ_I4fW^T2t$-YC(Xu8s8=W5*'
    '1x-chE9}cPkT3(c&7(E@@%+;@Th3}tF@q%|`<KR1)sEOi2;(bno}?=#j4vl;!tqxl(#-0N3J!77x^MAn$!^I-$_u}ZKuds9#cMV8'
    'r4s_56p{;_u*fTwM6_Ya5O5pl!0N;40RF;KyM70s@UOv5Q`v#|cu&5m%?e34!44A~a9Zz7?b?v=3Ad0-X|8e7idTT5+{5txEgCh2'
    'Z>;8&bbNeltu>Jrs%uZ4L?1NVT3#_2eE@}S%MV65N1+s1+k~Y#&iL0gKA?d9u?S8`p~HIU5G2SC4#6c?lIh;CO&5LkyH;hGN@#RZ'
    '+4h_$-d0~nW|d)t&Ku;S$=NE4s;0q8-xJ_1+z?Y^PB#Y%qO9x%;<PVk(8T~}Q@K1+%td){-zOZP78&L3=tRl+!@QD+KG1!KW3rCa'
    '{d*`PMM_>Fk8<cEC9n(#;`sXi5{_`_=Z0=jcuc`F${+Et^7V^f(5qj-7va(<3qYNJV=w+QnH~QP{pYTK+XQ|u`X3z^JR3&^HOdCi'
    'rHBG5h9&Q<i8x4UxKaY9x+`@o!bu-5VE`qhX_O$H=p3Vaw>hw&kf(v%WE(^!2)HpZ{AOGJTd?KB?yZD-v6YYCz)=QB2UQdY#KvtF'
    '74W=ZkZ9RED?y-H=a&4S?m^6iikVO`+kw8t9mwdl!RW4zh5ofpjE5d%2=hzH!!lb;9zOiAJPuK+_|6y!gn<AED>@~8w@_oFf4HXI'
    'Ze~>SBZE_rq|y&pNP~^P4Q2A0u8OWbAy8919^r==IbBXy-mRiYn<&mrG0g<!istNSK*6}HDcivvx+#0J@j)@5aoYB<jEl&P0>w*o'
    '<P)umwRNLtz@s$a)E%kEaYaa*+e6o;2!TS0V~guC6^uw-86o1jip!5wFsRBBGx~DrY)lQsLM#+AXjL_|R1lsStveKd3>%$p_7EDe'
    '3edkx**hvVgV`dT8=7cnKTB%jjSaoh@lS$5h~eld#wSMK_O95agJIc;Dll*x4t-R`tS0!8C`{1K{@#|Los1}r1~VCZ3RTM@8v)`D'
    'Fetzm@5*K%e8a*;ye77%4rg7CxwUK%NS=;~IW{A?gyd$#HY2vzOl%V(VyOrcfnOdK>*d3JBym|}1d)T_vWAA~L+M~j=_B~_&7eJP'
    ';1;NiqG3%BxsnT}QjE7UeRvgUenWUFe=dwMlt6mpjJMA*JD_a(@Z9x0SwL$$!q?H5)(36}*XwdS3bZgYHI#5C#hS^8nsb@ROFQd('
    'pFCRsWUIBezKc140aFKnr!Ri?;+HRe{^I9&5AyooDi|gP-jc2OU(nC_`uFM^vq0>G>77;azyz2}?N07K(SuQnzoXFcBRq}q@Q{o_'
    'ma++nM~wZcqLjcu!U3F%P$q?u5#a6zohwasCc_mD%K{wDkn+tVWiBvMas-*->O@>EIbJY!yc{~0<hQ`1c=h%Wp0?38H(GA!9}Hn8'
    'kCy|=W*V)EW7f*;VPMM>*An0?-Q$q@5c-yV1!XWf5XD}k&&d;Xty(^=8C+@5I!uAZ*KqX7<0=J6mJc}m^b1`TECd~TS_lxE*!jmR'
    'X{S}ff9KTiSTGKh7XJIBcOQRUBcacY_&God`D0UKrnws$Y&2zS2Ry?3$U~`-X{KL<#-(@@q^+1NO*B$HK7KkrTl$R1Uk{OgXECCL'
    '{o^SYB<^jxhzRWDnVrhtEw|t#hQ$@?BsCC$jMr?Dys7c>U@xa4W;_TKNx=ON#Fejf9O~AW7V$kF0UjXDW8P^wG21?5dyjT@FgP7{'
    't>RJ}d{)Ru=CoR59-ky#Q;a?n^AI?iLITd1rzs#t!cpw@uy505u<l2f=+;YVK}N@tzZZ{}^6J~1ycMZ~0B=Yp?c=;_l!jt}Ecgk?'
    '1HKPy{sd-CgiKXd2oM?I&DD}YOZXIn&xpHvMZH0aCIBk<1(N|uEfa$#&v$0nRpK&ww}w$n<CZ`zbQS#vy6;I&p)daC`giC|n-8XO'
    '{p(6eKc}|D1v2t<LZ=(I5<IAk@#e)bkd6wFr{xGNrQ!VlFMfgQ_J1jiO1P^skbH%o?>~`B{?}!rn~_MKM2w6W?GFcBP6p&IvMGff'
    'p^_21q~ozJ=N-(Gwj|uR@$LYwDXy*O`sb9tOn6Rs9csh6a6;FCEwp{+xPEoYYXo635V09qeKcl@8wE=e;nTaQ=?ds?L#nC2QG;Jg'
    'U*Vp)mfbW1|1SqY?7&+q%!IAG2wXIhrMC{m*fx*$%i}_HPUx~iUkRnyAFU4kfW?u=WUJ)z*PCP?eOm_{K9_KkSKOs!dKRxU#avoq'
    ')eKY0ux)wu8rid0<os;RbAT}zW+COBvKdq~M{Z30x`I=&>Bx&Cf#bG1AFD;CZ{oH|R!2d)chO9VpL#of-ptB%D^jvc6xNzn25(RR'
    'n@Y~@En$r=&2}~;@)?m&PvmbxSeWsGZ<7~HuzU1?cqeCb>)<6WbUWHSv8qP-nL8Ahxa)w3VxF3$5Hnq*K?nQ&#DGaEO29}9$*m@#'
    'Ks~`|MHU(Aws`SPUcK)3Z9JiJA6gLkZDkNGe5lFfwMnAdyfX|27z<7@YE)oVL_6Z%nXxf6G*WIp`BpyHST}~lu}IitaJOkRSmTU4'
    'UVQcyUdyDF>8Q}P5%4uU#dlrbjm~(q#4xmY;{zsTW_EA>4*L+edmLWX*D2Yx$Y)P*v2y^9c)Z=~L5skBEy0(|0@sw8aB)EEo+s{5'
    'sx?O=@=~e27tPLu#A*r6_ElxFjs_ux<LV4N9{xBuu~aoc^fOpUE21H%3lpirv@qzthZkp-3|EE7zAlaA1C*G9E(4TC2p<f5A|`cd'
    'UnWk3{^5%yEayX6Yh<)YC->k6J^sj-3)Z2khTA(igDy;l3tmKVN(X&XUPZcZ7kp1V&`g$J3ZR``l0q1|Q3=g;pc|}(2!g7i3&%^s'
    'Gt%BTc3Cpv9B~k%8e6;zto_sdM+dFl!$POjojveF-Yw$-(b*vGpvHQIWd?#2-Sz^?zb4Ruz9#7~pS!U&U&S$uQ4f3vSz6_0EKR<m'
    'sFp?MIAdz%OwI6l#^zpz%@zGtOinegi}4x2Kms4FT{XiWHqb|8g)Nl16{$KYy-9{+m|k8%^F8IS6GTirWA@yycvuhdZcQ{X?VL=G'
    '^T3H>w|liMouO;$#euLICD!+@cwJ`KACqGz*WvVOlLr3HTq9%$+ba8XTFDv2XJb0TlkyHgFP^?in$1Z#GfbPkNse*aWK701Ti^J~'
    '=}S?&S@NrQaZQXjiIY+6KRjwtzR1Ix+-&87j7y-Us5e&>+xlYv;Ijui`(GTsL?WySX3l-ZGY*htU<esaO=K{7a#ZT@XU!a@5%*Fn'
    'yu_SN&-JG&nZ%)3YchGGg<i1<VR=x4)Q=OOg-r?5B$Q+gbqpc948rrS7hFa)x*3H5#mS$^b5BAC<P=iQbpx*h0+G!?I$?r$G5{+@'
    'DhP$tlyp?4f73N@DD8z=$VL`$>t>N)J59q9RGVU#DA$SMO{$szGpWZCl}I8UiM8w4Lh?<(jIYwzA0<&WJR-Ukl|4M8!&A|{QSXuv'
    'sC5kRX{y|+qvIM|n6I&q=3D5@Dw3((^6cQ;tN~j@Qx&$=qK;*7mH&rgqyAUvg?0UJX}}p3l>KXp>i^H|`VVNY`tyrlT>lP=VRY4B'
    'ix8<VehDpkc8C%#3Al1YoshwBM!s*9eD!S90!)BPU)jQy2Tog<JNhdbtrx^2iUfiV-_Na&=BowSZ^jvBoZ$^{h7x}odF3vTQb;O}'
    '$h*Wr8ovtgdKu=x;`EMI1J2)Q*1-@~a8&oPTynp%%JR4LP`BFe3mtwI&18B~7{7iB&xSiL=vT2V4Cp+mEueV0mNaI1UP@A2WP|?K'
    '%9G=vV+UoaD`ve?g9)Ot(KLW2V#AOMXHR{I(!+8daBmYM>Vf!Y8T5fuUEO(HdiA0r?o%XJ{xCio=Kl;rAcf$(!bVSP;uf;H=d(C('
    'JT@nHXo7QfImm-y`|Yb%50geDQ($$Nl==Ql{+5m53helx^$M92PFRM8#>EN;z6oz+Zi5cR&60~l#A~^o#5|_v4{b;uN9H72gJEKw'
    'Oe%<l!SlFrmwh#)10wB3ji%dah`s)mCncJ>*}Q1*VoOBL3x<NS(M{eUe!Q;Ps!i{e=c^ie9Wyp$$tyuxwN2lEanjtUVJwE}ms|pT'
    'mK9z4<i7uv-41xz1_~B;-eF>XoJuk>Neuj~v1eIP2V|T@*cWZ(Enrn^QUocK`zTw?p!DlH7XfZT5!U4}7VB|k9yid1%F}EYiUA}A'
    'Gg7Nw7Sl?l_y<@SUYWeY1Y)4pTStnButLLyA<iF~NhkTt7Qbrx=;5V$5OEnW8*n=2XSVuXlM8@|h4)=1Web>uD@Z3rd;u}#D99i?'
    'G_Zf^qk8tFoRlRdDe@`Vqe%yOgTYLNylUG6`HGAvlLxDjc?ssr{J6T@9<|guAtK2bvz7^)TX`8@BD6p7Jj|$VmEyKkAYV9Pi}HsM'
    'a)*>0+bT9#Gf>xjH9Ml%Ii*G%3h1Ymm$x*u^T(a}s`&A7IZY5xF3GEb=}8j+R9SH8KcFXCitN|%OHi5(MGFr|?P+V0O9Y(c;gFt|'
    'fljF8YpK^IZ%g$=UNGn`qWg|i<P7v$Yixlv*}U<K(9c;ITNGElhS*6PKuNU2EO>4_nY3ovz%|fMGn5nqr|3N`Z0bIjohIM>bmKuZ'
    'o?;|eY>F}9C1yN|9jdIl)cn)&W0}~wI6#!4kHQFZAHon+D$>i8S7x`T>_~Fm%Fb>Td&|K#<fNh@VlBy@qr}?64q+^B-i?H(+1tAZ'
    '%;`(5C-IpE%1fFVfjX~1t;(1cFC3I!`jjJ8IX4j)WtAetaks<uXp)R0n7EK`a=U!Nc05itFYT@!a-bV+ugLaN(|2LaHd@$QQ;nu%'
    'b9<O>^#itO+PrLR;wIvW9QUguCq}2vZi+91n@F}@C1tlL6Itm63CZ*^EiQmh>6he<hu>gISjy!4%NPHRGQ`6F|A3je{v^T|UH>b('
    'X8xHxHGfMgrr*jGUX)_CQX2e=vfZwXUACh1VO+%01vJAY#~&92<tow;G@EyQm4g)z@P2ufC|Z-_u>^<*NWqg~&7T9wh+8QCw}9yN'
    'uQ5w70sRjMMd9fBuM|ohbEN$iLqExTDZiz-@xL<NMagYHYEroIBvZ(5IqASlSx=tAQ`ECT_~=;HbHelIHns{<iE8cTS^f8$o?xXh'
    'X8@{r%NIJ8es3oFY1e`BXr7S}v-mBR)VS$oNhhh?HS027W=G3=)y-7UZ;=XG(Vlc|SkcE^kPejwO%$GVz<&F5*$eZFcW2t{nKpak'
    'ymZ^HHXZT$T~};Rocv73J=1Z2$93FO5cpfE?w(@Y@2cioJ3Z2cQt0b*O5*)?Xv5j9719I0idI~b<V-m}Q;vThmE$>8c!u$bO5@4r'
    'Wfa~wRe784ZoDOG@K@X$CUKpY)|eY`>4rM=Q8}-i>D9lVdi9q__L+)(redF|*xwn_nrYi}+V*MhSWbJna{9ZD>GeAOs$ImLuzdzU'
    'qiNeo@4#unl~ugu0Y>1N?oQlLYLrDR=3I7fc?U4fJg&7W^Pm^5vZ!`*@V|esz4^&jYh!=!@aSNDd+(^mHn$$EKiWBJJ=ovb+&Va{'
    'Wv=A3JvhI1T^@>vnd+uZqOHrk#Yk{H*yL5xNEy8MKK$pL$Dadm0DXWmIqFyTyZIA$vfSBLY3_pNH;?w^Gf2M=VE{Z%pT9_yHtJ16'
    'Etz_{7C5Wsdes|4D&RO!$^q#Lmc{mm8rZAVGBeXl<FM1F^w>K=`@E(hbO>D7iR9}PqiZ+5-}|Pp`<+4N?=SwA+}IJ>-9xv75e(#R'
    '(5EY6<{M6JRNYbD6j92K`kouhaKcGSXOFhSTaAr_?W66D^&Pg2>-}g0)2B5tSocF7VyGyFnZxM19>#uy;|5?GjK1O8XkmnAGSP}j'
    'BHi*k#lV<y;K#Rza(qdA%>u%Wj+e?4h!vvKUjWiP0D&S^HD{Jxz@QL${_)c^+_<W#a$5KLX#1lablFcK+M6Se>GX<-Yl)t!lsY>f'
    'QD;onvpxp=!r&@xK5Y`!qN*ZnB8pX;c?2(s<1WKmW9mM|f|d=)xoU+{FN)DVMv2HMW(u`su#FIfT*qt4_Y@(uIwpP545KsCoT2h}'
    '2$f5iv`i|1pcGELfMm<!Ca{XHzG@xI6E*DdrP{N}VH?E}JEOgy&z(qA$^8S^ui5>dNIem?vblA*!D#bl^#!*7-~pa_){a%6=o&kK'
    '!^$2KO>1NQVc~qI#SG#YFNmgG)y`E@s|WcwcUt*z^wKFVC{E6%IE1Dr^Cso6$zA<5-AGRG>&&@82rF%Qva;IwR$pSJG|@g!qdw7#'
    '<KpcfsR*4)jX>$bLSfp>9IguoUTuZCxI#JUtt!|r&dWY?A~>p3E6Mr+*W5Zd0@PvKpX}|!Sb=}-tKnO&j3`cq6rmZ>22;}zt;#-M'
    '-+8okXsy-cztu`jM4L`=t!pdo3e{FNf@$(kCrh2xy_BqQA}S)coD}eFM#kS38PDi<M!z?rU*mQ>b;jYWr=3AuN#m4Y_H@l{N(GNb'
    'pQ&c%+-=5Z*N2KR2sR~CL=D5UX5l0%^8=)%h)$dGJUJX?GHDs&X%LEv2>;5eKsD7uEtN#!NU{{9E<BXuTuECPmjeb|h$km-@L1v?'
    'VP1xLWbrR;T1>O1_nSy-NiqZ-J8PP?xrnI=#v0NExt$b!#||K8GneD37Cz9D*lEfJkQpDNDc#3*;Xef+OIbaiUL=b-xoGH04YKXW'
    'L4rcPCZT0b+n>ttNJh+DYYKNRg}zS8`yM}qQiC{vBGUaw3v-SPwk*PV-hY?UijghS79PA5$yAL<rt*s{JhMDY1}6H(JojZ9pNu2#'
    '-Fx%%r9l))f`6z4d#B&`uI|%e6Qp|#OPUe!31GH7jOKSqh0mq7f+T%MB{;7nlM((juJ6V!^b@r)mTBfy8#a6wRz|#46Yl6m+h>k{'
    '$}!EQaL&<BCE|_J`L+fkOYT~&U^_?>)lv=Nl}tZHil(&YINuEe4dp1na?;!=fcj#uQx-3$iY^}l@EMR4-YTdhA98>xP@XK7fT{&s'
    'i|6>XJ_gq_4KI=|vQVsL+_{t7zbb*T?!@92O<%gV$xB@0#4DTyB?Dpa0Y`^-Hz6yd3&&`hoC*d1?i?dAF%OLm<c{P;KM@p7ke;&2'
    '2B9Lps#Hr2lh3B&AseEdgoU6Pvs3|{;TInp*+tU3mTu>n#3|7gW*thtrYVj!D|_;_^nL>^u)hDNOIQ;;u#gamoNkjrjV9Z%i=1g%'
    '($8bzGmQYADFS$w5WqMi_ym_*@~KU{X$v+?qx3!n>}1-cqTyGhloVK%+diQcF&<$E&&F84@d=2IIKsqj2&Mk&z?p`!jh7t8NC_vD'
    'j&-PZtW=k{L>qA;17wn&j3@t8ASk+~Wu~`eVj98an@SNzA=R#b_u}U-eszQ7U=>ZlIE{7@#&6Ou>Z~PgLIGRU(*#`DJ<Td`6Jw@W'
    'c&V-!n@R=RM35C9G`Y4<CbA|?%oY!%=frgfxQVomGC8I!m3c>n{eW(~#qdX#!JqmkAyPHjty}b2JZ3`FY10$SMjR<+w<JaYiMz_P'
    '4#mZ$bnui5{n&jfm9)|s3jOL5lRzqinAetM&K2PxOuv8n(_|>N2U}5mMmyNNIcvxmu2OqL^AK`!nJwZCGnta>M5Sz|oOQ7G0d@VL'
    'b?RW4PRVPQSma!Qu-9+LDtRayy-6m6cLZU@Z{d4gz#h+R&XCW<K})-(g%KTrg}nG%azsK;wHN;xgEV5uMhw+>{d?dtz;-CIBfR|c'
    'i(kAMb|a~5B};YYV^R>hr#NZN_>qT0(yYkGu#&UiTdIkYgV=N@!wm_?M663%E%PFn{wUaX{Emw!8}mU>HIGOq&jqHFU<PDpAcNMF'
    'tuD)TQ-H`C=Nu*~tEk#GU2nFm3*o}6hN$uqN7nJ<+rx{|)8lGcnh;8LQCN+nrLxhVL!ER$@4qh_T9)fua{4WoF$>_!NSF!Iq_5P#'
    '3u37L^x=f_Xr*}0g_*5sYpw2_h!NDpXVG^vc{$CYF3rn8`@|~=xQQR1ZQIaXEoFbV0`w_LSsx8|*NM;U5R;5qmL)-17n7*6hMYwe'
    '4weh^^Ju7@&$|UqtprtfH1VFG%cE&6x2Ai8X3gd^QaWiF_k=Q9f1z#;u4$WrqAIPNxHzb`hAOrzz3t(2fU;{G#EzF{p3aspH~hRc'
    '3gfxgrZCQJxQ{F1L*=O^nP?saD=2#E%H+A3GWpw3Ca3CzS5+Vj=x-lw?Y4Hd)(^K@yN8&}W*%6E2wpwrZcI+@!w3u8KxaGX0=ay&'
    'nxJGx?>z8TVk#x{9j$5-;8B?*C;je^(|G5%hi)hDGLzWzh<7B2Xh^wzOLO5AH^0b4btbPYXCP8FWg99L{&ehXoeZL@>5rLs*W>T#'
    'vchlS*Uw-4eNq0)=Lj+<p;AE&M0O>h4@2^2lHoja?Zl0>0GjbCnaad?_-g$yxVl1+Jh!Wfw3YWs?u+SIlj}4mDUP!sKvS<`E-)MF'
    'a340FZ}RL{$NkKtYBKF?lda<-@eYXaxMoLJeZDMH45&e`u1<1v(nI5e$SRp7w*S@|D+=P-RK|;GHI_FK6{j#=z|z?!^Tm(>tcjbE'
    '0mEdzC^23bO&62KG0u>YIk^}NSU3gEh$Tmmvuqex0V0uZ?hr4O%|krhKt?V(k(b;z)r}>gVUIHyK1y3E(R~z~o$Nq1Gnjl!29uk_'
    'KX?VZN~ZUlUvd8?ttzj_u425eUY1arG|B+F;uSNcg{J)1D>?mV2JvuLE+NtJ>pJzS!tPaWgfi^kdJ71wcDhGTx`TOhj`4OFVy4uK'
    'rc09%@snEPv!uS9BKGaI_arDNa<@;jp=e;>&xm^9T#NNn?QCkGq4!1$4Sh+TP5EGTGf9*&S)k0qWD`av{L<!!GWckWBIm!;WVhtA'
    '9R)p}m7<DF<yG0rWX2*H>Gb6A`Z&oHfkJN1UEU50%s0qgN@;Q0EimCYL?9;X4}Hj*e})Fx;M*_>6}M_O!6H+fOlc4>VL=vrqoBxN'
    'Gd5f(S4|Y^Q_}X03_-=oyoyC=qD@Ggc*+bzI#;(#tVAzupec+kXJyK59g`c1;P5Bg$h4_jwW(1RN-g>F{`>h4W^)y_mYA$As-;75'
    'dno&oT%3$5V|$8Xb9^;bu{t&!(c5pGB2Xx>rB*5G?q&yVRPJ#v;x7k~v6CtUZ^{nK9G0nM#b1N9Y^=RZAx6e(mY`YIc2;IO8)G@U'
    '(LO!1rA@dK8KSjJ-K9$IPK|Mhy*<1fO}g^5IImxM0t^wsX===pQAO))0ga=J^W}C}Ia?f`emh5n*zK5)0BLYtaV@N4>&7R1&f9_T'
    'ow5i4L%MJ|6-&hZR7<jO7sFl(X4TS)>RVu18e`BJEK<6Tl7^R6TILj!Sfb!&orwn8(IY!%f`E4Ppo${wW`_dr>9#d|r(4?2oT!y-'
    'EtJGHzX7chMbcFOLcx5z*eU#$hQ(knT8NZP6XqL$Go+m%?Kgw8lfpHHybD|LS$VLgo5v?f1ISQp65M7~kP?cLbeN=>j`W92WE{<q'
    'IBnb;OyeyB-%xjHT5tK{kizO5kl-O-VJ-l99MHPKyw77gf+=ha!Vnt%90L+ybes#vBkAk#-1WRo)HT%vog^j12=KFfrS%u#>u5}m'
    'bbL7q9X~=BSsor<ML?&u!uv-NN_;Zl0v>|2PENVcL!#F)9idD+i1{8gv2n(6A>^9_%mZCxoq?DlEZ6R%qpiPc?XB-_sozIOJFVTr'
    '8vAtpU=uF|w;paCv^KX7AFdy5d<uoO_gW9vA02MB?r$A^v9-0=I(W2qh;9QKB;dT&8F(UiSjiX%bhT8*GtxpFMIPsURD1cI`#iqn'
    '9H73r{u3G!nhvK9d(<YDu9X)r#?(04-rd@NbaXfghm0y1!CAlfbo*#)XZ!G|slxb(MMhOn;?9j~v9f?vGdlfl(dmpd6VfbWS?>y+'
    'PTGP4SjA{!xWpTh>FWxXSWd3fQzA$hfp@{TWnv%1gqZJORuS2#`l2=I4C1q~O`c*XAY}>T;Q>KWYanslsiy#*7&5O6gKxBfgaiMR'
    'grt#2N&@GKrxDA^6u}qjt40hGJWzD&A`9`Uc!q%kqAEZ>AjTlaI0`mV|B>Z`P*wiEf3@AY2@{0b?>hbfWmGph5aQ+iL3E|iR=mjt'
    '5!A%c(!hyr-j5Fk$i+EYp}uhAvvvRKkb@+Rj;WNL=~M2I5uC!x{x~>!=v;Y$)1d=I8#WMlMNRaas}sKCe03#xDNGkWiMI4{eHolY'
    '<Jf~SDCCS%zg<dw$^GON$#zDmZ#SiuXc5P`ZORbYPN(x}5S&|;z(3@^77x2cCh8E=#Nk9}0>uE?G8+;Uvd?JJR^_ki8zReG9lbW|'
    '`+em<RPlqzce~w+F`<&)glYgFF$jSm>kk9ZZKKQZv5dG=2jPNMBJOo7OU&(^YR}}t*F^2E9~)jr@s-E*_mzPkIbB|NeGgL+LWy?h'
    '_Om^JeB|?X_8n=(>W&W!8V6y-ZVw+EfLPjE-`m(aJla1v934-bD4-z+$_Ud50+8yVd^^TfM=r>Xaz}o5umLSt*rPoNJyfNIafEax'
    '1G!hK)jYm9Aiz^cVc<z1;-c^ws(nMKHr9+0T}9idU9~QnAO@Vn#)k26)Y$^DD3ZT3f%7j6s$AoCYXR!kDEa_!Wsm_dl}Ak^<D52+'
    '$>HG^JL6s-&aMTE6VpQpasN=n^l!2UP87oqkX#=kcx$hTR?;1EyR)XbmJC4%@;h)S;>~1ZC4$0mL4XBb5OH-UghI59j8_t9h21Zm'
    '_PHrZsQ4Z_mp0{s#cc`G?;)%zI$6TutP+D<(cm}?Af1pqJ;abKVKoV5+V~E|lX|R9{ZMp6pe@W3O5sJxy5qSQc$pnoz&h-jUj6={'
    '3&@7?Ca59t$;cg=DR&@czokQwt>N(hs-6lf_3aK+$&?wfCf@Be#{bAc#i}%ET}1?16Crp!77Kz%+;zN&mpPf8ouH+j$J=<7?ZWYr'
    '%n5Y4Mzm2i4dCn~=^oQaF3>F_<Jg~3#lW{J)Eodv^^pt_GaW2Z<litE$l1w+90>+zE`_1f%;A_&rwObHL~vM34CqU25Z>g2epO|('
    '-(#Arq2mnp4^1=4jHNL3ba0%a4+A<F`k8FXdKVejj7QCQ)SKo}s_KkOy=E>|B4(+j^;~lJRB8?D81Rj5gi2qb(Q%D^RFijDOME?V'
    'K_hl>ZgwJHM5j$`zeRbIWzwO4L}$!@y8in5kJrD2pC7U7f1yNOn6~TJFaGBGch|pX*Z<7WeUlOr{o=(hE2snL*&*up*U7u6%wt+6'
    'Tut>AW0FRfxzWKSwmW6_UK3^?p-Y=4;U(uCs&1&KN6E@4SS-QP4SAwTaKy37R%?s{9Glp=jfkxFfx!REL4bJKccALNctXl31p8u{'
    '09>jaOX%r<NwuA@)8e>%0CTZji4oZ1A$mOj^cD;QOCTA+iI350SM8p#N@YC|Xb{D2IwEpW%HYUjpi)VlA}U?S^#EhkEOM)jO%j1v'
    ')f=5^XSn|caDRsOZynm3SpQp#xXGO?x^u0iVN9-S8InxP<nSu7^qq;>q&1=DRCt^j;)bS6lMOydvBxKen#aX0WbHGkt8Sf^T)Vm}'
    'uU&P~r<Nf94_P>4ipxLYVqj9n-(UZRzK*$K^{gx&-syyBc=-_h>bep6!a3@a)A9BH0Z2htD_;B@<)UZl4JVX{uK&l2UtIq)hGM{v'
    '&geLk@}+Fh<(uoNTgqb$GS`i`4o!4jVH`c(i1C<&J|=kCP``q9s)q=a?4_A55iE>+SrgH%J;y&Ckc-=?t$rtQR+{QZhRy4Z>A}mY'
    '1>SQ?=dh7s^;M|O;naMLFn<yw%bE#i9O-+)k&=E+-_&K)e<_UWrLLsD6Z~?<D&GlKIl)^>8S#z2QdwWE0r3bcjXQ?PQ5?S$^d3Fh'
    '-pmV=nX1CEpimnrbQ5?o=Ee@T5BFtY%W*A{?;AFRizu$Q6cQiEmgP(3bRY5f$nEi95L;o5^`h#yZiG7>^z-pYt-JGv09={UpYA_8'
    '5XJAbKAKoM!4@cw;klA10_>+02@(DPm*id7$2(J9$Ma5{_IZ;X!9<Tt!5EMw0>@dAwSUSY5tpQrr0Y|S<Y`}=t7IY4MhS$Ds(3g#'
    'TGFsG-;#bj${vtsNHYOx(zHpbUyX%|W=#<;b^j%4lJFuUR!}MBky|@(a%}wd@$s>>)<hJmu3;9%hFhaJ0Z9pb359OU57S~qT-A}G'
    '@c|W#1Lg&7yqhaz8}>n?Br-g1h_OxXSo>Y8GOQ#)2|0c7oG9K_Uq{7Z2^3$&q+9R54|QN=s-{uO6Ex<kWgoJI;_dQOG!Sw@WiOxx'
    ')C`1#GBzX9j1QFZ0n=u4$xmpf0Z|M#n&*?ea`9R@Y<K9s4txEE?1mn;x?NZz`gy>+^!G5POS;m*3TSCB=%haFA-*Z|tNPSM&jyfj'
    'cAP7q?<1Lgv&NuJp!JRZ0DiW^!1IoP(rQe37$QVA&@1i>U}K9l_RzyyR}USZdpo=vZ=hyHd*1J(d-i=N+&FW>_ztuKpgs3E)Y%c&'
    'PvI4MX6*(6{nvM6bjaHcLjGwGx?cr;?0CtPyg}RT@cNjU$sF3ra9`;rgYN%ExEa~uV7%iUifdmu=KzECzDq==J2&>-@$QHek&mXZ'
    '4&qLHC@;0qn_aci4?~~|3>hr07qmliffu#<eZq;XAG_d{fP7`1>;dqfhe^z*!@leLoED*@!QO5R+<Yq~9;-7fenl)sL$DZWCWrV8'
    'tG^knHmZKbwza;q(>mNZ*xK4VY|2rJh{P3nJ|X>gCGkSW2YJyRf1U}1#h=ODcYILUkLf}9+Tt&eTVOKu)A1eeDt6nVghYhO)9mDB'
    'o?zU)K6RoqDLsl|>Q`@3AR*ZW9f{ANWFjF|e$c3pXoMspDkk@FwYjIkG+>ilgZAJImI7cYmpVfRT_q1eipF$`IX$fNMB)=;%k0BA'
    'Jns-{pk)BcV@MwBylU8talaR~Toz^9g%h-~i%i>*Y8y)D#k@$ALBC;k!r2K_Jm($e`XFtfi(o`DAO1VWcccyCUBvFAXocYx0BzxT'
    '8>LKg8CK=Y^*SN<n>qtTj|?7$T2!@S=%FYUv0-FM@<S+wh`>^A8==0*L-&Grh@2h(0SGa$ngUZcga&iEBV6#S@zJ@lYEXcX3M>W$'
    'C-oG!p`AqXqSyT}=ts7iYH1LS<&Jy72xfZ#;gva{jQEP3;)^-q;kh!z5IW&0#@BdKxo|?OUXS{Kz4e9p>XQl^jaHY>?yL@D`$PiW'
    'j@{VfqvZy?UOpMbF@~o~yEut4r@ISnUKP4H3i|n8?ut%;CvJeeeZDdj9tmRZocJ5JvMW*@WrjogQy7jI%Ib0h=DhlfA&qx}Q*m6x'
    'u`EXyr}_*%_&CS#y8Hd$`O4fpoFwin!vE$NUJkFHxt$J&arB+|jCEG#b{9Tki{8Q_`{BjHU9XNmcJ8vpJD>mPt2u^jdSy-kq#bxc'
    'SVt#)Kd#QPMz)C`c?<T(?5_RM&f=ndk1gEu>UZrQvIYC@4tB5rE!!X0@%xX&XZQ-Q?ixD@{7gR$nBi)fnR>>oXUzH~nYGX`fY3$!'
    'QTChARf$3Ziwh?&O=z=0DC={ZKHBJpE|jDMSYf81PnBv}h9p^Y(8en)uyEp;B5OC(!*MQJ!;)b-ym!KZz)=@<3F2XJi3eP~ScDb?'
    '@n*Jvz1jUM8c?Q<*$y__!Af^9qqCt&gC;M^q^eXnAsKL5K=pAX&r-Os^b@y0b?#mkuU4&OA1aBM{un)_p^06dslLmlzHZgR|0asf'
    '$C2rND%Ht$ua30lR-9APB0v*#bj(!M4wJdsMkf6jua*M85Uq*ddV3ZjdfN4+b56Swl>UN#jw_7e6P&gf>4x|{t~eU9zo5eR@mHqk'
    '!s5sC8W`d9dg6q5Iu?*jpEJNf)Np{ebt(W0peN6B`jL1Nkg+ncmo9L(N;e|eOC^oHbRm?dTB|=*@3h9(;9XPg>FJ<*(6G>%Ai~H8'
    '6FiKmdmi_dDgbIrwLlSZ<cAWxK|}5*n(sHYwV!*LX)mLE9*;=04^xXr_^UX!3b4p?S_scQJ&Wm=Ftb+FLKwsV6yhBJs*0c%EtCK#'
    'I^&*qz`LSL__6%y(eBQsd$Hv~Lw;-;eZ@Ex;<uWL&O$Z3;0O|35~cyN<C4Cd2}%noP0GqjG!?5XGMk}u-ti9_w};W_I4`rgr#{6u'
    'YzUE1I0ej^g1O_Bxcp%AB3afFH{+b&1<pB+6^aG!1nmK$wXJ?gG`HInkKhZp6Q6yr8K&HPWTf>k*fM6sD8a?=18>cr-ry~I2hCXO'
    '%dpf^H)x;(osq1{%i_d$8Zv=j6;Hn~PsxO;HjPvDQoMIGGWvxjW}}2A#n{u_e&l9Rykhk_hM3-9P?Rn{Wp5u*T6G+~7+DeK`8f!C'
    'ij}a)YH{Wj)67-KPfTUVFX6ZyxnJ@96XDZjS&#YCOhHU{!Po4zxKMWhE!mgIFOeV?&_J&Vtk$LA90Dnc8(Wv+dKh$Q2ci=zVaLK7'
    'GYb_c*Ks3xrQVV-nPy&%h9KLrWD*$rJk`Re2%<pI=s+RVFUV>oCjdU%!)4s%9oMlcR-dljNAeto(Z_licoV8uE9hzpMLDX)w3dil'
    'ER}CQsD=SB*-H0AV^LfNHEe=CEfuqf%Y0EO_VzFv$MoY}f(jTog06?|;5Ant;|+*}TosvtE59&MCFH%}f={SrAV`|wG*n3*7)mO6'
    '|9y7Lpz6wU_N2G~qr?~W@@c^V)`&MkyGJ=a>Sr9Gj&LR4qGnd#W%q+fh5oaK<X%`oAIoM)WCTzU^+(kbFHy>%r1lECErRUGYlqxZ'
    '>Y_5gR&;CBa9D8p%mCN2BUB!crZF}}<nT6kJ&S&!!!-Boh|JxeQkfbI*bcf~0H}BY@c)o~j6kk@P#L>%l=;b)aUPsomQQex7>T%P'
    'IhILG2xy+f=8x9tqBbTB?*UVDqZZxVPRNMw0P7_!C!oVE=?OF$ZRIW90(U{Zdm`Ig@^-0oDoPdngy?c;2?FHy_|cMD<|5gmLO&tG'
    'vplF|H6!U3Y9j5(kxWB6IGqG$+AQ#QB&`tHxmH2Cu{6_x>{B&TQ%h81>g049z(|ltX{G9c4_rJ_SHgW%h~fK)9I6;fAm~*GynrR0'
    'Ocg6_CXc-J@(5xZucnd(FA60ySz{(^7-WsgRI*0#(06lLqw@C48fLQ<Cx_Qt%FbsLM3Sf#=xr>-0q9`9^oDXqSTRLo5Zk6|D3wM)'
    '<~T(vANU=BtOy!;KqP95(#Aw)G!NMt%tf^e<dKfId|oU&D^YvNka%Xy8jX{-5|OExSEe+X)L2QWXg$nIPKEDMk}9)0PA6H_5?$WY'
    'nUFOTvL*^yCCVSUPojLX86dsgqTjeB;dVq1Hr-b1v_kG+;8gf@>4ZLh7KJGxWJ?ABZE+tnRCKZ}VAgtk6Aq{zCc(=CT#SU6{5Jf~'
    'ZqQ<TTqCdC?1n2<himAy3tyzeZi#A;w)s5=HNb~IIXv3hwY#ntqjV!QdbfO=0KAWI2iB$V)J$Mq&xu82kN38|XgxgG-+g#Q0gb-c'
    'KlqG(Bt6zJ71q)A-Y17o&5iXO*B6Z`9q^j!AdRMQ7ZXRxw+R`;NpE~bs`dD(SxuX0v~lfK3xLs<rhP|GBkd`#32!FK>V^5myH)eT'
    '#=+^S$E6Ctz&m{YJf<0_!K~@}_om+6QqB}$VO>0*l7=GERr)n1zm3fJKxnk%oY4M!e0vz%J^(F!JHl(Hv7MDRq+l~TRttdlK+&;*'
    '_~;rm0YBH)m}m??K1eUCm=@p)<ozQl4hpCUuN5WoSOz*!Xm2KkM4oMqSCzv6?+gDE=ouIcpv)%PTGXxGCzU4^;lUx@RL=R;%Fwsn'
    '&Pem;7#>4Ab;_7|dq`DB@I&K>SOG@$q!Rc~a7@_j=(ymr0=yDSR!71OM2bl(#+ER<4Yif{PRUvxuG`8`M<m~-m)XMPgM)LSZ==;^'
    'Xd1Z=?(brX)Zvqqdp|+QE_?*dEPOoDJyp;FBmz{`U0e_%)biYF(#LWGORXl3He+Md;btTE_r!H+IpYVvO5RC{gHRu~N<h+bC!{gH'
    'xU0+LuhT$Jr72vF?#L#AG(h~v=A<)IU+*A(zBorkFbsIeDLF_73ihRkk@|0TQe%Olw)%qPv@EVB*s2*!=rMpv5Fx?bvwaw3$sBZs'
    '$0V%-8mBz9B7YK95&i=6fi9$2KUy^=U>s(6s_~{b^zI<XVs2+;4ggx0>}xJNAjvszXK?#T$`~`GrPG37M7X~QrnXu#iUJhoWS@16'
    'gF9DV4Ju0f!P%<8!F&s3p&CRUIhVyBqK#3xR%j-uymf+#K|Cp`l87jI!DJ?r%w&?8O!AJ&B-wrORYer#ZaouHZZ4!C@~aC2$i3w6'
    'nF#aEh%lugXSHsN7XXmv>nE{4mjyw(11LtJze@O4%DNGy5+OzK5CfM`ls^tMc^EhsPK=8y$DuZx?3yKSSBEmKYGmnq5ixQFwet0B'
    'h$IYUC90z`ghXu72Q6(>V~}7-BH&t1ibN#HA=Qb4_mA;T#T*L*4<X|55SlJP>NE^40ZR<hsh*qTN#z*^g2Igr_h`|)P493wRWC&S'
    'lxHJr8cm!{lAy2E!@E3U2l1S*uAWrJ%nb$S^7$k~QqeP}9n^Ai_lUM_v5o5FTnte=qm?&ID?^RFF9V;=U_$^C?$u-GB$_jDWPESn'
    '$a5MN%Hx8F{N~?Kax02iAg`sn*Gmg)B&&@P)k;LL#d)KUwVKLi+67dm#O>tO;Tig^H(6R*-B3-+$`@%#vzS&L8Fy*~w>WC)`Jr)H'
    'i<G0FJeP-}?!}6C@2bYF7)k(ia#1lRKuN2bpO6_dmm5%Fb;jY}Ee>DmhOEuZY)>NrG%>-gfkdr7$*b0lRe<KQj1K}&rF4S0r3PAt'
    'F3Sx>u+<XGL@1a)%~<HmvCtW-Gb7YcT`8gIiI_J^s!6+{xdjn7%}rcJ0O3M`Y+6hz2VH_F6W3Q;*<?wV8#E0gEJ{ghC@v$JSXyww'
    'L(kFgOMgW{_?qnFdAuB*W#PHXWCLL^*oZSyIb^O~Kc`DcO?G#2o^%xDN{FHc0x(j4v6!kPU@AOw54@n2Ftt9PYw%94!86y7h4Lb0'
    'fw~@}2=2UQW4V!2QsfsRr{NuqbK`tB`1y?d-Yoe^{oai9UV-$+g{zb?-Nr_%l%W<s$tFvwvGf|?=FxtQiIm3lGfCw34aBcA2P!45'
    'oy4$Hp-jY+@e*)2XvaZl^#><FNlCnE5k<Gg<m)y_&}kSOna(7AAxot}^VgC%ym%dO(C48gD^<%Q3!A|{gYv6G*{E?<Ua;s7PX?_H'
    '_b>>%YErZLo$#)Rm4rmS0UJt;a^;ftDBWZ6iq3pZd;cM$Ruk`R2ghA(2yG~`6ZE*GQdKIX92FxQzHT{qQNW|Id6p<8ZH9$dE2f~('
    'FBt_|H2B5(XIriNk2XKqIub#E@39Z$RfVOA0fa@;<K$9)C|C)G1;$`3=^CS+3j^HuczhP5sS}sTZo8JojmDG{!;u!{`e?P}jz1l@'
    '$!3gEwQZ=4PN?W6Eq5-J+>hQlF~<Hf`c0d&0>G*;YiX%E#)CTYf=h8*L_s-|A5aVfQ8*cp$Yv)|(^`;;?AV<`o-Nr=VQ7h<rEUVF'
    '7p_QO(B*jB1fgC_;M^p*+u{K=ixxdovMj{M<S>UPyodXTM|4sIM5t8Je;T!mk!-_Q$B=juZwR;|<XHnFMOP?!qZSYv8yeSUF1cV*'
    'u&Os>%zP*^4RR+`%Yh4IgsU)a0`ycu4wO{y&EG+3C&eaKPmpXmM<r&oNW9^vTlx|OfLvO%e(w=^(?I2Fh&!3YD(l22FbJ8%0OAam'
    'B`Vo&^Z;SUt<b6Byr4lmGp|X8=K2;Uu2`H$xF)X_fw4(a!L*gtDzJhDac4=s{_sO$d9mvcxOoZ8Ctm69Ae<~@!VQ=fzEE_F=+eYM'
    'D$L-Uo-`ybUt(DqOkUxP45g0l7HOo0<eH?cAYU6nPfLe`$|vIy+o6UpHEM3nrkrSaNxMUO`{T1X?ze6a(}I{vFH=<RW5PS59rSvE'
    'FFw_#Tx@jzNywmt2&7G#rc80r4S*c!S>enpb^}u4K+rH_zs-Yg0x$(czBGn~xzQ&aQNqe`D#3-s5fXozXNrA`7H&YfH)78^X_b=6'
    'cq%DDHv@*vW3C?_Uk2fMrItew<60MKtu(#GOf32)#G-Fp9!i|JB<ZX$6CsuO9ex`k)ZFwUl$w&_0dx)L=3>>{>lUltaoOlQuvM#d'
    'f*#PTm;4@cxB~lRag!F;e-Z65ae4WkVipb4{$_IGYnBsdLfG3Ngyo57CUo6g=qm97%mus-xzl4OVQ|iy+1s7{!1E9=CmgrNd}69f'
    '4kIqH%}#Jy@T@0j1A4mA8Qv-v;6LU5HarOEVn@i%IR*(nvjcxi5QkL&ju>qbHiazBBa?>6tZdE*ad|JW?-{Jd>hs$wSa;Oef?eO|'
    'hsjld$w{fQX?wD%SjHx?d3dn@`S#}4!J$m#BD((E<(Em)7wOepP*uOQw)!SXZSeX(Dvo1QUYkjYZIXmC024CG=v9kJW%BU?1<Txc'
    'ba=GC3;e6nYPAPZ9Q0bPT&;ZCyzKg6LS4E~KEiVV{nP@kmqj*>X}l}R(5<r2r5ChTz*ce5GI1EwwVW!hV?Rm6LxCs7LoVo~v|w2k'
    '%&q`pf3KoP$b=)I437!FGO;l$S~&qk5r>(6PKu(L4)Mf^_@hvCa$o!|?FM%W5v3A-WJ=B3chh3${EA9_#;?jpjNIijS#U!>Odl*6'
    '@1BVv!w+*c!+In!ZZ4V{Ri*(d@yWUnkpR`gSQoZhMHROaR>DGCc1H&LQgDNp2+h_Yl<yHt@Djm>{Cf~`@gAlsfT7L3WR=v=J(o~7'
    '9gGk(5}cvHtGSN?E6`)|@ly~$FEFT*;{~UW(}GWzQk=nL+EHvrK@U#*JrUDJxnHX3Rt?d1is2tH;!_G=74Ru>?rd=Srh-0+xHyHN'
    'R3%|NX~VgoWz&;u7}r|@Z4Ai90}OgeV3tD6NJl>Bod}ju@9tKnJ99lu;fol_6Saj1=1Tktq*5m}DOShH-WB*;DWP!@$s^fyptpWA'
    '*@RN;PcXipkZIQq1q4l?%fpN^Q0Afb^znQa$EZo2lIX=6dCIN9$nrg{vC4@Hd)xDd_;cEi>-X$?!Y!{_emO95F7Rk8bV_CMd?W)A'
    '9&JS-U!1{3EGa3>45q?tRClDjUvhE98=5TPxf*9^GQnMK+qM*QBuxl(&;pK%(<PP1dHy}Vzz;w)u=imgT|yr1;v>SMQ==QY1zCz%'
    'OnQ(agtW+346E;h#CRpJgW#k>_2y;8k(vHtPS}%KgB;8yjOBSe(V3u(vOHv%Z^&<7wNkz0l7MECHg#0C1`X`Il0bv5hl(#Ye%U{#'
    '+o7T0YrtyociP>EY2|x#3Rcj2322q!=)k|=q1$!k?Omb}JQorlhW0uIJ}kKKnw{2LQF_Ly@7Bp6IYqy|wi9;n4sYJ~R)LKiflU5R'
    'GHXkw961b`e4}nTDiY9GZ|k(Z<o5Qc+@X4y@LyDO5(|Q90t{LJ>8^VU1lGBc^LpC7XlK`rBEYvXL&!IcXXVS#>1#exr;afvO^rF8'
    'd+KkCEcH(+U5`JnlR7{+PMO{C$YDxcjnxyz(5+Q=7WcddLAWvplc+0Bq|Zvdg9%ZUQcu8$dzd2`Z!2cn%3Lk-0p;s}k6vevb=-)8'
    '1+2)G9;wTlNtfuMM_ba$5UB{mIA(Sz3vkE@L5Q%aChmdBZZ%pRCg&^R9M~7mfk^+#Ik2DhIWo*Sf^7-rEozXDpP1z8I9K)Q!A&%('
    '!&<PI34k6F(dQhrbHEoZ-yHIiv#hCuS5xp2!$Qc2m09>Bj}bMig1gDRTypS{INIx96z5Ae`D}}VCzg8gD`3#__KM5fBi~OsH+oow'
    'Kf-kreuNxFBTRWkt{Ln<{?Gp+o%rEn!Z>9piwgUolEDSpk!)Q|TSp=R%U!vovR;Bgr5^Z}TmulC^o2&y&XekR+4VuVz@^S$0$ylK'
    'mcA|;k#~QS*H0=VGso7)T8cHM`{DT!6#PS*jJ#D#F|G{1$`E42DBAy7-~oM>&7e_wmu9H#qy{b@^-%K_Kfg0gmaqlsuKEE>hmkg~'
    'Hh@xAQSKD1Z&5d3CnzlH+(ZhG2|q~@CoO(+7NJ_rt^;kPGJ8x*$*)m*77`aO(P$7g8x6!m(~7I(abe9HtK}<Iobji^Z+M)e@QwI1'
    '%G-K3nlKKsVd1tH9JT^14yEikc;G(g9c!VQ-dQoO2K7N&KM)8IE^`c^zA~I2q0{!taKXNZQ6G38UfBy{2nriALzk2c()5ypumJJv'
    'Mo8en8S$*|LK`E2D`!rGhZ2&)v{TG6`}cp<C2CRUGv1F!%(^YALbVpThF6bOXoIm^W)9Lgs#3HU3($v;mq7^67~BZ+KX^PwpZspO'
    'NEyhf)eMqVILF^+P9>(a$1lyRgc=?L{+q8+<UyHA%!LI)DU*n18rG&<`z7cERN7~}eSQ)=2k7B1gg`oP(^L|TRWcu0k!F;K2$fD&'
    'a#Si@P2>W85c8?X-zbDnOdn}le~NI0A%<x?v*E<qv#Q!fKs;B2Y#;++Y1bK~VSc2YBCu$hIMO(n@<C{Q;^B3)nmx?sGg2BZP{>2y'
    '%id9Xb*sqc)`Rs&J4dapy-&9HwpzRUn_D|I-BuC}`jkmnh>%AqGoG1IzMp24v>^=Uza{jX(AtiAnp*Eav%}2nFf%*MOW0v_Y7@u('
    'v38k+POD{Up{LNdC5?>C>6MEHAZ_FQ&f0-Gu#LMuxi<=ltCMemMv=Th!9ZZU6iZaXJgf2KN#n!Y4NR9;O)DybFcvct_c`Z%Oe?`V'
    'Vm<`{zc^+y_}`$7t8xPym&y90+q??eD2=03Dh7_Aagc)A$H-BPiC1o9V@n-Xo4`G@mbRS5KvRQJCdi^)u4LF*L!AjKQyT6}BA+tb'
    '<+GrecmA0XZ)U`MdyRNEGO?+<`!gfk>ol?<tEr!cZdt&}x5-LYqJmA&_%l1%8?%#53;XYarL6LLEM>3N=v8_9jb3lS+*LrIZ`ADd'
    '-7!H;OMP$52sIpIhBBW1akbxob!u3u<g{{<X7z?k^j$D!71sMzjas8OZ`H~kg1>#U*6T576;|RKGHex~`F*x*<@G5B6%gt`WS>xI'
    'vsj?XX7;gf$v!sa#iM<3q@`6ub;HfC9_{j8a8qmBuItl5dNC>P4cf51)W_CB{OUm;N5MJwBQ(jKz?*mw^ZTI#bP#{;gpstqJs>_o'
    'p||K+pC`Qi=8bZFJkcw&+|4a=8$tg{WK*f7);WN9s9wI5rLID-LCzfVNMz~B1L}R~+z(o(j_a=_*0&{6eRW#>cANzC$}7nXaTgBT'
    'z+3N&1U;yDIYE_`IGT`&kKUy566j0Pys*Tf-4D27Ua67IpoSi*O}0?O{a;2NT=;0-cu+BMoCu)dbR>5###I)XMzS$(VaS1hY7k-4'
    'gBOh+MZy30*?%XQoj&Q}O=DqxxglCA<ph+Kg_IO-?=-8VIle6ig-R#UFNmHX{WRFZ{IQn3MP$!4?NJz}AOyNOa60ZFN=t<FT<@Y0'
    'lu7})orV~tGc6-iRSP{*9T-+XF+8<avFt+sIg0|%?J&KT_)bM9I=+>qQ%R<GDOMc7LHCPkn3iRw5UCPG<R#<k=r4|I2}mmN<}V6h'
    'FhC&(gbWOvb{mt#SA>*a(1hlfw%nEB+heW!506?q+q>IGhch-iW3yQ{tILbnlk{Sn@zxn{efxN8Nyvtqx(ea^BH=7VKQqob2e2Mt'
    'XIaI65`R}$EsXaJXU?!Cs+W2HOmtG2?66cpxK)65DQlQuG8H+1^i8V|9IKxs7n8-%<Vn@bTz~N7M&0hgk4(36rdj77=Trdd2!3Q{'
    'L!-gZ_LqU{Td>M`ORLdKB!PJmo{2NgO(&|xS289wSurt6E|2Bhj!fy!BhU5Yx;*aH;ej*SUh8K;a2_@I^D}1vd*%hNcX&TCf)(|0'
    '(rZDbyi7+5$L-Q7m3(N54`d;f@64_UJwSAFL68E5@})8D@)nL#?i~@xDUbE%r`2!IpCW5{7qPW+WGMSym1rbvz)CftOzkKwEa&#('
    'RqHrs?M28&joU+s1!$?I&|Kq8wc~=I%(%~6%6(>}`Mo2}(#(#d*X^=0)+Hk+Dx(L+>J$pn@i(IZOi9kN&X|k3H@_GBky2<UXN^p!'
    'GWA`ezZa_`Ubg7aKvoiS<#fcE>d9-Zfiby0GF`Sq`1@=?!TqvXB9zA4lq-TXM&^bnK}3m8y+7UEKGnXMG|dTF+(>lT4WT;5Eo%)#'
    'a@E9`gQb(NbRIEO7-`m={*8>V6EJLgB$6jRp}sG3Oc72)G$o{}hr}F9{f5Sy2+ExhO8BzrDkeWwPC$74=$j}?AL-b9m){8vGRg7l'
    'Wq63@_B3M<?>d7hAkd6Ol(L8kX{3iJ?3!~`r&uVu7U54Z|GTiO<}+5mnj?-nJGgkhjdJd6)>P{|)xMEg-lRWMHmAvCm}}%ymBwjG'
    'Btdpn$Kgg3(If>7IksI0$2M$_yxJ~ClYKgd$IwXqHk3Vvp<hh$D$IIb=#@+F6id!1&I6Axo~q=-X4e9#VHu)pxH@h^r6$XH5RS-x'
    'e%~8}Du0=9G|WY>mZuWB-;ob&ojaCR*+t-X=+pq+ryryaH)5m2-HFh(JWco*ug|hi#>ONsAQ*YUX^TJadyepHcrBEmp?uPbMEQYd'
    '!0sBHg*qJo-wy8<G|Tr?_Oda9CM<2&m@5#~a|NEdqXK~yi0eM3JS|ff58H^iF8SULyw#h5c?_5)Fzo5vriRB|GEUXC!(qZE#HSnh'
    'O&eRAB4|lsfL@#@A5C3g5iPdF4V5z56m*dkEl}i76NAkdH{7fT?cAIKgC9IlfRJ9ZL(!9DZQY{JZddo&?FygWE~Phr8DH#TzTzp?'
    '6}33VRmBez*HmMpg@z_^Q|iF%5s2F4f}>fURc7w{kuoakdv0t!snniSssiTEsqAy<u2cnC!i#xm-4`aosvUW5n`1!YkE<fv2Dt~5'
    'QtL_Or%&Xqx}3U8e97`!{3@J_^E}qPTxBxJodlhPPtzEOP8t<?V<Fy3b6x7zNq?pnRE)2yOXH4Y@1C4BrT9IQv|gvACAmV+dA>tS'
    'wlYi|CXzvuOf{MbVsDKgRwR{~C^i{TujdZiH!O{1x9yp<_0~&U-vK!*$3L<4a>k0Ce*fgHDV@$mUgQnnF6Hj#l~J`M8`@*H^PFtF'
    '+nwhb6R)1Pjy7TFOKlW&wopyY#K4jrj66WiY{`dl#_#S46@7408mXpxf*ImvDf~G_lp3S63(RVonV?rn?$gr}2LiMxtD=vSoI3<X'
    'Q{zufAx$vsiOd;)t2};+(Hw~$2CD|0EE)$WEB0m}I7CEGBas+>b$Ixb!=tU;*53N=*5PCE?Wx?H3z^yT8`wGU!#MEgijH}Ul!88~'
    'X$;>IP7%Bx%{k=B8S2@@D&loz`n&j;udMCyX^px@pse2DDveaSPp_qa`DGg3l0Y(@v`(DPDQ30m(nUY}l>2sc?t0#Rd=FdRFci<N'
    '3)mlFn@i4KlUs!bEj`czxg^fdS9O0-)>iF}vk~RVW0ftKOacg{oD~4)BWsUL_k~=*qB>m~%GQ&97O+Ma`VB=OR&g&`yGoSAKthgz'
    '1(0~5vyC%;5e7brs4Q~70_<P-SRlN*WmJCZUCj-hQO_T;g;669jAR?R@#K8|JkC#Ub;ZPs#?AJ_%xn*kx=W^8e%)-GC;n^$`VMYD'
    'CD!cO7IeccXuMazY!jMoLbFZiO>IIGoCKEBJ4%#zcLk7Ccq_DGnv=W}P5v{<%_W!v7IdRl*SQEnI2abD75ES2C(NCFD^s}q(mV{v'
    'd^J1j%@upVzzIkb7KQ*?egGu&&>KXH3TF4@MRvJHaiGelSEO$~h;)r}cd?Vz6#J!hOKhQ48M#I6(JMpozU->_@&WILJUZLB%uHh>'
    'u{h+XGC$^oNsQwGVgzMmui^?!uwHdfM!L%S-u!$ar~(eS%XtUy-#kn|nRPJ_PE4AZ&-m45aOoE!5n&hs<Q`8dTYk(#G*qF}??D0{'
    '#JcW@xP2j4L<>IzouSfBMjSFQI^(b#69NaAu=FKIHBxMgV);FgqZv)X0dU9TG3+N1aK%9n$Ca=Y1f@c&yV^Z7*pOh;cD!{=&C_J{'
    'MIlizIR>|f0b3{^gle&ja0Xuf0$x$^{iHI_=3)QpKgVli86EhdunC2#%N}ZYq=wC)=UyE?&nT+PVl#y{3~A6K4QJjkwp`pigw`@y'
    'fwbz83`8e(iOIgsSzY^rnw&lunwyi%jfP^-;<wM-K4wjZWzyQeJOgfeh^l*psvm@~>q!m1qlQ^c;$)P^t_tk|I_J00EE!D&6e^Dn'
    'gi!*H{^XTc0ML3PTi^1Suul?~jeDKhY&4{M1ti;Ra#eqvQG~7orq&Q>Kv_b#jLvKFzg%ueVfQ5?&CmAX**<)ueR#G5&vxM14m{g|'
    '-~Am}+|TbIi+W>Q@s##OwObuJ7koG9INq43R$2`1Br3EF_Z-V+B8s(5A&qMo2CW^sgoxs*VU2k(=K(AZeiUIKg$62WGWnw>jlY^H'
    'x>9=yLo^wVRp{+xc)8fyfsga<tl1VlY<NM$t$a-GxqM9Sv3Ed|8=sRdFU?JJd1;x}L;zIn9XN$V$WWtR8Ok3c3_QVEHvsI1U2?fJ'
    '0$Z|?sEV2t({}teg%uea#my8_E(s(@LzW9gFAxF72bM!JO2w2>I-FccIrwG{Nis!%$T+Ig$cWRVXhH8Dpa5bDg_=~F==4eqT$fuG'
    '7UxU6Gq9*JkzRSomFeb(WS5&Bz8W_>sxoPE8aZdCcz3>JikoSLH!@LV5&3n5S7VnEtGsU4<q1<Mz0EZ@-87MKa?`|DxoJ*uq7hP}'
    '2lAP&%{`@K0{pjlN`S3DJojMBPGvfzOHo!IPtr1)otoxPd}8cI02m$z9e|BmFPeMFdNK0c!5a_}jBP%RJq&e9(pSQl;_{`j@B%+R'
    'gn@!6b!Uvv(Q<>B^6Hcc*JiusY}cIankCMQ@5+ApJ=iH{d*pXzk9^B_$8jf95#_QSMJ1lD{|Qg)mr#lgVi$Hfmq%k_JT^XH`zMjx'
    'aUGu`71>M#?PQ*NfxZl4a#16ux7h6x^Mm*dSLlp~9BB6n9e<buHDX*MagwjG=*;N=js_t+#c+IZl(yLijZEi=o@xXCK?oZQqdSgu'
    '<=TQF{&G<)=CCx=^chQ;=zhBL0QQ;-CnA?7QZ4A;5JBp4mw^(vaP_X!b3M#jwd?p{(8ruuLUgDPT=?nuQ9Z)M=(2c33oRN=UJ#~1'
    'gBZjuorZl6-tZW}L-#BIc1<Q!MN6y>>w50SvWZ?GVB2Jlj}ahTSdvbDS3g^*v9m?^{~Zj!S<)`GcPU5k(LBIO16fvoa<;&R<K}d>'
    'P@K^siXmr<6DlqiE8d}scP3Q4W3HIN1Y7ucjBO|lZi(I6@$*GCEX9XH;X7jr_XaWVh=RyQ)G!hx`Y~{e&;ePT?ZRikrGZ<=f^^ZQ'
    '#*&};#m!S^;BzKo+(HNKLBuGDSQp5OUvQ9_=_T@D#ywKj=84P}5qnWqj6<N}x{SKHVE^!59uu0ENYkhcJ&_S=X~RP|K#wA{E5?d('
    'd`S&m!zgJd#FL&@n>3jEg&VmzpdkweF|J~hEgFM~QgIZJMX`F&?E;gf()p3)!LrF=?*rKxz>;{EA$!LgZXxdlz`S5Cz`oicM|S2Q'
    't8!06su2e)KI1Gv<BQ-D&HOH6liPGn{sn2r$9QPs3CI+FqB9%((N0@7!)zERymw*Kf??F7b3}kBkZUCdgG%J92oMWlZQzQc6M$YB'
    'W0MmGz^Q1hV`H_dVlpbKYD>mQeeM+k1?h91Y8a;K03@tCrsrO#SXDo}PV6~Du;W1i<pBA;=|DmQo4jdAvxzFBV)JGmk&o#+nrcpr'
    'M!bb0iX>^jLq5_3!UObh<8csbHZ^PCG_0z;B_+pA(Taqep_u$4;vypm2VsO|KwhW=rw%UVR;Gutmi#2Q@F5rM+z0Mg+)VG4!2V8Q'
    'j)HAv8khIsra|k;C@`K!2_701=o=;KA&Snhd{?;AG(k)=u*4j+|J7ZgxxnDWm_YJN4FB4_BD~><9O?tb(#xXXRQNU#`xE%iXPUoT'
    '%?TFwP_P)Y|H__?yZJQCD@CT)v0Mrv`++Oq7l$C#xrh)=tpnLaXAsggTiDa_Zl3fE0f7t#<sjSXRBIV(n7&?4;w+=}|Ha;$cE@pC'
    'iGqJ6iBX@bvZ@LT7f}TQY%ZWon<Ur(XxRrqgNdpvAc?BVQf3wwmFgTxZZCc8v7h~V&hzPMw_kV9^vsuchL%K$)<T`rzX13P{v~sl'
    'h{(vy$gBbvZOnGtL}f-qM%=h@_qZ1jrLhaF%x}OEDyu_UIVEY#3_p44R0V`(8wgPiy~HSEACbUQ=n#btQRomaoer_eAQ2=JbOa!T'
    'BqXF+w$w4cMxneAinAHz^ALx>A%gG=5`hchw-A0`dg0f27pe{-t+Q?Wbr_>#_c8sgd{hHz6)6c~XRYP>TsE<Rz#epasTu3NFsX{A'
    'YR55N3WBD|p$%)-ZM7U2iZ&~H>~uPAKX5^UrT|06KqLkzxXw>1txP1O#MjWX_vrxYXEf(<rq1Amv_0d9ot@-(rjHI`a^FU4TKufU'
    'UQ7aw^!ZL5o9qoqVe~|_f#zUy*l)*ahY7})u|Iq?PI(qiNz<p)*Xk(7sbA|9tPOxcxGt3X_Ks89eC|_8D<5$oH=3Ndt~|LAp9X2q'
    'If$&4Vs4pOm98LF3%qvt^s6$=X6*jPKb$R#h!R)Et%dJII}1NfyRlC*hbf~aq9DQr5iW>uHy0ani11fLeM<%P{jN}7vnaex_hf3J'
    'y^R~%_oRBz#vBv#bTWu^`V2t~z7RKS;Lo>fWWoW!&PQa6)z?X^0`RkGcbetIvsW#rw_gtIwo^m>xW>L5{%qBn=^tYDn3Rsl-ED%}'
    '{KPh!T8PCg$JlL>YKjIjop5Kdt9*5qtX6{b*n`lE)A4iX@U;<`vz3%8oO2$#PH3l>f_Gl*W~ex?&VG0wM^@A*jw=a1l{IqLc6(G;'
    'H$%ftqrmKi32`9lgjRWh_1WQ51H(kso;t{Yvl?#~us+}EJ9b#c&8W5APKU~XV=kk!Gw|W6HQV+LU#CnrL-SUhH#e`dva2Z1#MY&x'
    '02JCgJ21qe^*s!z?qMZn!a&~*oXNFxJlVU+!T)y8Iikuh0gpE1vc*HoL)SrgM09{CH|BX2L>%Gylf<#+YoA$use%p_bf}<16Vf3}'
    'euh$NRiX)etEMy^VDtrvdOjq|C^BiElR4UI{XvI5e17I{^zWhvca#E!h?G{vuxBse*;2M*`jybe&Z9~q6|l%FCM3sexC2oi9LFeA'
    'YhcGoSoMnm*{R{YxxF@4AamwZcKYp(*WAkiIgNxDS*Q@F0<!N>+Q73HW?Ifp#Q+AxDEN+v*wZ146ZZ2tQNMUgpj(-rNO8`jfs-DJ'
    'E?uHgdxuBy`~?;Z;6$PpZXYVD`TETMu5NW;x@!E?g&dndAlbexJy3@=j-625=@*e*(^TsR?8VjQdoecOM5mT-9}se;c7-_9SPp!C'
    'c3%J1YZvuzO%92CPpLJd$hYo3eOCDC=c9vQJB5QI`+RhG0|ZSn(V-v5=+H%^Lpte79UZzf7G&;GlD+u4Nho?82~9Jpvy&x47#(n?'
    '*=4brvz635^7gv3^Yk7#Jct4l&mzXpKRw%dHq@HUfDsl$&gH3`3qh0rEYZ>1%k38oK>rVdY{AhM4Cr}mQMXl@a6_KjusLaX#aLOJ'
    'W0`7_ZY7s#1XKOM_VfJb_!?kX+uq4F$*5-9W{M98G{_iVB0>J}DO8Cs1!T(*S*>pL%;kJ2`=&UdCB~`mbdLJFar@udi+I8^ZBb;F'
    '%MDB{q^d%yN?gfEE+LucSS~2>Tt+OCjFEV!i6(;jyLQLh5t>t#l|YnMteTZz%9ZqYB1sPie0`?1zbkbzF|P2ur1~Z#q2$6d<f2q^'
    '>@n8wMEmhfEZHGPTFSb~2)}skjRt<N<$L`+SB1c`q!cQlXQRRz!#NU7fHV8yY3aEbl&`bHuqmvip&c~ah=Gmb)Pz!Y61|+saBOmU'
    'T%teyM_6p4SY1u}VTYEEt^6cCS^Acmrx4o5`&bIGz7Xrb4zWJMT$)_!fbAa`PgtP_6ly@B27F`G0JC4Z<?g#2)UB8nN$?rqNd&YD'
    '7RcN%;jBo90B|mi;RJ4rbTq-ZkntQ`o6`@2Q6Ug{7_CKlZvtb~lYudl&q<HTz%p_*y1o^8SW=&BG~_)a@u~(-_Z*{pMzmP>sB(-x'
    '<1rvOZFJ1vb{&wata9IX+KwO8e5W;NI;~pQ6EvNEW6-efb*KuW3I8gQN@E0(lWEuOL!0do!!%?G2<&Wc!~X^cZrI#ae>56)8}^{8'
    '`>pgCYc;A=Y4Ph`Soa6`SERBUCX($bElx&pGK!OtbqVE~%Hm3wyE<NPr;1llk^lGm9oNBfM5OOoUC{q1GXttpD9wj(pnRNWb1z8e'
    'Xu$MK3@+FT@t5Z6<p-+Rt@zz>w|&^E8X$x>2!;C-UA4jv#Aj;8bQPkiKrSHc?BEB)Wg!%UV`CV@7V+v0Al&|r7)<?8;R5o3wxI(0'
    'YA<C-L9pw)y*<-xVQR7wU$f=tOhYS?Y-%DHa58*29fxTB%eu#V0A#JU?K}2fbc;1H5H#7NzJ0fuIHSTVpX-1>ryTDy%CkO+#+3Z5'
    'T6?Cs%p{j3@2n{VJLM`w7(tjBML;8SFAOHo!U&8(3o*G}*kh6#-t>G&Bw^sd0BdND<4v-i_^Fw6rO__&WaTh2KwN}JBzDuVz6+DB'
    'PmV8&FvC1kBN>#wc(0m>SWke(h{xSlJlq9P3-867+J!b>rA>0t46>n4*P*oGq=$67JK1zciXz6&@pzpCV0{Nj%&B6V;G6KDnPhOk'
    '>F`VfRj0e{v|3K99_%`FF<g&(n#pXgbGF>oM;)?a+&IO2BoX0Op&fFpYO1E55#?l*EG}fq4Vr1?wbx(oA68Np`Si&gdldPICDXT?'
    'gSqsbmP=q{8+WSo5y>K3)gDAPRFjT-&NNt>W#m)WIRlSK4I1ove%Oo?G$GaGSkn!=L;h^T?u-R$CKpXZGbdIo4Y5fx8H(Io)3QKK'
    'kegVat5gnpNPVpZ%MOluO{)wNF?1JoK4Lk9F|Tg<J|z+MsX}-#{R)<~XpN?2{hRxkQ<$<i0s+MYx|G`&3-Td7Qdxm7%XGkHE)n6v'
    'AXKUyN2^$uFH==bGKM@=Hs8_Y#WfR2K&h6dN<T^bX7&QsN-!nG+?~bjpX~_PqLc<apP<;LRz})TW`jRHm+@&BEx)8(ltGgy`bKFE'
    'X!_has!xK6G(}?0w^H?OWFB9~_M5vSb8SZX(v;Bi?@Vb}%`4!G^ph_E+0yL!<Pv11(R95Vk*3-_PcB!Qm@Fa|zqr}5-m$1~&1mtG'
    'xa7|toSM?IFWVhVz0B_yhs)a!Ff#x!N8fdVvR?F5WW`?J1L0|t%c6);sW8f(TF%~Rakw9iiIq+mPKy)Nri{vkoFM^#GRF!HFyP#='
    '^jwyUp=zPnXo)P2DtC2+(qxJpS-YU}8(w_h#qystZh4|ov6@0BRAhiAPl@2;6KKj=m3U+&T!I-<o{R&<0kwFTv+C!Vi{GmJzl;Uf'
    'P^ZIkwzAGFesMaxHtJbeO}iUjr>aPGAjasl*s{ZlDkzg(yUH}BNJWbko;m!!5Qr{btZLrDjS^qG6vbU)<<6pf>vI=oDx-1p=$luU'
    'UHt|`fGw;?>pBNiPv%rmC(^fgih^y~Y3~c3_O<e~SY7Jp!qvXj{H)+)1t)tNP8K^x1uuJ9c-bVX-5XqW(erauJGa{hO&FOARyM&1'
    'no_+!9fX*qE~xth=vs<#lc)z8jO?!X2=E^)98+aBSylW=9~C%f&Txakxzg|J?a3$$dx*2o=(LKK_*LQXSe4dt#^UQ<NdAU33YXEw'
    '9k_Wzt`Kj(MhT|Ti`Tz;#N)-MrYh7$?ej)W)v?PM&0OzpJ~PAMRCv^PEd2T^#-oB9GqgA<K*K6^JR400C7|k98VCQOGJd6bG$Ob*'
    'e6S(bdwp$reRJNT*O$o{h*=6pSs#weQUwxaBT<1h;{r^iB;M@ySDg^%0)ObddJcFsJOXyxg5_!yy^@nJ_Zem0i&-*nzyW(1x+D!1'
    '$z&a;wS5E)oSv*Sq&}mpd2{EoCEVRvs-Y6~m*q$EC2d)>MipZ5oi<j)8I3C}2iz=H59rp-+c(!%k;&aeS^KtqXsmJEA6MIW#Xd-j'
    '#%a-2R9nifik&IBSlPUK4Ffhwg(2}}5f_;#fs0SLgq3`8$x1HW<#IVRP0w3J^Rd++Sy{<A$>CuomJx(vxlM0?u93Kmlp~>J7u@x|'
    '4vCq-tfq2Qg3S8BLT0~teU$}LR6<c$7j9Cn#|t7LQjLWveyUgW8Qv$4_A5dy3F>aI*%`Dz8z6NSz~rHHCg62n>^<yU5McEpQ?FD_'
    '@zC4Z={WRCim5=GNlInubf{|{>uzf^s#R1OjVW<Hc42^B%RSRd(v{D7Zb5myUav=h-K<0<tvemjW_$_ulqTUFOi>kjXUB@|u`I!-'
    'RI2DfbRuDPx1z^ffq7xLu1ppiC4Yc5scB^VxpEJMYR#yzQ9?OeYq4|(TWn@)y7~B=Rr6|R*TaaAbUkrc!j;xO*Os^Wk92W)@nU2w'
    '{C!@l8KuRFi$1i+;%?9EMY`KV`#pe>+iuTkacL>Jm92fOsn;62k#b5I<>t+Wvx#)g&Q&E(s<OlOCi`nQO7fBfD?YiZ#{^Z%c4~ME'
    'A{Ju@du#9@s!k?s7Q~Ub?Kpk{C>GE_TiD#p8<wF>d1%35!PZzOQZ#Q^X)^`LiOY<(>l-E2a-+0qjqrRWOcC*g1kb@5F@YXCu5vhs'
    'pedrCI>_RE421HT2EY9*_;K5YwT~c)4!IFDA{<TvhCV6IHUp@v4!(H{cmROE=mp=*tEG1uIB7-Vvw@{Iia|_!vDNij&SbDl_L>Ze'
    '*zy@*nEdEdK{G*5(2~OeV_r`{L@?Jaq;_^V89d^BBs5|>Ae!6|qfSdP$n<s+V-UX_J&hQ2ih8DJU@P1f7BKY(J-h{=*Df7wcij-J'
    'JNznLQt?e-Gjo!iyvFquqsD0BbEtqK$zD8KR5mfshQ?jc>?mP1?0cOKj*EOFtLvQV+J*-heSFvJC=!zmOC)Qg%`E2WQN+I98aM%='
    'C{N@xN|3}9H3U^k1>U@ScG3I_^qRBgy^rR>$L%e^QKsaG6fCEX#`C)2{kL9$hWBBU-!haJRj<eKHxM2U96wlhH_>N9BB4n?;%0Zp'
    'X-QXjw6YkLS7=wQ2TVpDkTUE7h9&qS$SxI~P-IBE<4%VXK1j$|bvkV&V^GW;`ybRX;aQGSTX@aug>G*Us}w5HY%~_nC@?;uo|({1'
    '!!dUsEyf;JwV8T4#R((y+#sCF@)dsTEfg^y!MDgpQCKGm>qKFlD6A8Ob)v9NJezf*uuBwniNY>X*d+?P#7kzE$Wwj3BbJH6Ch?Nk'
    'BqoXZ`aX2>{G;rMFJ;WY5*LBBV72Vfh7G)Jhr4yWH8or1znhNRDdS5}DMPyh>f+o?rD9<%pXX`E7!zH*E7$W)zb`X4KE7D4g=2_g'
    'XYU(#cjjynas2E+oJj&PQhVcIl$c>siz8S{?KrjdM$o0kY*-lpP4xB$Q;RG2vfetqsl}x`(c65mo$@3R)S^gzHhcgLauj>R=(jBB'
    '@jDabZor$#56p9)bm(PG8Q+*Dyyi_l-IPp0mPeGqrljb=b87B7%{>aLroT|&Y}@-85VQBA8HnZ;VOx-s_j;WpXs6_q)5YowzLN~q'
    'Cyp~wyuO@9B3eK8m}B*up}jC1Cu<~3Ilx`(J6?ICv?HUaiAZT5fKelX;#3y`Fl$M46F^%r5wD&6>j1jhb7$<mHUs-Zllv9EoWD`R'
    'YA$Fp6A5lMN}_ZdJrh}cHcBFo4?g5t&|15g1XhkzHm7&9RmKTcMw9D^2pKjb#<}%HWg;JU|6s>>|A3X2oq80j&(AY;HfSpizqBa<'
    'GZXE81Z@CtJrv6W+<tkzV4PZ<T*bEC+HvTMl2ij(xYzGH{xv&r%JD^{I$GWy^`-kIWW87TNl&E0wo~7=gDrWL#i+OOc$gP&YVogs'
    '_?gtxGBsjpzs@vZ4_U@s1OjQcENa^<GO=8fiC8vDoH>HchZ%<#O|X&nj9;@ZEm*TAguIK4lUmfQSw6^u7a~qfpa{?D0!g2k^pO9V'
    '77JAyHSuH@7g!9>pYW@R3HR_?h^ESrWn!G~^1CeVf5le`zfGckA>==kkY9-RrxWkLWrBSn(ibBAH(jJRT<|S~`a-BLg!-3DsL#DR'
    'Nx@Yp-J_!qLwjNum*Mz`ge8?tAZY8GlS}m1IbU0fK#O2FT%Z@AbDRGdnfby_oGJ7chI2sN7lyMJW(1KnsScAlPT1nna(aR0<a-*b'
    'V*S@A*7)PvH{=4Sa&p5}&TR;U)psbXn@C8oLs<fdYv<(%IJN&c=w@=dA@MrIH{Zc}rRAZe=FqUT2~{mY5E}xAglHYGTpd)<<<9`Y'
    'e)8|C3_ZYy;!jF-Bk-V%X=vbpuTZGcwdR2q-ZZTtz3&VHXKZ*<rk@ZXz-jhPfmlFv+OFR%hd#^DYrY-q&Sgxbg}CV?&tDGFAI8B2'
    'nuq||CGG0B<R%Pb`cvMZUKsAfukAqqE%1LyBqEX_6Y`NHM}Ohd6-Njy7znHW#y9frHwDnG^*hY9G6lD>hJu%vmZX9O3OZ8Ik%Eql'
    'r6ZFBCfwq5wUeZxfxWyY0){B}#!|cOG&v0ir>l@jFyPcR!>rsHH^|<0w=)2s-gSCSw^Oym-pT%*K@+Qi<qoracWvv<<&_`axV8M|'
    'YL(P(G4%DdW$}BtAHFHF)J9L-uKPCS%ZGM)+79*q!LIE)EdmnNiONZ9a{9a~fQVHK6n&LTg%hiMMHyA}<^Kp&vy8MQ$!5tRGqTL&'
    ';Kz#7{u=RwuTxYDocTI&#-u2zY>(?AL41`AV*K|e$T|{bE~#x=-&`!OZ&K+Gt)td2){Wu2SS|rxmZDAvZR+r5JJwj+dQ7fUf^MZs'
    '94czQZ_xmMr}wAU;(hBaesSH|_68X1Uw$k4dY?F~&^luy%vO>aB1IPv78o`w@JDRY@L+utri+;=7t10)rRYT-qbeIY;jh@IX5x3?'
    'qLpC{ma4QWCE*i02<DGAnJ-s09vvH{g!VVeUc_5hN{nNMH`V~4AyGQWg8DjNjH~i}5BxLMk}`j0e4uT+9cWv2@Y2R!&pYUe`$IXY'
    'Ju#3|Nf?xCNhSL<eghLY3EbvsNorYUp$3llrJ*I#{%Z(tjQ|rVzp2MN;P}(xyp$^SaM$UT%PnP1<`?A_+c_(hI;AQVpBRpScH{9e'
    'q8U!mIJ02_Rh07*TK9k?+*`S|${sb_x4Re<-Y1E2m5v`7Rw^Vvx^1i6daGiQ@LDdtRjR^K5zi0W>bcA<53k{A5}Fn@X9$p7RRT$>'
    'q&lm#kkGp{i`d~{#@A#YOe?Q-VqC1s=jl$E2bRf5st^B>0;*EFVjD{b77JFwiEIGocei11*x~z$9j4}&Um5mC_v4#9lypGt@w__X'
    '@Q4OR`CRS1Bf24ummO|R{fUl_QZ;QyRY{{-Z{Y^W1!C*zY0C*ZZZE6}>sk$K4_L&4YrCGe7fd^cyEfVv_nlhH=?96ym0TcE%i8zc'
    'mVP!!xqvBXk2X_tOb;Wic(bB=YVMOyM4!Q?p{6k1Ipz}BZ~(+ntha&lm&<J$tc{t25zQjhFpPnu7Vl+6S&rS7%+?mmbS$WGnKK?E'
    'Iwfdv2Kr3Dg4Z1HS5hg96)JF2V#C~0*_Q!h#$;bkf1I+SQu1XtGKV*;Gw@t9k0W7-!+x^4D#8k6|Asi(a>B8x3KEZRdD0+1MG{3e'
    'am9&K@fndV8hH=%8^vHGQxPL4&{)yqG9tvdl^G~9pcsBXxhy10X9NaT1eK9Yum`OV02RFhk*>5H%9<o~Uf3PtrJ{QsKOiXZnI2wo'
    '=@H__UaL=x-+BQ%*nByHL;)NL2wr@<^)r7;4CSs@LtHR$9JeK|L7{(b04EbY?^bl6=H>NM`IA~*j!1Cq_OgDPS5*gjWvDR_SU}bt'
    'WwG)FLvyrN#IJ^$+z|q4_}X&P)P>VwM>IL_7Kijh`JQ<3$gQH=r+K%5&|*e?v<pDON|J;-?V8>1KhMacjZ(bwPUf{#5s4&G`E-#;'
    '2G6YFR;;+YQa$C&;B&Ai+3OS~Y3Al;j3dwT$ceCp_>s-NhJPtK26)F7LlLahAQ*RocYfk+fdCuYD)GtC17#yamjOum9jA4QBn+ZL'
    '=Tvr&p=7IMfn%<!&4x^GZSu*ZPniD_6KfOE8u0<gpN!sFb~AC)x+U)Jofc*11Y(Q{PshSnH@xN`$ld2VH1R~xnyHDFZvzeNBKn2b'
    'Z3;3W)|HBL@p?aWj_{hhYRbIDsRMk8Y;Ba5gku<J2o5iDUQ`4zkes(HSV*jA(6sTkb;ZCgM>)unbwzc&nOwWEsm)cti6-Z(yLbb8'
    'UpEbBJCsdX1+-P^V>a=If9DhiXZ*iLjv<_K8{|wun!zKpnKXr;6QqT+v9noRq7*1^0v=I#P1X^S5-%Xa8O7U!E#NWspc7^V9V|}1'
    'Bo=mH4Q%e4Wd5Sd_{|f!A;!BCHiTNoQIT<{f@vnX4u*`|mD9j37AFp0N`&Zi-QJsmp<JBFN#T&~Z^}M)c_d8CgX7ycE_Nz|mdU8u'
    '3_2!XM^U=Z7G8U*i(rBoZ<LTA=P_PsgSbH@Vbp97+UDuL**3)4#x06Dp|%>MmK_2;=vFseGe<l~2iP7&lO$3E@6;-S^@GjHBW`mu'
    'umCAQb0iUYG}##<3-SH9m_oVaL`-4q@pFhNRGNv5DU=_WJf?7LTw!J}0jf#LiD;i0TN-O(nI!jHxv8<nP>Knh+F6lzNxbyc-<wK@'
    '@hN_ee5t_BgPZ_5x7YS!CrH+x9F2*ni*Hh0qDgCuO7fEaM97`}X^I7eZR)w9Yj?Qc<vK`t?xE8v&jP*r>(7607+Y_mRIV3Q!eva-'
    '4<J~g#0e(;h?!;5dMPvpBqp_BVi`%AxXL~Ur)oQeuaXRNTvf2bPgMAcp21IK?&GxF@V3|DeoNv<d@g+OXf`Zz=FO&*z}BmS;7CI}'
    '{Au<}l}tP8?7IN~l6O`7$lD>!c1VdfZVH#qiqp<)ilAN@+dSzki}{J3kK?S0$Ot_*ze6sxnCUh}s6{u}$N-%QufD3btuB<T`HVh&'
    '^0l4P1DA5-DUTfWi@W8Fem8Q{X^o%KSEr4Ta@eKD$n(YN1C4dak^S1hECn^jdot2V@N7;yn$_rjW!~^HT!`3kDlVDaaAj`KoG7qe'
    'VhS+X2``Lh&4VN3)qoYvk*1!_EAziem{QJ2b+^X&vB*QIre<gt`2dJu829Q~z{g$%8hbuxE$f^4YnU-jeL^p4l_qg2f8;YcMpF~j'
    'U2UnC(v&ZzkOHpt>Vh>ppLWT}c~vdRur@Q<QrmZeU9!BR=SHRb75&O(R`>BSE7Eu+Bg08aI;`^jrQD~f<!KCFG46B|=|?ubi(E4)'
    '5PY4E;_-YX#^bYjOFo5k#U!564?Tt&lAp{p&5H7X<LgQ2#)QM_^dNnLzY(5s{k%Mln-s0vX76}5dZUQS7Uc;LWGdQ6DM>S@my$B5'
    '&<fzg6idecdwPemQKmtBP$ENoPC}4ROk_&_A&xAo+0PU&U|gq8ugc;pbpt6e@skP3mt~AZnBc(V9tGf>ZVv=55sac?iE`*nc6g*l'
    'MCOAS#jeKv^VNiZKErsH$~K;Gl;e4udK$010kA2jfwq}hH*eEfYuWly<4M#AU0#qMKMkymix`z}pF>}Qv11>3gK%mxw|w#*krm&J'
    'VCpnJ_^Fhynz5Q~NL4Fl)JMnj)C65oInui-)o9WID0)#JLHOq5{hzyMJ~j!IX+X-Yvn@ur-*YZ5D++x%&j61}g;S{K^;RiiE_!12'
    'iNO#broZW~G5mX-9hA~TtvQCtl^NM+gikwSnBtmKj&U_Jb;a{__ve~-wNQZQvP0|xnb83XWGX^{02g<=WgxwziCP4Kwgbd@X)qZN'
    'Ai@DS8X&>NWH`W7CY(?2%uH8m;M~enrw<^&sJIACvO@<>F_(1J2*b5??VARVbsUCy!3TK=JSKm_G#<OG_mxw*%qH5i(*{5c73z|A'
    'bv_1|4I%E)i_!B4j>z-$O%NY38HSvG?TJ{<I1E?}S1@?`;EHFN{8txwk&Em(?!erWP<eil94|Cp<ExL<hzH)A;x@(xdyP-;^+JL+'
    'QZt`4goDpf5yeqNahyJiBVG5Ph~p^YIKInq92p6co|W-t)+ou!g6GLXS|AqL9ZA9PX_PJ_DiL{c1^@(X$BFWvXhIj6qJ`=bySZd^'
    '*^EGW@IvIQ8StJ&HbO&|NisS=xnz`ec_DSf+ofz4w6D@>A(fFJQ5lXZrcpT&0_&nlTO5i|4^{&?tOGVeZHQQ8Y+sU#phS8)XAxsw'
    '7q1zF$<5Lr$Vw76;0Fss(@in9ox(RW4fljF?932B4$+)=uC1z7^7e!-qGL*OHk05^rm>&O2pMcbabU~PnaBkHoFFa~qZbc%v-#f$'
    '&B!|^!?;W!o$#h%3cjUG@{%y0=45jE&Jew%Q|h}x_ef-u2fUzyUlkRc2$>2(cp5^ed8YDc;fp4JlO&*8mMfej1=XsvQ?*2OJ@|ua'
    '7E)rNHAF%^HO;_HC$))}5tH70R1+3pY*72*>wCrv_`)I9@tSsL6?$L-IcQH3@ty`q)e?7t07-G1`nXkV-}s5x*nu1yTE~W;{+{LT'
    '^l-}Go5tajepX)8?JGatx^eT?60B=(W@c+<W+tcLxpPRsZ4Y`}I!$fJD(z4?9fidop>xl%js*R(itR;@lZqm}^!>Hlx2TNuQpf26'
    '-Yyzk*HJL;fl9uF78$8gW`tiamP=iG$8E-91~al#6{z!EP={MlQf9h#kCDmZ+C3V7s*;)W^?R?^u(my~<Ji5_{d;VFIr=I3H3UH<'
    'ay3dDTc#}I9eq)8+rv`KC9j9R{F0$)xCd-nka;Sb8Hpa^k5S}?SN3EL3o0+uIm*r01*4*WVb$KJK$&tE0KV<)(D9-;`M&R!BH@vI'
    '5nbd>cxX6W7kC?0uq{<Be3Ov^qiOe61{f>C!YX^@RN2P`Ex{X#w6|T7rp{o_#f<nv8f<JJlokSI$s=Wiw-rk=;>UxAQsHsQ&>@%&'
    'g$+g9r6uyzS6sCai7^SBHwfXeDzeM}RsoHAPSx7>U9@S9v|0NiUx_Fgx?aLCYx?h|aEbf%05D>}#$b}#lu(B@K6G+M;#^uP$dDmo'
    '5kpTCE5v0(qs>C&zal3YJ4b0uC`eEREyp+WnRYKTxDozEacr8WOwnngG;4!G0Wf7R=H(R+tNbvzOF2M)Dj-iy0A!K~na&6>w;L8d'
    '$VmJ}QTTOK!mLHbEO1i#<dJZ#dEQlbM`c9QW5}mWxx`S)R^V^f@uv*gpcI9w&}-tr+lQ6(x8YbdZA}SD;Vgn3PZy7^G~o2uW5RqD'
    'J^V^J;#bQ7lhFHWqQfX(0*8p<wrb&Fm-_lguvkDkX>&5giZx@+h<wfBd=0kcko|1q`=sT76Yj`p!Wr3xvt5CDJmbMA`i%Glt9H1N'
    'l4B6jJ{ZMt0ons9#9NrM6`2AGq)Y%4N^(98d<l=FtWGgHjdjXYtT}nhISp6s%gW!BVc_YTOG_A1d>dAVUQ7KOnW??U77w3-VQa+8'
    '4Q@021DUmb;3G(<Y~Qgd4^K2;X2JvXSSFAJLqYa|`(UW+W$SgogY%<|=rJaK$`j4W&680AxDf4;z7}JO1SYu7WZ`95scE2pGxR&~'
    '5~H%5de;eU_(8FJjuvc&S!>wbL-M1D?E}70&J8!qhL}0O$+#5mDdQ%xCwc$ia=nSK%4prZ*Qcw4Iq@!%xsf}4d<m7a3fbH)mOZ)S'
    'Mb6Z$Z~=}d@tyX<5WgfVY~kO4&O8^p*>w8h!c;vx46F5St6Fac`_=k`0Qepv=`^5(EB=J@wbz0@tlIrPtds<)>8K@ioHE5_MEUv@'
    'vfvbg%k}k{O%@5-70sXp@8H3Fve^9s(K)f(xd~Y&_n(`ur5DQ3w^SMO;RM1#YafBYwMDmsu+#xFWCBO2R4J6CLP`2sm81#o<(ZYI'
    'j9XgIq)uU=PRV$^>FHIfQ(s3KeLWXezL6@4B$l;4h!W^cWtD;ImrSUaOr2gYi7S;!T_g%&-=^U833QW~%K9SolBs9XOVV+B-#N`B'
    'M_1tQgIwr<*xGb%(Xb8inEKxmCWB{GVG8A?P+kh<<%KCP86F)ig0`z}N~6k>b0h1rbz|kq?ImOuTX$EMR+rWUzvwf+h|0G1M--IW'
    '_F;O6pfr4cWW{KwdW(w)*87`LEP3oT)4u+uF>AJL1aqKlzd6yg4eO2NE4L<_`Hp9IjFZL}=K12Ays5qc@5|A+08I)~ZdhXGquhZ0'
    'oZztu5?^NsJ=L6y*kjU+rq40+8FlbUD_aw?&A4K~%lFpq-do$cvAlBoirkuZa%<WGsc2+QppnEVdKIj<&A38uVcdy}2~V<6R68eK'
    '=GyX|C9%50<mwK2bvPWY?J%)6d=ac48dtUk?_k6U*L6Bn!ccPxoS^BkdYuS`yDA>W<||uHFGf&YjK9kOSehYld%;Jd)t!1FV{W2o'
    'H$j;RYp@1J3_=-|^}|~;98<z~Pw*Iz<SQXI4SGGyE#8QJ$Aq^Dc;Ph=8eS!-VBBp1yb(mgt4Y8o75s9{j?wb%b{JVcNKz;p$^O$>'
    '>($6>Iqne51#ouJ+ym6Bvza%T$fS^M!Fj7{xqP(Lg&Y^8m2pz>@cvu1SD@v6*kl*84~^>9@U48|R+B(5AH5nO(>`w&UD@<O(yKvU'
    '<+pdE7fQwzCX;n{6Lag4d&elnO1qb6&tS5v)&mZ-dB90A0Cf}6NW-!#l}aRvWHYE|J8RpfyUsk>D9L)x!PDV{)y>`BU~G2qNxv^L'
    'tjE5wy65(@@4m$7tm#~qO!3~?ht=C-Nj~Gk2LA8ZQ01G{=y}Js7eeHBS%^eYs<s1scdC#A3n{RW0$-#QxVPOhuG|WCJwI$}F$6He'
    's(1$dq2D(}DxAbtTF8Ydqh}!z782oelL#59g~#>lkq;-i{IlX<%zTh@^~aPL_Zf=M277L&qbj)4uTs_Gr`%%S@mp>)RBgm>XeHmw'
    'Cvrp68aT%|`@Vf%m8p2EfUqICxHCR)y7Uu^Jis(-HLWTw`)O;mKDPkR*$esU{(QOPr%Lyy85*)InzM7+<@qKp4um#Ow0+K6@Sh7a'
    '{X@<*BS<R2JDGWA$LZCBqX75POkh{BSITi@%pW7}9b&aUEo;p71DJc==>a-BL3#Bjt7}WQx9))2v|3?my^dFXHq)78_SDQVsCR$z'
    '#4%3?uZu}|3B*i7Okw~m^GDnw19IZ+WUw=hnhC_HxjfS^1d`eJvMKr|Fy!2!=i`#@$jK*??!+E*(j6KzH|x!izc@Cx%_Z9p-Dby`'
    'tU6JqJeTIThVzVN6EJ?E*FxmNl$Pk8*!FzjR}E_hQ^R&VAK$sXUB`E+W@j6id*TuL>8_wt1D|)CHa%<({D3?6J(p`6BI%?mdhBmE'
    's8e)-nXYQ%p5W>uZJRTqFp@impuV&y&R%bvlfmcGDiM$C9t((mov6%~OVu>7E{)gQSsd!8em!bKnRd8IQYRhW=j=AGkp5Wq6{eH;'
    's(uPj@u1(r_#XBY(@RXnzC|%v_g@*N&P!c%;M_R-uMG7*qx+=gB)Y7tZ<0i+ekq+VsZ?_ov+2cW$*Gf{6K;~I9S*<%kPo^jnr``n'
    '?05^xK-45U*70_t5UUxI(FUD~gFX~O-U6fr)^<@$A{v{{Yg6el9apI_!=`A4iit}UY7omvkTl#C@>L;U#Z>m^BViS?)pLPVAyvJ^'
    'QdP>5R>)O_Tvf<b-%z<~5`)*O6Nd2pVDe-)B2kH+sc7=FCDC9@Jph3tKd<)#&e#W3?uEg0ywSKUD0Iq+KH-I?4#v2)qT9=uJ39K+'
    'hUIG)pZmVsB)TAK1|}l>lc_Z1jK*Zr0Elyfi!1$pltm*uzlPoFx_JNT%o$8H+jTBu-b{KZTVRDMd>4obJbh-4sG=i!$2(l5li(Jw'
    '(@Bq##Y+c)ECqTmNYnzoWcQ9vSz6OnaMGv;#Kdqhv8a+FuOnSPkr$O+J(0zGnl=watCQo%H5$5&l64nzGyS}b=Z5!xRk-9R8v%(o'
    'z@2y9PRj?@Nl6IkVe}FC5_K)mVe0h1cQA-Uq#HQBlaIZ6?7oZqbwl~3QRMwNMMj;13>0L*L<Vvb6)_V1An;N*U1inJ_<crkvgE9|'
    'dsMM`;A83Adn>nuV8l8Q{4S%d<Z8#;F0cP!b@@)650~3MDz~a6(pIgx$|hcV#Cr)1k`H3n3P8!LL^uf_X?e{7;*t20z^Zb|#@X2Q'
    'UEjf51~4J~g*O#M@mY+z0%Zkc`JEb1pDs9*u$j2CF;6S-oqcalTLBD}x_YeO$P{s{-^sWH8M`C;02&b#`nDf9<@miswaCOx(xLc<'
    '(~?EM<}JDb7)Vm3;~lr1mU+Ut`kMOHu&(&NeFP_&{w+VKfW-X(<mU$}vv`2wGLEP&m6Aj*&v;!<1}G-g>ytn62Tw~%q9Ds#<>MzO'
    'zdU|?{O98*$DeYKSff$pzPR32wbK2`?u746H(B#*DZlehMlEGo6VR}ipmEx%a)5c4d@(s)*V~VFCfbKx7jLm2P1BgAI4t9dG#M&l'
    'AcVu|S3AMlh#sx7ktI=Jj;syQPmt^Z;-PQ%0t^##e7b<&p$q$V&+Z((tsW(c(@BkfDs8@-AdCd{R+VFiV@IS_2vyaD4It)u)8dhc'
    'K}A*}{KsVQvG*O20@h)zn~h`)#|VQL*6Vewbc4*byiU)n7Cd6I&iYW7hQd&S%4TI#e-^Xnbk%ISFm87=6k~9`Qx0!Cl=V)#mCJP$'
    'Zs_p**C$r&=-~^}b}4SfWET=aC+1vCL37t>4LXj$Cay&T>jvb(J8SCIRurWAz}x0aj?@OIEi9;^ezrv&Z!@;_QeVI)Tkw_U9;nP{'
    '%>dYvDy`bYn*hV}ZeapPM;O#g{-CyUuY|>wN`HO#pGxLT5MPOqmmA;zv?AV%wSOxd$~S<E^JBUgxouMn(ShyvreY&fkL6zHXq38-'
    'XHE-Jh#rOLQHUOe=<#h8Jqn?t5IVlQEPG60qH#Ap&^g_5Lfcg(n=h?8J66njE#509cU=^N+>$S}qqDCcop`&3wU5WfVvGzH(vH{Y'
    'V}W$Kic>}NVdpE1E69+lZYM2j>l>x`CpSu)qA!XDQJD8rUW>u`!Q(-fSC9=cy-^x$+FLqG;{llLF&QYa<ud~^`RP-Ebj(GTJXkB_'
    'hl#9;=!x+ck%TAo=5=u!$!*0XRT5#NjSx{8b+^~-3;<TxTxPGztH~ZuQ=7_1nod=l<~^z0Krxy~<EH1?rh1TyA5d91Tw%jPPLyh2'
    'g_j~%M=wg2rPYVlFido5@C-&G8&S-$%noIlO&9TRqT5R2`S}z;Jih1f08kllF5>U%_6fDlG%awp6c(|jECBVwaBhZD>?{n=&&<G|'
    'nm_gMO|Hl}dx0GL>0J`g`H?)qLR8y|<_BAKwKMQjnN#**7w^z4(uG7Rehl**&XMbP-@3G5;oSHKZmQu+@oh`JW{MC?v|<c8S<Sw!'
    'aY-uUDwZT-K*)PXPkFTtx(`BcOVr2Na(V>hj6-20gQotH1S-0#Cffz^*YSA*BN-vEnAu`{<-*hFxr$UEbdtfoC!zwfDryzny5QCY'
    'w=TH#cbHoje7fM%-yS|aQ7{~aTjqqql_tz^C+!GgI4v#f*z3J=V+2O9g@Nx&lQ~A15qsX1W)ldVM$pKVa;4K5EnZsTjk|UrGaz0V'
    'an?gIBeAhpI-Ln_1{<T80m;sftX-^oIg=58jQKfg=&A|KVaP#7GUzCYaEAkATJ}+J!}q%7ppH)>o6&rncx&zAwxxMvR!k9vLse4F'
    'NI0he3=326+S=}T%{`|D2g4>G3fj$@p4UN#0~^l-faSxnz4118tS8+ZN8|XsF};E0k+CrCAm{SiuD9>_`JvjG*gUnEL1|)<%>4Cf'
    'cDw;Ebc24!KH9>tG4{aaR#@MME+T>FmWV8#umX8%Sem#Z6^20R7R>mSAzxRA*#n;N-xw+#J0JXbUH-8-(Tq+@vjVm*Z{b~?LBIaM'
    'b9-et<p1@Fh2>>)VvjSEkyr*>CtZ<==&?XgJQ+^w%8rMQSw3d6F1>yRFkLGkBQ;p$OA6{`=)rk|m-k;8*08~djo17E8%Dk#3;5Q)'
    'j)(Ia&Hz8oXE*xz23mWG*4@{~>-T-{aP-RXwjJ&Q`8dQx-q^LmpJj_O5&-S9$-?gjO|78h1ttGRQ}S3;YeCBkT3*odJYSiNtlrt_'
    'II9kZXOw%=O|R}~Ivq)}%9;tHS0UBkr0VySrVkU{6qO`ubCq=Ah-|Oqb>GIaD1sT7@I7@H`6#As0oJfZKF9o{*kX8R9Z2<WR3Tja'
    'F*37`R*G%RG21vdlYId(gHXZb#B{Q6Q5h4iv_MN^VmOs+!;(isjIGcpel-hDG!vQ0uV$Ghe%dQqr%j%2s_(ZrEU$0yb#}bgxKR?*'
    '3iwyx4Se8v8>LOOF4CzG_Q<_-^^Co|s(x4<1CR8csc43JIYBKy%mHX`!}mwJKxJ<S>wB@n7&&xVeNU~NFl9`3KJh6g%}A!?$;c<!'
    'WI?+vQtn$_07bO-+g|HvtIM2nI%6lb$wqr)!t7jr-Z!r+#}2})#o8-t2VU+K#(kAuZ9kEGZr`j>MyJnoC0|{w&AFDZWuIfSA#ty5'
    '?{LZzd<=7bbt0;~FJWGZ*{Ve91VQFwt@Myko$a*Tc6)?3SXE<|6mnz|zHqy*^~k)1%fwg5H_vxrW7hY@A4={(;09ZQD(BE~Z!bp5'
    'xP3&uGw;e;be%T3FuQNMFq^sP;hEI*vWsy%4_!wQhm~zWLmh>ICQ-;yL>xwAGW!j2k4;C6gFtJ5XI6XANyH5skp%y!<IOsC@tL0B'
    'ooD0%_;=sNOV6BR*Ob3er<eUY91f>NAi>Tx_(`DY%NW4u6%eI}jz-7J>)TB?JZe~H<X~7yPwzide+|0L5+Ufb>AMc{yBh*s+t>i&'
    'Tv5_Zr)oW@S~ku3fpy8UCHJjC|99T8I)YntWZuPSVGn5ZXgRN1hK1BDu>=eLI~sP>&c**7<v6d#QdPy{GKs22u|?xl%7w(maNrmq'
    'vLexh*{6GJ+HM4ppg!<BxzsY7NM5q7T`CYG24T0w!W3wjc5e@uJ|O5+&%+!8AUyUws(9p+{w=H#xLe%$(zKn+2}SChGPSPMcfBAa'
    'y$)I4Q0WmsC1UQSysgT9GxWD<SM<xSk~rw+O`UN{EwHUqW{i(sNVgOt5(VKuB@K}+%KmmmlWKJWL)Q^SGRdTXKFtz(UOvgB1*y<B'
    'zN^}XZgwd&jY88XG>xxH(-@cdtI#qEEu+vf3N541GGa1Hp<#SCG>l22l-A^>&D<>Y;_f0Hm*{$9*l$>}|Mj)y*lkC?;|PR7WHnWn'
    'L#F|rePq=4@v<$o!t1r==XGE4g<a>G(7PW-03GMxk19f>dCOAE#Sk>0gK!W~v|GG%w=)Q&=l(U}myEs!%_i{LXQ!T@lF^x2S13dT'
    '^joP?9fDH^ltwq1xij(7l(X~iQrSB5Vj!O}4`u|gL?+C{3oRFBc_Ni(TwFug&&iaT%$3O}WNZ|cMyS2O<v3C-j122=_nq9zreoau'
    'yJxkGtzIu&1+<fg181k@L@<T|&<cXBz;VVa{4wBTk8F`qiLCuPaGae1Py!He?)CeQf6We@awYEL9TzCjKZRN?!WR(0H6WsUE(vF-'
    'x4ucgZh=B}tz&o5wJx7s^$wSP*WnbSuxYTvHYvWigIF60pL6kM-Yi@g=nzfc<x9YL2fa^vTb@dkqkoGL;}Ph(Ou%-Vs4N!<x)i&i'
    '*VcN<&%!APV#U8`H)Zj!^sfGI@K|i$Q+-(>Z+_kF2-gMy#xdhmDLdCz(;MKSPY`k7IAe8?(-i^=x_OlUUVwBT$i*l%+tIk(q?!40'
    'UEts~iYYUa=Prn9vaY!u^u7L|zcAHxdV{HChFW|`#8r@}^!#r_i*meKl=hZ>A~U-UU;IAknQsGe0bxt9wTn#pV_a+uCM0Gw*4>X}'
    'lkG;lJ|hXWw*#*;2q}Xw=)${bNt?rD!Z5FH!#aOKOa6PYDgtV%*4sA$NQVvUY%bwN9+n`F=?&}I`!(bq`egZc>e7jXxyX;F2@ilo'
    '^TNO)6Is9;O*_p)=;t{ny8F-?^bIqDr<AQ_GUR?H$f>PXnV`8$I7pHe&O$x`Y*$bSHUn3r<47w1*_A2<&tI%m^6Uh|0a657?Y+Pe'
    '%1M8LADdJMrXWIl@Op1}@DBA8u_lr0@h)g*m|%WrfhMs<vR{MLn5w1j5z!~oH<Bdpl?~)?y228lfY^H_;-}OZS^mpmoTX(V{(642'
    'Qu&TzBSFwDMFd5>GJ!#!0tJXwdml-dwzsh+8B?7~Yl{K}GIhozMkwttqUIuf<#o}Zg+j4!&=N`ID$6gLHARV$CVkPIyQ$FRzH^#f'
    '!poG><q9qC8=%EyL|_+sT%pGmdR(E$6?$B*9;c{hp~DqATtbJVpEVYv3uUfQ=DwTCT<%RJV4M3`9h-_E+=g*PU4dY*9l%<E6#fXA'
    'z;*|7%dj*eQg;TRC9WqPZDwSG-0@QRO<~$s2f-0n44=<WcZ$H1**>G1hiRR18rE<hGtcsD2pJLk%RVK$eR>_U?e;*5IMSvqDn;bz'
    'pO?}e;TS((BPklwuqu)I{>VCTTTVJe5yWsWM3w7O=Cxl%xKvnUgoI7I*K|7LYP?TSYktR*rR5RvquTPLxY*>qfxdhjPOz?%E*e-P'
    'u6<u3SVn->Xo4)R_xEeBK+F50Y942f8BUjb0Jh*A-28Va9q&7ct?vMuVG5PXG)x*0V83FZxu8E{HygxC5{lIqGJTyO^#u#VbMaiT'
    '!TLTGA>$|)WA#C521K}CXC)ZOD|9kti8Y6DHLNH_&IHqZk+aKYV&jrNMc5-KQdY{RD8>o;MQt;M#Y@w44ig#IM;Rq{%mLN~kt~R0'
    'K_s7+NPgqVV?h`vAdDFmr7S^|!ag8_phr}mD%0+d8uSs0*m%n%qF^F{y<R~;wv$=xW2Qos<W<soA=#H-2=Pi#u93NV8ITa9-)u3x'
    'VRzlmQNx<rDE$D2^KIb3)@^8kb_Hw+JJ@uls=9ggENE43&-uP1%no(k)__KcgI&;OSFt0Nl=Yn&n%h8amDe7iiRZVj!eQLQ7Tfqo'
    '4IjnY$l|serP=<W6?h%ccqr|D-^N&IRD(0F`CLk<IGWv@)U|IUVMa6R8Jcn(SYsDBD?UI9r~M8+@3!63i8$g{HW`<$4Qw=qcu$xJ'
    '(W%iKrwl%%8%Ul^=@4a~aiSjcP0W3Gi##L?!&%IaXrgMwZ%^TrnRs<**iI}CALXo#dW>6|W-pH|@Z3zs0<T9MUc@pHuM*3|NAYDE'
    'j2}eI4Hik|&%vtHTCHkfz#@=TRK@BQyX6i7pcdz%W3HWY?n8ksHGW+YUZSaVN+X&P#cgl5q;;5_711=QJVno|>hqNbRG1S@j@&1a'
    '$3r+gkhpV6?4^Ay7YZ-1_I63t+b(GoiJc?6ozW1(`%B6@U`S~clSbrr2+8AhC3%ob#fTkO;Y}JXfV(s?@>)yyiRnDITk^U}#ftu}'
    '2h?`W!(32~e7eRXs&{ByGG>yp^1-X2!vW_pEzQo%{7n)&bm&De<^2y25n;SRh}<Ruyzd0Whm@<zh*ioFR-z14rFibqsY$%%$h0zi'
    'Z2*{tbwTAAO5ItAohu~~j~eRAk)62Z6*-;uO-`rb{oxSB!BLdwrvl`inL*^b92)`@pBRuKPzM9;=4p;6Bl{AhDKJ6HH$5dyu8J1Q'
    '2Rdp4PTz_i%bd~cD*y9F$scS)1$8z`EBA0kN<G9!=%3VDEZxBtn;Fvf=`%E^vMuwCIet22%Drq#-aI}Vv#D3g-p_aK=+z=lCUsf!'
    'Ss4WSMUzY(9_8_P>@k+bL!%6i4sRyrbd%@=WFiMK)Zc@%H=i9eRA>f;W>9Db-yF^0JE;>C+JL4Fusd4>Jk$aQj&%$0{*?Lwk5cFd'
    'FROmQ`;UOC3Bp<E3(rSiNQavgibJ6|e07S$H&12Ay=+dN%%JWM>S2&k4P$!Ry3*-b_ihTmX8?lozGLk=zGIc$*^9jzMui?#>ed|('
    'UI9M=(cN-Dd_SNzF3=3G+XspUOr{>2GuLXC8MaV<PtaqSEP@qC+wq@H-aUSD{Q2>hC-1|*pTU1WEL9U+vuE#P3GyB3^uvDt{rJ)G'
    '7srpF_e1P?@-7?~QRM|+|Ka34eti7+<hSrjtEXH#{(p}j9{-uX^~K4r;APw1_k35p{KN4l$A89QVfZhg$s=gMNe1xkza4*i{201^'
    'Mjd?z7fLVw_2m7NU!437{uf`!f+qOpk1#`+46XAo*d18{P=zk=09wkw(&8Tj5FW#~qvdqmZQthQ{EiATe+K{i1YSRaQ67@c;}Z=3'
    'kCT5q`CSR~Fdy&-pB#U1@~h*&STL}HF1$w`)_>FU_psIfBp~2$59KS4Y35}<CICKyz7Ltrb?koN@VgHP?q8hz6jt?X3!1=Iocsow'
    'ak#4-{gdp5UC`ZbF>%AK{0v%uz|huPVcI9v>W|ds@$rWMp`XiL-F3Q-YVq%Cx`V*+Z-}C|gk*?XC%=Xn0b~fmkMK7V-2|#pxn$tU'
    '0U{jXUFrD0!OR{a@M)JA^rQnAUrL~Vbn?^VPX%-_d%1%n0$qf|)}+ed5=bB6WGwjS38BePkH16!Sn%#6LWwVUFCt8bH=om<bV-Yi'
    'k8|=KOadD{fr-E$zeS)y@Am*;7)+2_@D7F94=uZi!VfR$L)wD(8#swiX<;AW6I_W$vJ!mdGkEe*U9OgQ8kc|a3;OfX@h8w66M^H9'
    'A5rJNjgjNAPgn>(oasYY_$PGOymmX$1d;hu*s$N=*fdf*+T3WLQ&XV_k1d2B!a_#@gesjxES1bC@)^SS<R1ulgo8*O;1E$U<rE-L'
    'hfM+t=Skmz-@k=fyq}oT$xjU!$69ZLf>Zi5<Ud1?FJaQ}N^Av8#qI993_PSku@-o8h#G}VE&fCVK$1Vvo%DS{sl@sSHSK+Is-K+v'
    'Opra<hXXM2?SH@y3M}W*(42rT{s#f(-IHI57nq7henfwcwhTtqM>G@xGqFMy)r<}Q3Gjg^Uc6CCpF&%fI0iVE58<1LNU;5XefK{J'
    'Y!nhI!SWG&mv`eMwHV(S@M8WXFxP-DqG{;KTYK34_twcTBUYj@5`IbKJjqH1J-yL?@OvhY&^+DeL)u!t2qqVS^ZOK@0_M|~;OC=p'
    ')Hk1q>wt~Naee#51jSodcVT#j@@KHjU%+O`Ef=g+wfGYN>`TF$3o)Y*GYT=I5HkufqYyI+G2_LF85vQL5l<UN<j=(1C@(J^`+q@*'
    'BUz&7WT0((ewW#vdU^8e8k0Ae&3n-SBpyig`0aEDf{#Xb5%|7CQ~EP>#r>o6ERF_UhZW$XZ#|-2dqiXacn+{#>+B2?VUQ_~|3bJ='
    'x5EO_$pWnUoKWHy;)wi)8{JZu#!AQk-|;6%srbdJylocarX(E*nj52WPhdh{5U$B-{l$Rodcjv7fX=z0_ao*6B&*;H@=b6JSC(?V'
    'zzG2)kbZpDux4le`tE<9J+DAe#r`Cn!TY}mQi#V3p!yF8acue7$!{$@YR4ZV`$AmRze?n#x$CqB9o|5qu>?Fi(<lEZb`FbUtqghr'
    'OFAg!e2gE(!-XG6kafglQOYk8K>6)sK1d(nfxwx-I&l6c@1bzyg>D<k3tD~o?0rDQ2<0OIH4-YQ;c_q4<m9(vbXtW#L=Z)Q&wOBA'
    'b%C!R&Yd&t8I5<x3x%kLobxfDlciYNLyII?<b{A`AIoD8umfsZMa(ly)FJ}<Gi389!>O_0e~H=G5zqR4pc_c|iA>N}e#y9Hku3F*'
    'l%eoUw`>*+|NZ25@S!gd_9TRoe_m3I_vu*Si@+!>ayPV@x9rd+Le8WN@JG-nA=&>g-~mKtfnvXJ{a|(Z4x(rmU$6BAj()D*>x5RI'
    'bF%}BV_x$MF$1yxk2T@{H-;Udp4TGAKm^p{vnW)GpQCtCwUCDq+#e+<GcdNF!RtT6=6r-C6nBYPB%bGAfn4;za0;}u%tsKDpD5N#'
    'Gp!5$+e$LvM}lloF6QN4=SV6hEE@|%{31zvEh14L6E3kj1|R+uXOSsODwy*mG?1Ib3t6JObo_toqCy&UNI@TX+pA8~cLer4B3R<o'
    ';03WXe78&}r>{iFne_Iy8w7&6e}P+&XlIpS<36uj%XgPnuB_c$zO!2Iwkk;(t7M_N)krC^R>Z}O8dyww5;zwOwpFJ;5gYk{*8GnE'
    '41)T5fEXZwoczW@T2CYtNd|2Ppy?MWwXBL*@pD16Kaj)xR4K-aMLkA>rcgx6mmdHQCUwJ;pVkdXe*k(P`lE?|ckLaw$t(W|(SnGP'
    'pvKLP?YnJ4x&M&UmebHQ>4YLp2!d&V9VzA!Ne0rJ7I~w|U|O2^gnmzF7gRl<t?vug%<wvS4}m~z|6|-Ke*G!YgD-K_4U51E5J%>P'
    'Xu>KOK=NIrw~vv_ey9-l7ZE9aPgi$I6(jZSbG56eaveW3fz{IC^>6WUKB03*C~KWXiu**agmoT49)#vcwEG`PNFe6$gjqC_NnC@('
    '0FrOsMN30AQVCh|i4b-Pd+V8|q(ZhUWV=GPD`dMuwku@2Z<%a2C1pE{f<%-l`1df_FJrO;Ewb(S4xE^n#hBQuBzUy)PslF*E>R<Y'
    '&?8?&6Vu3)u7!TbnzsJ>>pxhpT1!ZB4H#HRm4#IKl1i1?_o=-er#;|P$2*G;+0WwjguwYoEl)GL+D*IVba^BH8;K+z5iB0dS)ywJ'
    'aAaTy!h`W2xEvB(c=b%Q+L*bp#RT`CXd6E!0{$Bmu*5h`uh(=L+x|~9Qxi|pKh*QKj)3<H%Jn<+bMPK~1md3wDYt#M#UkXt@Qzq;'
    '%1D+(_@UQ;yIU*ws&Q~H-KlEOhWF@ppwSS)6V6w`uY|0Dn1J~BA)UX!uv6&xa~O{#8nLcNCqHMj{4@L3Sh}!|KL$K_j|2~r(H@iR'
    'E)k!6Z_&JdA+6Vdcr_wY@3EL@LhH8%PCzo6!i9(y@W~?vAebF9ME0P8c5&eNccV<L8kJWdQtg2MgE}+N9Mm6?TjpbB^XGP}du~5!'
    '^CeAQN*ZM%7cjeuVIgkM4P7B^L!Y0~7sQE)Gac#aZAlG<JZBbtPG=537yc*^41GsRl>aJdI61REj})$|#XR#diw(pwBqddK4RL_~'
    'hXs|#QoLa4gNPP>6p0nO66re7UCOn<4%sJsx=l{xwr_Wx1K~tQz&+N7Hc4bKEQXyjDf?LAOKeoxNSrHdhvUNWm2RA_h+Wl&A(g}$'
    '+9SeZYq&jP(dbj23m|&=ufP2Lus`}6z<7%VM;ewX<74Z}-J2Sx1SnVNguh|CJ^eF}Sw4AW2{G^qyZRoJx9L|XzFI_ZK4F(D>s~}x'
    '1-Cwa*svrymU<kEvN6ojKw>&Q!LE0(Oa<wTn1{#%Ev}g$CElxWaoyV$`8przO(c!^z0gn|OUC(yKpf(7jRc2?lvP1Zs#fH!1p4tv'
    '(wN7z86PSvi<pve>6wyrmau}DstARQB6&#LdqX|{o!qo2$OI#ZrD*seZlZE$%ai?E;{6ov(A(kb1E2_fK$`6nlyy?GZ@V35&GW9h'
    'gxmiYDczsptVyguam<>VnX!)l`S^Eq7@;-Do#+W|C8X3Rq@_HfnS8-mPs?V(<)P>;w@!D6GEu9Cham{CAWGx^HiLcq=Rx50NLR3T'
    'oIsMEKal5>b)t`zOoN02N$IB~#}Iiw`4wS3(<nM5UlLA!L~#3<<xi=(l9N0xie+v*UOucQ0<%>}OpY<v94kXvurpp;iu9|N5`_OO'
    '3?Re^4K$nOyo3PF7%tccQL*<~GE|(=YO(_T&*?!)OCbC;IDLhDr?D86A>(obJ|VI0eL`Uh7D=IG!gW08A>Ony&cxXGC_ZUHGGMFc'
    '97JdBkHV4u+i2{Es;i79`=fANKa~23J`K>_WYC#()C=O37a$NzNf}Ki7SW)-bMn*6mM&Exa!b0+u5#MiKPO;Rj{*&@n`0(Sf^>>%'
    '9Y4OTqAptc5YlEq!U4X}SXNwliU%ZQYDhPzmLw5WG15cg<bUC)f;S_rPFhf4;d;ZzIk6tRrAvoy5DHTIP>Paj=Pj1LEj$zHjWZp6'
    'No;dY{vVG2Py>i5Qk-$P2xfiX+jk{<P}Y#YFxk@HlY)ZKMdP+9Q0Squ4}!?}rO}#PA%Qd8^}Rl6F<0c@0*JN?50~MOD>pF|&+~R@'
    'J#Ww-v?K1ey^RFp3jbx5|L(x)RmdI>()6x}wCc9_)4FogD*q6KPJG`S1eD~NZG2CF(U$o`HPZS%Ao1}%h7t1NicyCltAD~wuLi#@'
    'U(y$Fmp_kMS>>D8>8_?7IQM*Pc8xk&SK$GcwT#|LlKbzPacegW`$648`zD<}7IXz|06mbbPVY&r_)GfvkHSnR4hDvd4tysH5d2a`'
    'jiLt6%0=J(p(8@C$kd90p?dy9ryuI?V)XuZq{(u_I~;zQ5SYG*1ZiQ&RUNKLD`$dKsCH>NC}BEVy7R`(J4;)uOV?JG)&%>N3iKDO'
    '2jb}^R{)XBMr4{M@i)P}r14SNHS5G2_8s4CbM)EG>oHA4vV6@@PqHnssf45;wVbHAI&k@+XqJAcX<LKP>>ePbe#F+Nm~|--*2sTL'
    'zh|SL2!$1DB>Q$gM-48`I(5VCzvxEW80mQ$b8SxuUkcT9Fc9ZS?<fhtNZT-o`X4mAE+XFN!WY1%KHe)N1E0h#j6609()5%fF;Ctd'
    'CyxO%gj6-Ob~;CW6jlEEFaMeHzmHTphWyMLg^j4N5fwI~!bbFbY((m_80CuAA)Cv==U9p2)}P-IIy_=`07cXjx(f#@i@^`c!GH3e'
    'CCu{xvyWMAN!nKE9S0Tvlzf_!(?;G!Jo&#a3_pe8r!f2!hM&UlQy6|C!_PO%!ZTJYkfs_;V{#qExgLdPaaN9qJClcm<${DZ|Cn`4'
    'gPzE;aISt`w{&iSD!LTAL<3z8mfRPc;cnu6BFdX5m5n%i<|7!Vt)^fdsR{zF!*m4v@U@(DvIneNpmRMhrlc@&6(+92#P!@wT+hk$'
    '6sI|SotcFq?fPnAllsQmr1DcY9f5K*9eR6CF8~QTD}9q?)oQJQPYkctwh>)s&(Cy&WR}rd%>klN3ql(c8Uj;n4z}H9ZQFU<b^P*7'
    'eXfdG1mXW@<E3><iE*aCXLal&Zx90gZGjBY3*7L?`rdTva{<u$ZQHMj9C~vXXZnZp`K@a5$|y|l!Z}lOEU4mpo!YL*<9c>(e5+c}'
    '#m~nYCTkRZLt%*JifeGxBoNQe7=eh46k#{$_ONvWwLDWhq1B|eX3p5U<=P!@M>aZtVN4@Ow!E0zQtsSE^AuaYec-5>y=F!l$~&xJ'
    'a$!7TedEwCqn=<5aVs1IwP4U}l6@+km6RUVxWrU?E!_3M_It$2^seGzb}xrzP(zZ%ahTk4`o2Rp1eB`mpel>pAM9cxQ{b+E-<It='
    'R@dF}sht7Sw-Xa?+P!@{FwB=qFC^hY*;=z2!xDWj36OM#R|9A;qwC!1`-!BiPxZOetxP7MHDsO5>aq)xF*-LgfwgP5FpI3YO?Vjp'
    'SS-b<srj6teI5|P!?T7S-2tGDp|uSMq8HA_d+@`|)^iiK_V!M7`tXEJdgkD;O>op0mD=7ZA=q-;?V8<cnP<PflhuV(j`XC`Jw}-X'
    'VXEPKUbv3eb!v1MXrY8Rfl8ZbMw^Ofb*D)+`N9x3%4N>qDysP6;gcsf4%~Ve9GZp2DZZbBxnFz-C^7n^s8sPFaIT5GHvB_-vD9um'
    'P5yJmY16-}m|v($xnivq$8LsqKw-r+|30XpB_E%ZV#Nxh4`0LUc2(<|*FUOSKdxFZl&^Yr22GSBat8oPvj;3hcHy7q#@Cl`-yPts'
    '2GO?Vb^G)?YiyAu_s*5uORHjeeD(5X^uc<4n*SdNrSG%|<}Ow)#|*0(<Azc1L`v3pNyiwj#ImA^nO$4HwY;+00H8O4%3qR`tBRa#'
    'i&P?^*|7&LCz;Wln%4MTg?)124yoa$X8aP{?YUjo+-Of2MBX|etDT|6Tf(HW<0COOwZJ!(QnIvVeCgEkx`&D3%0tVAt)L57K;WXy'
    '(Na%q$$DE}sHJk&vv<efx$d?$F{!qmfPFfVjMp%wYnTxE)N`UV%1B<^=G5Y)XmMCs5fd;^t6a^5hB!Bw%sPkWOiu&Rs@1q6M?imP'
    '#XdYE4M1!wNWoW23JMxf(12&90U3AYL~-Upu*;R1B?%~(^;*b?0tm7-9Qr2AcD;lTKyX>GN+_e2xMoAD903mxuvxHPeYGbmHOylI'
    '2plFTmk+7udc9shtP=RD7Ly(PfHm4o31=49Q|UV1Ae1$v6Qdp0+vJWamtFep)?o%`78YQ1fP;1R{LD;h*iqG5Pk&6-=AngO3lHme'
    'g%d+&fJexU7KgB-ofa%@luW_Tn}PK)00F01tej#j!~CfWQ+*GUrA{plT}qJ8$@vqNiE;j;STcSZ)*_9~dIjDiu&5}pO9iM^sa%;i'
    'KQ;fwNo9J4R?Uvv-}Y?3WgWQTu1bk$m0b$I34k0QSyZ6{6Ir@Dm^rnsI#m+*7#%0B*4-ZTnrMEbtb}W@gc$x+8Wx5Exq)+O+XG0#'
    'L5O?iOR`cHm%K7epnia!Wi@hTUhXZ{1&<0_4bh~5YqQXyG}zg-zBg@+OrJ^x28jH%HsE^8YYw_tsDyd!Qpdqx<&rF&f>p6XTU0k*'
    'AcUs}M5pSq76~4%wtI*?Eqdwo?Iv0a;oS^8S6`x<OPHmh*SdztSPpIeNZ@pUcb6;kCXY2t*xS=5>>N7HYhJf&_gdu=?gdUY{t-6s'
    'Xde-P^!Abk$|InPCRFunJ^{~>2`dynpm=bV%0QHdf--QW2LPL@VMQW@Fhjr#`V5m}9gF6<=jG_P=mJj!S|P<A8Y_^kx4fQ1nRc(k'
    'ADc`qN%~Q>%mf0^(WKXO>dKXzFw}zlev8Sku+9|(`0FRY8n#o}c5e{qRE?7j3o<<ajFdZd%94~k9Ws_f+0(HXW=fxGSC$LCT&MK7'
    'Smcp?EI<t|Uyc*)N{Tg@R-v(qlBo=(*sy$NF-nabReywUF!#V(l33qMZI;_ZuUgab+Sd2iZr>7cuc+Oux8b7!umF4jZ@5}mgOCS^'
    '_IwIO3f`0AJw~TfT&V#Z=LNG;<MpbtNE0s!Gxmt-&dWCqi`f8GC}NGLoGfsZE-LB57i(0VlBqG()fz&Z%Mom&<i%DadMckKYfNFm'
    '!dRtC_yenUp;-aztSt;@FJdXuj{Hu%rkFGaiz-&=|JW#v*b+NQ2f<vg;XCYzwVp)%su(mX6R2=qDg`=iu{TuEdprP`_^wZ0<E5aP'
    'rsxWD5dolOSrq)#w<rtAe5cKrv*NTb;TgQ{?u%o%SndrvofLOgh9Myb<Wb~IYK(yq+KIQ`vG7|Gq3Nu_%#`So@d*MBhLa=S(qyjq'
    'zI{|jQ%f0+UHz?r;~%XOee?V)oz5lgn~UX*67LiUA-nLk%_`@2!Xwuq!<Qug&>*z8$;h+W=y_pT{al!;%}#9sG7#|vSw;y#EEJtN'
    'tnb>vl@Lxpe9M7P%1Wxx#UN#s)so7U^_fi^)ag_%3p!ZI0t5&w2m;vgA38_Gcd7bgdVfUTA0)y~oqB<QRsyWD`%Vdq`#QjeygqRK'
    'zP&?{5#`FftUg;#(s}b}YxXt`CH4rZW3(t{0B73u4pkVf2s$lyzU}%%%G$8_GxA}_7SCiat7gr@Yh$5Go=mXownKmgmKMywK%6Um'
    'j+ZSs%yrJ%h!e%nD!>D0!Kx-a`-#WLA+m<2Z|mcaQky$Uv*hSwE#Bi>ZV+P0l5z<)pyeH4tUdf?Q2Yc(6sI;CiFtGWV04-V8eXo`'
    'd{b&4oDzX3nIb)$viVbRVycf<7Rf@Z5)ILU$%22Ciz5s6TNO2t1smpIR>^k_BynDi(};}N^EBjTjo<O0mm9jFdn`58$#ABAlh9hQ'
    'mTSj8!otnBLH2R31N;+(QDtdCLasy!)Jp7_W>ih)y0h><am|KJO3Z&=84^&D@8KV@@{X)fvAii*ICTP*3na2QQx|oTfl}TiN;#~}'
    'jwUT%8T7HNP^xO_RWGC<+}U$fnREB-qWH?CY503$aU+uAxRiFfQ1+!CYqEpJ(lbg?rWXOS!j!I{Qoo_VPb_zuUbME_2ZJDV+ehS!'
    '!C2mnQoG|E)<BY{TIW#(S1wU1#uZ;llM%g)=4p=Kb&^AJ&R^`LX-8<%!}g*N(u4q272#*l7w}b|z9~L@Ec8u{Jz_89JaMJl-8t<%'
    '&ApKGgq6}$=P5cT&kc1&Zq@_?VP%eEIU=qBv*gwa!;KsyuGjG(m*aYoObDx^z2PjF&|ac4&6q!}NT?Vhf~Vj~3&TsMO``ot?}4^W'
    'RHY{>w3{AdcpnA<P9Q*qynz1{+(2lt%oGy!e1{PvlCooL65K?a#q=T|N<UtTdM<^td`e*;wzu^cCn=+w<Itl_*fG7A?hgr_pXzXv'
    'yl&QnsV(g7zIv=}y{O-;P)3Xt*Zmh3GqmP-O=e-rq}htoM>(ve3ap<;`e&rRw=k4{#hE@22D>b@+(aqo#J0-Cmd|)Ss%bo*djMCR'
    'ol9#L>=Dq|Ksu?*qQrGo*2PZ2o1rY~V6V-~cJYTXxLTw2&E!_BWo<&<$xD#Uz}b;dr?PcZ1`sa}#r)WU?4^rqdu$`jsj%%yD<bd|'
    '{wui`NrOkSL-tmAvII3uw9ZpbRo9+?s`5!$!W$2KPy{*Mb$cP*H8s*pe5)D0pjlFePNRNe59pEw`#Yx=lP~Gw#gy*4N9sad>hw-p'
    ';djp_X$Z+q7nzJi^5YO^Ov2d&L};UQp??UZX!czHP!y!c?nIGBLs+a4ym8XAhgUJ-PX;O)-_8P1;h)!M7@|FZSZ~nXc6<P*`dh{q'
    '7)4Ia05Y^#TZVq9oRzn#R?5c_6GQ?rAp!Ad(K7IT7v-br4AhCQt?%}F#AM6nV2FSlOy!1N7_DTxP6u<WWI8q!3Bs~~HxLkR;3)#Y'
    'h9>xD076vT?Kv&Hd~^U4y>5q29sVp=Dhkq~wX!C|NN_xF+u?4V!b!?y>eaV>;BfG=V%2c8iZyLrys&j{W@c+<W~O2_gmr6V3iVU-'
    'ZFfT)O`mQ>&09^O=NwqFS*0F&x4fp^aaO5Sx#SOOl$`~W@#8hExmwHJaYMS`*h5q(1(;|Y%b0otKi<IY4d@b<d?XF*Q`u7nnXTpc'
    'w{3q9jRoayD`(;=7^@!Gn6%_=r_8Zi0({*TPMh3P4QWrWpq)^9Lx<Ll<&~>9uWzkgd1JL<t(OQtVdkZv>AQVgLy4VYrOm2!Z*^(w'
    '?#l9wo41x$@ht6zUFA4PuPlzeazT7ByMp&etIIfnU68O@OacX>bF}J&Hxb9t=7^_gYm4WQ0$PQSRUYnt?|atw;S5qOg~0mp?OT*d'
    'f=t3{vbzoyDGbPPOxKL?(f*MIAPwz9Ajo0>$FC<ZV<b0LeavZbHWuLuNxL`_EHxg*UAP&(fo=xYErT3C!gXqqYj|S~gbi?23olgB'
    '9wt4uNz*{$y~$9Jv<Db$bcrTu3th5B!lsva8|1tlox*W~K+E@?2!9<y<z|b!-)xni+Qq^<8TXZ(nSU-Ga_Y$A*D>!8YtjY>MBJ)u'
    'ut$hNnnDXSw3xspjAEH`3cCU5mpumy98c~l9%Eb|7mQL)S>i7V=o>An0h>@uGFXJIJ9w7w%SQ=oD;Zm{K?$`lgKHzAWT44y9|`Ng'
    '%@)xm(&*7#6}f#Z`rF`mh-u`8?TEAq$LvIk`&#HL!Z3#6KKvkI91~t1<0$exHPOjq=v{~ZUPWmO=poDup0A|i6%2D~QrjO}muT#I'
    '$7zSwJMUQWmy7(;M_!kF`xDtU^!n*{qUSc*&~)>kVOk@zr4BhZNSS)vvb-*9w=B(Yw`g3d#Ij4fa}-1@5h7;A1B^lqDC7Ov#gTF7'
    '7iCM2OZ#RXCT1|r(0OWWyP=<MfERzJVJ}`F^bdTyKc$)1`Hu_>J9bWfv~pUbRKoSu_q~4bHF&e6O@w)xHLTa`G?lcNI*|t<xs2!J'
    'D#)HC9gOL(+G1=LekQaZrzNAbH5v3#8IOlQ7w5+dP}$K%SX-W=i>|^SrsyJLH(|Dg<{Utn#rMUyWn{kwlBh=wW}1sry`qpZIlK&n'
    'O2vWAKNtIY`k))hQHBjZGQc9NN2jvM8-g|_Fw+YwJ&6&*Mo+ff%$Z0le4b%GC5v2|PC~(CxGzlfg^9i}(Z3ufdZE)4M*6SLNMD%e'
    '3-f%^JYU%53%h)lT|O&&$i53Fgk-)QypNunL4@w*i;L`kiya>X)BVl>Xl>q={l1NH?9{0TY^8y}bMC#%HH-S`7SjPz5q8Qc$-u*u'
    'oqam-PT+O+o$}UJ%k?ppZzY-DnWqYp$~w)qT-i)!_1hkR;z>f}AiVDSStD0v766di!s-5C8(4d(B62$~i>`>$pkKi`ZaN@)G^Fy_'
    '+#U4xR^gbv$tM0=Zr6o1ygoCN&KMdv{yt`U8d_ZR`uyx`XDOxXA>|${P1}7JwycEdJsZ>09V9lpUJy3U0%5~*heni6xchc?BRqA9'
    'tcBTE7r)_nz#po2ozSk!t$NNlVEV*MgbfKQ(zly?_Kw3j-m@}QPJt%64=iy?Kq0XsQz&=CyQ!|%8g!hg)ccmhd<5tpHe<TyQC*2X'
    '{cY`F%sSpX<U2Eg(`nZR{gxdf9Rz7a<eadAJ-5>VjRv<EZ;$v`yWYCev0cylk-P0QQR*$rG{hB^uDG6_6lb3frWyv@#}uMBPIYl%'
    'ZmxcQD&=QL4#w-t7_8;&H+bi9NE{k-i5<eST=b0Com%MIy@0YoA}E3TAZ_O^l%1q&yFH-osYQsvfeYZsc#b)ZAsjF(gFonFBolVM'
    '<oi53_nqD7jJ%a2!xrvecksrk(`&j}Q2X09$hu4kryn@swhyxoY9Ii6IJ>_;Uq4%)F)cyw*R^}T$LN&PfuJ-kcj@ovF4W;aIW37L'
    'P}A9qFzDIYacyfYuN$?0&Dh+)AF0cQtZCbW(ChmS-W2wE@EMr*T;9?9mhA+bmbn=qjNgTwNN_|gDU>X@<Y&s&aqVXL?iy%DORGz3'
    'tDxXua)vjSuiTQ4sun!Bv2x}1(woaGKa@{5O&O-6fhmL4azDHa;)_FRl<<ky*1uI*XKi|OK06WJ^1ZdY_tv&R&%1qvXGb9{C{u)J'
    'w!}X~ofk^Tg?i6c2gD(K0K_|>7D#qUE$p~J>r1h@Pi1_0ZTZep{DZOx8x5_Bt>G_OR*k<!<<s!bs8CwgC)4|I>*np7v`|o!?StEB'
    'Oaf60|FjPq*6bX}O0skpKcNTArsx5-fG4WX81>hykzAO;n>>d%WNnjkAn@gHCeQBr(v2(kZsA_sy1ukRph*a@R1gCsJS@_IsntbQ'
    'lm8jzddEcNsu?N!$U(KX|3c+CKE({_l(7B7SP$68c=Lb8?DMJY=UKQpQLtEX7+$u+AWMV&h@A*L>Pvq@jG~vx@XG%us^VZg6(^jj'
    'a?KIG#;Y~VM(?{T%Rjm)0aucuF(I2)Zl%QaR`9PKSze_i>Z=gqiy|t7epIPs9KO-<RGEIF)2ZfTKAW<;+Y22Ith#207!N?@R77gN'
    'ST>I6XH;=kIShRV-JmEp#hidKaG}+YM|WF+<$-R23I;Tb>d|oO^U&UNdTjDQ1qAk_HE4!b(07_-BE&X#me<rgEPDqfuuv7v!AL#8'
    '{6XN*01QapQ42bBS{UvGq`<;l&TvTBewal*M3IwgSJtlFT7E<2l3Y4$b_Oly(p`lz(XLzXsO?*<#vr@CNjWDICJL=O&pLy?#EB<s'
    'UVjkO&ezVDs&W@f*XRw9<UwGauj89&L)c!T?S`}wSFQNC0fqvG=8;$FopEeyw3#%o$O=Mg;+zVzcA@5Vd#*k@ym;g8nsvci<`>b>'
    '!alAh$^AjpglRHGkb}SgwF~HMQ*TnEq-H298p#>%0O{|!wR5#W2UJ6SaC%{#v+ju(IWv@F0M404xJ!@6&rQ`<l9R&}pfD^@aBWyD'
    'w*-UUria;+5`B?J`sv=+#N+XkimE!vSz+qZ+S&SS3S?O5$$}TzAlpnB#&TE?Q(?AMu3|cGOfvO$-P?YEk&DTU98n3ax9bkjxN=1D'
    '>caY2j*es{y+}&p{&t<oTDek(f4lGx>|l8o{;?0sz@)XYw#o7_&Ho^Z;t5HOi{+%Y2EKV{81w9mK4zjn#y{yrqu#DF@fOpX5!0%l'
    'kA|43pG%nRlVQ6$r&!WJOu%(}Kmjiarjg!&#j)FU4=qWK+OG5v=n%tVyRZh1nn;<Uku%)w01c;%EQ;_`;UtSJOu|Pmd^AlgToq6o'
    'ps}DhV!wII>$+h`Kb(GGxnVtBJHzg~TO?~}dxH?gEPHhhdBBNI1kZ?dGEjfyItMB)BnIc?dUx%BXQB8f{My>30%VfOa;dE?wk!cI'
    'v@&Dfn#^7rme|BNznYhxfGvrbfns6O6)A#PGOG#{g46R6oF<i$?xHg!*acK(ndRp7K$&BMK_9;l@34HD-Lm^3NifSKPpPtj7MAMh'
    'qtjFl5uGcLi~JI`@CLo`+b#S&gJffnlEw-*B$(9au>4F?D5=lE@SReM;c4>6X3|&|asSjSjRz;*jq>Bu1cC%y=x{CKCgq4>-i@DD'
    'EzCh8Ws=$QWfOT=Fke-4I^{hD>&*1ui%lqBZftBEyjnZ|4(;JNe6apn?e)!fHa1$rx$3A=fhV<hUa3rD4$vSh(?n9~m(rgVbU^<m'
    'jD-8Le*VHHex|;$QQL%(-|^sEdE-YRa+Fnb(z+x@ty!Ft+soINZebEiqpXl)F!<_3pVCu^KBiSxQXb%!TktV&R!QG1gKQM++I>uO'
    '#!c#j9$ua(XUigL^D@Vx_md11?N{blvdJXF#kMbVM6J~%gMPh|p@zJLfS3>vGn|_!rj+@VbS?N6##R9U!{+XlPN#fzWou=r5@k8W'
    'OqbpD+08Qo)STvUdSjzMyfvC0Fy-Ed4uRwJFn1sPNZ(ozL>#T%*lx2Pblj#>o~c@MGnLa^W(fw{LFk5q(7Ec{%{?dl5g=0{xj4lg'
    'XF^B|6iiS@$!QQCz5}!wW=P-wNxLg8o`MbYMZ^e1{LOW2BLKCj5<>6O?Ligyi7~$Xs8q5p!=DYSJI@z6r?S9+hirwiM^gb+3(d{2'
    'WsVkkM=#JR*Rbque00vbh4BMe6$L<rB52iut)Hu(x2_%eZU=TC_O6e{J{+WOUFjUyM}dXcV|yr~+kK41p)ZaN<daidqe`#ItlJ{K'
    'HF=sk4kp9I*)CW!^YpWM<VQc)6p25xUBv}noAA0c2Cor5Cfv@=$Eu-uI+3UN+%mCROcJ|%&@1!Yh0ciwfX@s3+|-Uj^zaOx3Y=Ri'
    '8D}n7i*sT)CmDQzMfd6Tjg7&~xtW<7{d?oa<}~Aea~F^w27mR{`6xjwx1O1srPedAEyY^X%v5`t3;asP4w<o&V%tf8tn%MY$L*AP'
    't<$hauhK%NX<J?u>-?TIQ@;qm2(yEJ#|`lS2d_@6WW`s-y(pPp7kkWB@=z!p9gp$d=uca2<6V9#g{pk56;wDqyF(haYFUb6(90=b'
    'F5(GZefD}CDHCCKWw%G_dLX`0!8>o-fbu)BDDor)EOs=#qscH9Tw9<=u)y!J;o(DzL-@9xDu||43uD(XjrO(!OvhQWo4cwE8iwKo'
    'nI+!Zu(`X}x3!{a;#Nsci8Tt_z0&XNb=s2gaXt_-CvOl!sudtN6ov~_jKuJpEvE-u=ja-&z{wlm9>D%(k1itaat4Uv@H2+M=*1;0'
    'Pb#X@;cw1~kT>i;w8|OO4xnwgYPX%MAUNOi@k%Ag<VXE*l|*yc$zI|oiTt~^`uhg~-pq8Ac2E^+!SW#N4?;2H9VgV4g{nodn+`wA'
    'n?H}6w}O7Zb9B{rTX;*6FkxAs?rkRs>>Ve_8$K4OmGOnED>tvd0jkFGoz=CKD>v_~A#T{@A@X^VtQ}Sp91BlDh)huvSom%wesRU2'
    'm<ZX`DBkEZA6s(JR6+0_MQ)T1YlsFlw3*i27KVVIn?obB{v0n;;+reiZ{NJ5y+p+JeD`h22#*b}!m+@5Jn(WW01(6DEjrP$yx<un'
    'C`Bwi?>nH|_^q#@>Ylwh1=;yFlAVIa6g1{J&=_NhOP<xrl{e9Zef-DchsR$YKR)^8@nZ}AcyjXI$@}of$-Bo-tm989;_ET~d;EcQ'
    '{L%4eC%?5YrVCr0{3@|oDg+Q6ZC*;t9Q5{jpyiNvh%Y1lV0HP9FvPj-BP<z;mn`khRsbC_&aJAR01XS>w+0k2_HW0Z(S&hUpIb1~'
    'hbQmB)IU4<)$s=>zkpxwA3rHYo7|Gay<R_06<&KgPRHBX0$SLydjwLvnR)zAFx;O38Xv&$kB+}MeuzUqfnk5$uulH><4@@$k51kN'
    '_^jT(jk{y&f`EDV<fqX5{ga>K+!R!gA5x$H0qsA6|9)}uD+{`Rh;5+jW0?6P`uDeZ6_nC>Y;l|*tobM2fFh#o9+7Z35-<f&Z+mdI'
    '{JQlfrRsy1H!(xl4ha2L--Eqi^|Wb+LETyn{Xvrrx4WLV2j|pl9YukMRkTO$;tkC@OjGF%TY#776I)rkQKHCFFJ)(n$<4aQw9^SN'
    '9SPk#2^vaMnJ3?*_8{RLjr1ma&yhyeZKn(y*XmHmyBuq9Ng!BB?lgNPi7XuP-vB;LJOEP{h56Xh!8i!WfOBk!sV?Y~UEi$AY2pMy'
    'OVjB3(ClDJTRb=q3<gV;x4MxTrYndd-b}+IucaA~S@@&u5EWyBF+OWBT{J?8;jk`DU5qf#YpaU|)v+vK8Gcmc3tAjMR{iB4u~IT}'
    'M1!41nRKu+;sVYlQbJ4OUXt7b&o7Zis<s3a(qspxFL0c&Xdn2P=p(nZVMTjAZ>YAz(?P_B=}3H8$LVciWfm+MROZQ|!AK2zIZcVg'
    'JNUh&h2{d4_&uE2PnhPMykE88=s!AnuS$pf__NE3DtwM)@-w8VpTO}JFa8rwIFXa%&#C`=NF78oBoaRZy73WHf#XM)ONe)dMOpv`'
    'Z4nBdrd5cSKm!#iSs{c&^1+m(ZmrqDUPB`tKre`VoQh`Po$3Y>|8k{b+8TLAA{6JbLNByC%&QyL`5EP`F5&5~(T`HPpic5y&s22U'
    's7p|;L>3ezIdItd^#Czke>)s$Z@ckVmPodDFW|eS?CHf{H(SiWu`7xwHcq*ZGmQl@$EEy&^A?=<<>tIvmNv<X3ts#Z@M6wpS8(Kl'
    'BY*82*{Boa|FCVWoY=C~b{)=WxwN`;Yw6mW^*!sx%JOZ@v51$Rf>NbYsrNiggNp^UY`0e~1$#9P+b9{pE<RG`1ECvW;7gQDNQS7C'
    'a04rK5ha58lCEm$C-Xd-7*dCk>{$3Z0OlXqZD0x%DY%7J?5%q%w}hv(R88ipOw3nvi4V{vzAlqvIEQw(-@#k)-Rb>VJWTi^(9>ol'
    'p3ly`R-b|Y%qE}D(Bt#T#}{6&&z(P47ynM{@75cQ+0ED!B%zJ|!QZ}qwmy6DTzzi#Lj5fFY14EM>qmUW4;{Dzzf%HQ&U+wsBxUF?'
    '4*>eUgD&U*fPWiZ$;%@6%fj0iutnQ;O9j-FlI)pJK>jz>{NwWmNYKa0797yl-xRsOm)m97z6nr3a3wf5{U{@86s9KmADPD{kQimu'
    'Lu(szy|OhJV;(XQIr@}}?L_}}?<gWD-4+JeMj>h$(7@C!)p+RHO#N(CJ1TJGuy}p#hf6=1ojZH(JPS;;G|HPL%XDuiYjY|%b%Pyb'
    '-|JEcC^54xsqpe@L?%nCKUozq$)Yg@TN|71I-QP(@xrN~S2&?T-?8C@s;hBTYq{_AuH394mjLk?tM}qvxHl-a*rMRNoFf}oHVTsV'
    'vXiu=FX;tPwA3diC1~-FbAT!hSqBP16fULh6hy8daudjJf(|u_#NEBOM#;SZijkX1__N@}z4#t#*ISTIp*XCfwgt7)0`AjCLzFO4'
    '`i_{x@@n=ZrpapqGl2~h3kd1MmDC~e_T<&yj2Vw3&8L{oZCF0Y8{r@j>pnMgc0w90^4-EI0Hl|fn=okb2yy59%pC1D1#Slx5U*Xn'
    ';hRsh8L~rKf;CbA?(QL6#2RFxccO@tWWop&QBq^FP4Wjli6*{%u;upp13-AR;N^hZkAn`D9Br=8SmmHcwvIGc;uXVx3+b;%{>&JH'
    'WwQ1H+rM6Hr&v25c$&N<NvQ_{%j;R<Myy~PocJ_odYGIH2zmf|HeX?II#jL)BQ-z(V;67Ec_`(d2ZL!yFiCsgX(cynJi-_Z2ik_{'
    'w>KrjOW*5@co+h_27)AoZ`cztMiimawgyAp1hM_J&iHoD&CD3U^0X%?!J{v#(_=CXrSSUHz)OCv8eJTT>Nib2cjBO~;>wxnw<4c<'
    '$+@G(kfEflQ)X74>`20Dy@P;Ke{i*PO6en#@X#rwE3tvK4a`UIC$htiJ#`c;?V*kkI%k00@Q|^ncT<@*?g(57l&>>+_1x4^4Q;yo'
    'yFe+kV`WXsQsfr$DvwHK&gk*H@o4a{hztmc_^`6LL1JLJ&dG*mN>oL`c?@@!Q!YmmtC-h3C%MibUoGEmhtJ5gs}?#|+JGJn&DNa8'
    'EBQ^pMEK(U#PBW}@uy!I(u|mGx~<VPBg6fy`L|s^!1>2!KEQZVnke@sgEkqaF)7mL<evKI_#xSy)01RS2xQ5qBV+Ir<giI?K7-Ix'
    '1g4TDv<RRO&)UNBDJ8=+M_O$fiB)A`mQFaJ($gcbiSPga?Okni+eVW9?q7j;Qw1O<A&Qn|TV5tBTau-f^<s%moG4lbB0vc?3D5*7'
    'nO1nU+5NCzuIm2E?uWaotE;=;5dWj=r+Wr(d=cq5+1yn&wH5))^vrbk^mNbkbSoU8@y#~_w{1<t6}>S}r^`g|3^~)1%@4kY5%XD_'
    'Y=dNn6dPY{Zys$L0j44j400s5zi=|O6-t(6shLAe$u&i20B3%(JnQ2D9KumkkXJNc!gA1IAsQm39?^A9eYu4U05!urZ2KfwjVn2;'
    'G};lY-=^F1sel13r3o91Pb^Q?)ngqC(<yJ3oJg)YV}0NSe%SO+S%`Mr*9cUAP)?DdPL6On2Kgu)bDFxyG5pb|I?Aa?Pu${KvF+02'
    '#tX1h!A!6MXj(Y^LMyXnRY6Wo%Jo-}TwvMj!tpR;cx0C*o(c*nb@h3Ug3>Wef;n9{5*UO5|A^8NS_diH{w(pxLCdGhN9j~5AoX~^'
    'n^P5&?xPVH4E7W|A&eRb43-8BAIGZj+(cV2!!xEF<;PLSXPZ=2JEKW~o5jT1Itt$;?*14f5OZhV0sLlw|Dp!?#7jWkpzF8UHG1Y9'
    'Afd}Sf;Hk2CDmMG6|6HLM1(#msYY8uU(Q2><^Z@OnfOGGLcgRnk=6^|kyQ4>baVZRFa8PQr9*Y}$HLhz`+8g(uLj<^{}t!BAwfX>'
    '1Q`*1hl6*TX(J_ch5uokHaebh$1wLdzdGLCdG-vRA1)8XolYt0j)U<JElc$0bLUE>-@#Ej8n+dJbhf;S!{R)H3yq7){Dg6lslweo'
    'n?5vjY1Y`#f$3wLbWhcuD^~1p-1h&C+Zt56M3j3g`G)z&uY&ESZpG((f5sFaT$91!L-WE%wga#6DmrsS(9<vW<9LO0GkV1j^tX)X'
    'q{3Fj`JXD))$;OkdHHU=va+^(f2~q+DwWDNVC+8h7g{Km5x)tkp_Fz&y*NK-ifCZ76dY(&eD9Q$qNr!3X|{|d4&*z1uZ_dceAlmi'
    'dfgwDE|=+Vv*%Ow?T*{D5D2|`ZxtirLsi?6Ekf%%6n8$o2I5BF*^U>S;~uSf;lDNQ(Rb6>@j@<`sPh=ke}Fq8xRet#*^pV%F_+bS'
    '5-hoXuMD3hGmDE7u7S~a>VL>PPV^OH8QrAtP+LwADuo6LR0P7MRwX?wu_GBN&r3w)7ztszP=h#HrKB@vA3Vo#E~a!N2|cjne7Zzs'
    'DyGfOKJKs`xt_Q$v9&6z|C4laU#TqHzxWU)<62J9etq4(n5#$CqIvu4?$KmV2Wqq75yR6oVM(}6ruQ@Uvb2_GAG-V|*M5_0Kf7GB'
    '+HNc>J$}flU4b*Hxy)X-zlpuy#NN*;_KK!%tnNVLbY^xsGi0*j?K)(H**qpmc6U<l7?tIU%j}ajJH5;ijvfX&?bYJ}`;Sj54mr#z'
    'YbK@F;&fCmLX~lP2RC<pZ@t;{V<i6(5jtMQkN3C_J0M!roen#G9dw@sXHNirdMR~^f}7fVdi;f=<Iz}t&FI9gH>YroZ!UM};#v!$'
    'AN^k^Q93zBw{DS@*5GWdSgFj}@fp^#x7p#x_$+`IRS@qSCRfZk_haZ6qA*PVUkZ^H^4EiI9*`HtOI<nTix-F3le_WQGvtGLbyq&$'
    '1b<l^b}{V2v?vSnz*_HiIle&#8gY1g0a&?vR5OYtd+i{xKAlZSS@67=8_t(2#Vjl{Mr{};rudd3Y2|~{5<M@Ezo<B?E9%v9Mcye-'
    'RaI(EB%?X)w5q_Z3b^}KXL(h>tIE5F)uf5)O6FBHd9_Hh57EMdLbDGaILpbqd&#?d%MJ#eX}Mat3%}guyXnihnx>l7m1G!q=k4;e'
    'bTu<t%D5q)xSoeC{}QgV#HVmdPPxNQej|q9@!*W)gO#g*9Mav(mBKdMjSP6+j?Ucnm#ZJl$hS3wOvg;*CR$qq?xb6*b9d_ojGTa|'
    'm1Txqy{m{!&)(SsX|Jl^Rr#4&W=@*lZM9kgxN@3O(#~&+&Scp6Xf!`E@*(AZy6j4>b_OvAo^R^zrB2c<w-dC7I&k2$FyS+?fN*dE'
    'hRv3hG=O)4A70^8+$_eqX^7QKE31eGnXuvn_=I&7nc9cBTK?yfPlXhe4f{+g`-1m<&%H{$k>(_uiV4XU%8R3CkLIq${w2ys1_FdC'
    'qXR{!j+xYK!v29z-9<0DVkmk!Co8a0D%?k)XSwrX;LZmcTr+<B?;ro2Z_EGr{h#sc{a<ju`^W#BkE*y4j(YEZFzsAm#E(HVy^p~T'
    'X@`;k7#={P>xg!^p857@p?L<ilC-;i)Qs8^09E`aP3Cng*C@To6|d>yYo@)3lruh<PzYi0KR^E0kN<(ov>@8w-~Wx1!~OmJU*7-g'
    '`ybx_oALgK`DmuyMCYH3#=IP9rl`e+1%lKX-+wQ-bL03b>UsJ(_T3(_u6n|)TYCXP`LPiB{s$z_Lu>?k!KgG4g8_G%F)0?E1P0%G'
    'e*aeh`uWhCWlcN1*~`vnN+|p4uK%NtDn^rwFu2M^Gm$ArKRFn2vI+O6Z@)eH{@ZU)KV3S9FWCZUP+nJRX=2mP0(|??q7p-60oRZO'
    '+!wgEldRc*s#k1dbZV@r!$>g$E%|&6$+Kq6)w1&Rb66l-awL3mx<JQ4*iVvv>!<}ZJ<@k@t+6aWq=kdwf0F1T{LV=i?YWjjt|KV0'
    '?O$f{tr>_hLNo6l@BfPQmMph0VSfAvM@ISE2d_Op!&I9xvF4vtA6bVH*4|rx**MxfK0Mez-fTSny3Tti)dpD&`2WY9?;Om#ei6ia'
    'd!#oAV<QOTz*9*hkt(PuffM4$U}vNd-b+feLi~$?-jvcPbmrsFeDLm@b-OgIw^rx2e9T3#<C?LK>Fs;JKVqWRhh1N1H7P2ApCgX@'
    'd~;p^w0zdV78FtAY(;cLUw@*=NEQU{)}uwa-C_?hiC(0<B~n-SBR}p^=l#^#9SNeaWj`LVer99IL7Mocruy%(WEJ5~*b7KcL56^H'
    'qFz9>l#~y&LdoM|0?tt5vd}RRaOR6pjt7X7lgp|C+q4%DKxycZMTR$87`HwD4T893wjLFJN(&LnNX}xw5??s-R9Xl^ayBC%)Fbu@'
    'CMQx@3_70%wl#2hLR_3A-N$0!+;hH^JHBOpW6h-{;{{^0Bdk26<E7hX=U6YD<t5|lB53<y05?ExRxSv&RO?afv|WF8>@3u@$mcb~'
    'YG^nTMJz%DR~#jtxy{!LPf|Uv6eJvq*$Ff&9JI3nY@yl8hi$l&Gz}WZe@YaZ{A;DNEY{v=5n7H)1|-}EAS}6n)E~rh^(S-o2(G+W'
    'sV>%W5J18Eyk^|3RA7y&7r!@1?Xnl9DSCz5lD%j+|7K-cxhNQu{E$803wk0U!Pe>oWMS#}A@XrC37I%&UJSz5B$r+UVgJE;ujdZQ'
    'XsRK+(qglZ*08f-pUsWRqXn0l*oi{RWPfTiSxz4<u%(a!Az_0&pB4{m&3HUO;_h+p)Hw(sqq$QP3@O!OQBDEp3ZTy?sI7L64JWgc'
    's2lT{1OD5l?|a00aq!MJ+K6`k0h}j7iP=H|%JJ_-WsUuTOb~iWyuU>$CJY@$kHxu4OCZvLs+ASkk-0bb7Nw=uDadAA=X+Hm+tgBi'
    'V)B<VU%4_*7oYB|OfnN_9n(@n`NF`;U}$be1V6H|g)FgMT3GfO3K69R5s=YhGFbQm4p!N*=e~}p+t;Jgg4h_@KNq{1i!&$5@Sh-`'
    'Obr4Ftwld$mmJdkl6aPhnzq0w<{vRuh0(2B&kmmKHXd(o9UN`4s{sz*8{*RuFZ}_AT)c#LM89kEQe5=mc2!+<=s&Y`LsO>WV0P8g'
    '`>Q?wJczN!5_UVUXoC07vn?%^`A=C|aQf%(Zf*tcPv^a$KV;{;3-{h~wY>N4`Kvn*cHiE8xwBF^=)73pTzwv0+<WlN-hSNQ-`~3m'
    't6|H#`{t{-<=+oC_K)BEasQnkuY|8I-mR{0U-gc+4_d9`XIC#@tPams?yo#waijBE?dINi{w4LJ4*!muiXtT&&1rOdZ>K&F=q^$Y'
    'ht0r`nIyy{K{H?%M!Ycp<$?3ishFb?fyxuJP%=kNsdQ88b5k?h6p=IgSmvhYqUvO_?$$SkNA<5?K8U~S?7mzNULS669}k<Wcb^;`'
    'Zr1mj{o$+KtwFc>WcA?jvzPU|Z{z)n|IppK-?`J-c{%8Bebs&Oa^QRY=<4bH;Mu{uZsqm!dC0m5UB?JJ(o=1HtG;=(*i5TB)e2Hh'
    '|BO>jn)vX!_M&=cW50Lj>iAVRt{*R5ee?9|?Kk(IHm_QP<IZlddl?;G?pCYsuIlZhix&@<hX-M>zw+kj=-%$d&a2Cyb$=LNEqU*j'
    'E_OSujqS=&5U;rFzxuhh>Qt8(pKPkuFEZPtt)DR6f~$>h-kevSuRrabKRj|T?`^MymA%!K=H1Tgqk9jVe_XwK-o11G$x66WIgdM='
    'Z(ZMWzkarVu(IOUSJwNFA78yXs|QaH_uBpHo>!?q+<y4S=fA{syVY#Facmso+(8uR&9_KuPgJni7~t*Ox9ixemHTJ7$r{B$Kk5zj'
    'W-WpN;&N*f_1JP_w_1lP68t~Fs^CVfRxf(zhc)!oR_#9Fpybk!Y=&VgMzsF#jr}O}`I9)Zd+G~8r8OT{!M#Q=iuxAEU_f+i9C>gp'
    '+bDm|&jOkYaO^eyr6b{4_9?6kekZE?$sy;tyYej34e{G*G+II1Z#3+*l7raHVgHmtW4}erR-hyZRa<KbF;D=##5XG`Su#FLek*vf'
    'y_Tb3*KNLb&p84JsxKL)dLvH2xw140{V|BS$5sIvpS$#iYZIA-sspA2x98Z>kdWlCfkb{5P4CDfeXC{;`mOQ<I52Y*2kaD?WN*|A'
    '72`T;N9X3+R7O<0#2C+58K3#iunvw@zN9Y^Pm+JzlOf_}LJ$swMS5;P^vm!u3_;bSEYmVB!M3f4WPn38hz-kSeto!J-*!w}@fY~I'
    'f!pI2J_>t5gGB<wO9@n7U^BV6oDxizy`^w0-&001KB?(C#3bmHDnT^VbsPPN+t1)&Y^bf=<}zjhfs2Qob^ts6T7w$V&@xnzw$xzN'
    '@oR(3Bj3u6v1BBfO-n}9_S7#jwo(+(U+EraeC3S{P5{Y~ek`hFYZPQ&69i_RWxfz^B~@!i1^uU5m@+7p8G4!tS3}IyTb@`jIa*ft'
    'IIl{^vh;_en=~Xb0-quft6R8Geo|dK<-0{)A`&JrUZOW%&}y}VGbh9k0F)e;_#8uI5cJ#|8$IMJ>LM19#nv**2F)NwX0Gr_C27>Y'
    'HHFYAF?GaFA~|9$#nGVG^aUH#4Yy}pXNPyPwp^*4e$pE`#ugagxK?<h7e_wg%Ns7jAjBfU;{k5@U^gUmyYWTT&rFM9*lfUAk)=$A'
    'H#%+@wEUPJX=&}}`2yt$!x<riiZV(iZoo7sCXz+JB%ASiWGmj{>&*I#l*@bvrjz<gGSLLn-8zwXr{FDsl5$$(C=}JNPiM?J-N!Pw'
    'ilG@^BrzQn8Gy-*6w=@w(@vRJcO<7r6?&8VHnU6lLndz^N1ECC;Nr24>mDVQ^Q~WQ<T}7bC50h$^v^!i)k=n$SJBNsDGPWsX~21~'
    'HX{y;q<}6Zy|L#UaRK7Yk><K0N50uEh~a?|d|o5H|DHK2WiX=4pU&H}eeB+=2!)=H&{wW_gHGuoL;alry^A#1^0^-(1RViVqO1c='
    '4Cm_Dro?u+#4_Y&m;fwN=~Y1MK-BhA4j4L#*7DjP>KugVNNRXF96~0mKyaAFuwR^g3_(vnDHlZ8+so{ia5C_u!0$-dh-%KKRvgI4'
    '@4L_up-v*k%aBujW8CsN05)TXk)ft#1{{i{gEM>&f`mgYq*Jip^SLUr6?#1MKAaL{=+3Q-62!rr!=aVe!({M9c|q$9$1lzZi(EDI'
    'ELSx*i%SyoSizW9AP10XhSJQTjA~84v|vG1nyo5mDQ>Vc4`~WSt8_i+rwG@xofA!x9;jzgR(wk;_*%kIt!aq+M3>26PPA`TA(8eI'
    'WDhl<yPqkROvs$zO5SF*9-d;}pwo>l3?ErL5k;%v#?2t8ZOMIJWS0#4wW^I+5ZEe|rH@l<Hjq3iqZ0B$hZXOHS3$98l#oWzwegP}'
    '@meN1z+yqP#`Q|Jby9MUDer1Pc{MdvP;JrQ8H$yXOR3pgME3ot&$@uz-*IDucWG~ApuHfDvG<y)A`Ty1gI}}_mopRLzeCC<F^yai'
    ';%3s}zZv+0F`aX=F<2^Cf{Z78Sj*1hq!S6Jc?HXg$a10^1T};%madpIW2e28i`K<%-q;-#q-!dXl7dO6Yg{KsJTdR+rT;cSoD*B7'
    'OJW`u#~p|gg6}MbZbZmTMbmKG=nM&0Ze7GP^k1Jh1l0ZTI4cwKBu%MVL@e9JNvX`@#*6p%i~Zf>@x>^Esocy-n}=>mUv)u;mRwpH'
    'Ep5Ce27&o)?_0jVPXF3DgI${n=tj0%d9<l^CfZJ7HkA@c^B{+<6}Gk0&Q8P>H%whiE<lcBslcx@fu}nSm>D?*T=p8Y0xps@ugL3y'
    'in5ul2;owuQ30HtH41VCQawmDD%hIvxnzj^&f6pWy+H3&b+e}+z>Avkgjs4LcXziRFX4Mb=?mSV>Y2*G4F(v5-629vNM(`?7HX(r'
    'CW-fwu|C;e-+#LK?BJ=>@f0w{N($zQnP%&AJ<mL~lIQWkU8mP*MUG)B^d!fq=3b%<X&n){Mzr3D5K3@6A)_zi$hS0<e$Wx&F^Jg@'
    'bMttw95O2zUm{SSx<*mhp)|1&NSbEj;4BWjfU4?<cqJ8`yQGii0qndNc%rVleBGE65}fs-tJufJnoC2b&&^&G#|DwZr{#LAQCyod'
    'y6|O=FMJ(xkClmj3Yr!@`h%T^a!d*YDT69Cma(%D%cLh<^b+U1Tr;QXPjf4HI|;>y>VA{f^L0X(sj<lYF!cn?W@Au6S_7%4?ro2a'
    '`Iz)sw+&x~BwC-2Vyl8IC!tJB5^-5)?3UOaD)efJ3yVM5jA*E1&F}htmkM-;2ou_dyM^y@7-0~(O+DtHp?eveOLJ%jkxzxw2QeZ!'
    '0yUxAgEROv(rU#bapq{#L~afdrW7PQKHlVv^x>eZ74A#5OYO5XQl^vifUz@;tjB(Hptki3ls!tkk*NVflXggEj%#LoaM7ctxU4HC'
    'NIjetRod8@5%eZrpd5~#&GaM!y%HMZ_&8JpRCBE9^4=G#RR}4`k+uhfFq*$jM!@>vPJ+BiV;|+jY)&#|a)!=aK9E;1YPAyaMld!G'
    'wzj4VH&vm*<^&11q)+O@xQshouRqytY^>Ke(*aPS0K6I3#%5x&^WhGNE7wHmksZHWy#wV43?*hbq(u-0ok2%i%!W>KpuLOZzDwj0'
    '2rFWSW(-bV!z7k)K*EMqBoN`e=XNi&vMnZOLH4E=dd4^}lKaV2Zh}}&Jwz2NZtNdt*b&z(2Im*-4k{|H_884LAR9g@a!r=&u*l(b'
    '7xXxKDJS5`ap{z)!@Cd?vAIZ!`bE(5$`F4;<1A>mbvhsp!;(qb!=j(;E>6EH_k$9ptE5slNH8Iw3we0Rupmsg+q%cp;kZL0jYBRP'
    'N|-4UKISZi)fK|yWzdU4Kov@=25F>_q$=qrScKN^0g4fB&xSd^n1TceB|``x)mgZ8XJfRM-GyUbWM055AU;7n<ut!WvS8$v#}_-r'
    'Ee^d>1Z@Z_)q~t5&dk4(o>DU>u+kM<rW(YO8Ua+xkvZWYEHzDXCkoIW^)B&6bS0MZ6dSn2CWPE_F4#?ZT~}?-2LgW5-c%6wVX)km'
    ')%7+sP^sihw1`+My)9$DJu=46N0d3m{VSfb>9W|mnS!tJ!zz7HrT6r3brCRvSn?XX%|5TCxM$Cc-5_M=ZaGKIflIbst>O>~X=f%G'
    'H$`J7bHX4euenVs<&39*DII<>7)V_k_dQtn9O7Kc>64N{$lGoWJ}}WcyWA{k3Z}c1!9HG`Wnb9(%)uog7&IFU-hz&;Pvf-lIoSYb'
    'n^_K5oz817=vnHdmCv9{BCQ+I>smS}XoSlD(K&AH>>X@ua)a!KZ6OjAychgwCV3@VU0Gp3Y$YRH9A=HPPg2IK`v{ui_J-Je!BKE6'
    ')4>wt8mW4+1!Z&G7tYt4*#Xk^se?QvrGSHT4SV`Nkt!v~(+IOC6=@=Rsbv>zT-B)4yr7X=Jo+gmv|Wv1W$bB5Kd?5X(jde!rPYyL'
    'rIZ?q@=y_qTW%#|s!+jY0NiBw>0)KxjT`M4@!|V68p0>FqTE_!mqx16QZeWyvO{YK(BO@uL6~}H$Z214)<C^bn9KVu%#AKRlySM6'
    '-w&I3cAqeXzRy*}ddqaU*JbJCQo6z}O_bi5?R<5qOH*LHCpp=ouQ(OPp|FH9G<(>^|JK-CTO47zrl)dRsUV&6!&H58XrjPNHqW19'
    'J{2kRl#E?}cow-mkE3_>2HmWSL3S*%2ZpVB-?LP6W3DQ5PL|?MXKo`lL3fdkH?tGZG9^j!tzpL9Ky=9vkkUFg-;^A}IfKOlg|rR5'
    'y7XdRJc(!cx3k_mXQlCwzgT3?@%|CbzFMO}8fBxwNi{l%Bid`Q2UIPoeB@qjq!qTwR@%}<?M!>P)zolRLzXF?E67td?E1CCMDR{2'
    '?Dd9a35n{mQd%=P5kUj@&p8TWyIV80S;5i*mSm5$-;mcdWGMmKkhNfTQ?%gEZU;J|R;|gf@w5*EYR0pHhmjHmlUtZsmlSAR?wHv%'
    'DU;sC!y+ChB9<)z;zeLmnj-iyuK?U4|3RDj;DvY?PY$8KL6ubA6?!4<WLF&q;L8cJ?yL5+JM#_Bl*773N=zl4a>9r`kZKtpIc|;}'
    'iEd?&L2zq0f2w5{4@7ybEu4r#<u>;vc?EV6y{I64l|@iVUgiyglEMd3I@ewnOOx7cnH%uoqL0RP+ZR~&NRdaek#kd5bUQ`lb2kTP'
    'WRSrc#eS}JVxBXrm?QwpOdLFv%RyY0d+cQ-Z7Jh~nM^UGdF9na^zj~%QZt)w7tv-_UW-~@gDxmIqS}<?BpRIzqlR$0J!bK&D<7S#'
    'y*Y*z$F%1fID{a(;2;DU1DFdh*qvsK(7&HCj45cC4_q=g2_hyR|3b|ECkK0bJN3ri=JE0R)6E52%yEET6SGU<1fRoFwvSH`P1ie='
    'Cvi!fa9*nE!jRQR<C_1naYN*&DPxIVj&*ODmKvf^qXB)s(O|F2Mgt2^qoIsS)Fw@)Z^?3G-}+xspRgn'
)


class PatchError(Exception):
    """The current repository cannot safely accept the patch."""


@dataclass(frozen=True)
class Change:
    original: bytes | None
    updated: bytes


def find_root(start: Path | None) -> Path:
    starts = [start.resolve()] if start else [Path.cwd(), Path(__file__).resolve().parent]
    for directory in starts:
        for root in (directory, *directory.parents):
            package = root / 'package.json'
            if package.is_file():
                try:
                    if json.loads(package.read_text(encoding='utf-8')).get('name') == 'promptolog':
                        return root
                except (OSError, ValueError):
                    continue
    raise PatchError('Promptolog repository root not found. Pass --root PATH.')


def safe_path(root: Path, relative: str) -> Path:
    output = root / relative
    if output.resolve() != output or not output.is_relative_to(root):
        raise PatchError(f'Unexpected path or symlink: {relative}')
    return output


def replace_once(relative: str, text: str, old: str, new: str) -> str:
    matches = text.count(old)
    if text.count(new) == 1 and (matches == 0 or old in new):
        return text
    if matches == 1:
        return text.replace(old, new, 1)
    first_change = next((line[2:].strip() for line in difflib.ndiff(old.splitlines(), new.splitlines()) if line.startswith('- ')), old.splitlines()[0].strip())
    raise PatchError(f'{relative}: expected one source match near {first_change[:100]!r}. Found {matches}. Review against the supplied snapshot.')


def plan_audit(root: Path) -> dict[str, Change]:
    """Load the previous patch as a plan without writing into the checkout."""
    archive = safe_path(root, f'patches/{AUDIT_FILE}')
    if archive.is_file():
        return {}
    data = zlib.decompress(base64.b85decode(AUDIT_PAYLOAD))
    if hashlib.sha256(data).hexdigest() != AUDIT_SHA256:
        raise PatchError('Bundled production audit checksum does not match.')
    with tempfile.TemporaryDirectory(prefix='promptolog-audit-') as temporary:
        script = Path(temporary) / AUDIT_FILE
        script.write_bytes(data)
        module = runpy.run_path(str(script))
        try:
            return {key: Change(value.original, value.updated) for key, value in module['build_plan'](root).items()}
        except module['PatchError'] as error:
            raise PatchError(str(error)) from error


def build_plan(root: Path) -> dict[str, Change]:
    plan = plan_audit(root)

    def load(relative: str, optional: bool = False) -> bytes | None:
        if relative in plan:
            return plan[relative].updated
        try:
            return safe_path(root, relative).read_bytes()
        except FileNotFoundError as error:
            if optional:
                return None
            raise PatchError(f'Missing {relative}. Use the original repository checkout.') from error

    def queue(relative: str, before: bytes | None, updated: bytes) -> None:
        if before != updated:
            actual = plan[relative].original if relative in plan else before
            plan[relative] = Change(actual, updated)

    def create(relative: str, updated: bytes) -> None:
        original = load(relative, optional=True)
        if original is not None and original != updated:
            raise PatchError(f'{relative} already exists with different contents.')
        queue(relative, original, updated)

    for relative, replacements in HUNKS.items():
        original = load(relative)
        text = original.decode('utf-8').replace('\r\n', '\n')
        for old, new in replacements:
            text = replace_once(relative, text, old, new)
        queue(relative, original, text.encode('utf-8'))

    for relative, text in NEW_FILES.items():
        create(relative, text.encode('utf-8'))

    manifest_bytes = load('package.json')
    lock_bytes = load('package-lock.json')
    manifest = json.loads(manifest_bytes)
    lock = json.loads(lock_bytes)
    lock_root = lock.get('packages', {}).get('', {})
    current = manifest.get('version')
    if current not in ('1.1.0', RELEASE_VERSION) or lock.get('version') != current or lock_root.get('version') != current:
        raise PatchError('Expected Promptolog 1.1.0 or 1.2.0 with a matching npm lockfile.')
    if any(manifest[k] != lock_root.get(k) for k in ('name', 'dependencies', 'devDependencies', 'engines')):
        raise PatchError('package.json and package-lock.json disagree. Synchronize them before applying.')
    if current != RELEASE_VERSION:
        package_text = manifest_bytes.decode('utf-8').replace(f'"version": "{current}"', f'"version": "{RELEASE_VERSION}"', 1)
        if json.loads(package_text).get('version') != RELEASE_VERSION:
            raise PatchError('Unable to locate the root application version in package.json.')
        queue('package.json', manifest_bytes, package_text.encode('utf-8'))
        lock['version'] = lock_root['version'] = RELEASE_VERSION
        queue('package-lock.json', lock_bytes, (json.dumps(lock, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))

    helpers = runpy.run_path(str(safe_path(root, 'scripts/docs_update.py')))
    changelog = load('CHANGELOG.md')
    text = changelog.decode('utf-8')
    if f'## [{RELEASE_VERSION}]' not in text:
        text = helpers['changelog_add'](text, {
            'Added': [
                'A single home composer with automatic routing, a manual override, role-based examples, and a hypothesis validation preset.',
                'A prompt checklist, a compression diff, placeholder fields, clipboard shortcuts to external chats, and one-off model execution.',
                'Portal-scoped shared folders with reader and editor permissions, plus revision history for editable prompts and templates.',
                'Editable draft answer suggestions for Generator and Optimizer clarification.',
            ],
            'Changed': [
                'Group secondary actions, model explanations and token estimates in accessible disclosure panels.',
                'Stream slow model operations in the app while retaining JSON responses for API clients.',
            ],
        })
        text = helpers['changelog_release'](text, RELEASE_VERSION, PATCH_DATE)
    queue('CHANGELOG.md', changelog, text.encode('utf-8'))

    handoff = load('HANDOFF.md')
    text = helpers['handoff_apply'](
        handoff.decode('utf-8'), PATCH_DATE,
        decisions=[
            'Release 1.2.0 uses a unified home workspace with local routing rules, distinct advanced modes, a four-part checklist and role-based examples. See docs/prompt-workspace.md.',
            'Schema v3 stores team folders, folder-scoped employee roles and prompt revisions. Existing private rows stay in place. Reader and editor actions are authorized against the trusted Gateway portal UUID.',
            'Existing model workloads and one-off execution can negotiate a prompt SSE stream with a working event and heartbeat. The API preserves the JSON form for existing clients.',
        ],
        limitations=[
            'Team access uses explicitly assigned employee IDs. CRM records and automatic organizational department synchronization are outside this release.',
            'Run the staging checks in docs/prompt-workspace.md with real identities, the mobile placement and the configured provider before production deployment.',
        ],
        patches=[f'{PATCH_ID}: release the unified prompt workspace, team library and editable prompt revisions'],
    )
    queue('HANDOFF.md', handoff, text.encode('utf-8'))

    create(f'patches/{PATCH_FILE}', Path(__file__).read_bytes())
    return plan


def show_plan(plan: dict[str, Change], diff: bool) -> None:
    for relative, change in plan.items():
        print(f'{"update" if change.original is not None else "create"}  {relative}')
        if diff:
            if relative in (f'patches/{PATCH_FILE}', f'patches/{AUDIT_FILE}'):
                continue  # Script archives are exact copies of the delivered sources.
            before = (change.original or b'').decode('utf-8').splitlines(True)
            after = change.updated.decode('utf-8').splitlines(True)
            sys.stdout.writelines(difflib.unified_diff(before, after, f'a/{relative}', f'b/{relative}'))


def atomic_write(path: Path, contents: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o644
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        try:
            handle.write(contents)
            handle.close()
            temporary.chmod(mode)
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)


def apply_plan(root: Path, plan: dict[str, Change], backup: bool) -> None:
    for relative, change in plan.items():
        path = safe_path(root, relative)
        current = path.read_bytes() if path.exists() else None
        if current != change.original:
            raise PatchError(f'{relative} changed during patch validation. Run the patch again.')

    if backup:
        for relative, change in plan.items():
            if change.original is None:
                continue
            target = safe_path(root, f'.patch-backup/{PATCH_ID}/{relative}')
            if not target.exists():
                atomic_write(target, change.original)

    written = []
    try:
        for relative, change in plan.items():
            atomic_write(safe_path(root, relative), change.updated)
            written.append(relative)
    except (OSError, PatchError, KeyboardInterrupt):
        for relative in reversed(written):
            path = safe_path(root, relative)
            original = plan[relative].original
            if original is None:
                path.unlink()
            else:
                atomic_write(path, original)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--root', type=Path)
    parser.add_argument('--dry-run', action='store_true', help='validate the entire plan without writing')
    parser.add_argument('--diff', action='store_true', help='show the planned source diffs')
    parser.add_argument('--no-backup', action='store_true')
    parser.add_argument('--commit', action='store_true', help='commit only the files changed by this run')
    args = parser.parse_args()
    if args.dry_run and args.commit:
        parser.error('--commit cannot be used with --dry-run')

    try:
        root = find_root(args.root)
        plan = build_plan(root)
        if not plan:
            print('Nothing to do')
            return 0
        show_plan(plan, args.diff)
        if args.dry_run:
            print(f'Dry run: {len(plan)} files planned.')
            return 0
        if args.commit:
            subprocess.run(['git', 'rev-parse', '--is-inside-work-tree'], cwd=root, check=True, capture_output=True)
        apply_plan(root, plan, not args.no_backup)
        print(f'Applied {PATCH_ID}: {len(plan)} files.')
        if args.commit:
            paths = list(plan)
            subprocess.run(['git', 'add', '--', *paths], cwd=root, check=True)
            subprocess.run(['git', 'commit', '--only', '-m', COMMIT_MESSAGE, '--', *paths], cwd=root, check=True)
        return 0
    except (PatchError, OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f'Patch error: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
