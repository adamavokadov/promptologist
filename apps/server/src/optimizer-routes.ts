import type { FastifyInstance, FastifyRequest } from 'fastify';
import { z } from 'zod';
import { unindexDoc, type Db } from './db.ts';
import type { Identity } from './auth.ts';
import { rateLimit } from './auth.ts';
import { AppError, nowIso } from './util.ts';
import { withPromptStream } from './prompt-stream.ts';
import { suggestAnswers, versionQuery } from './prompt-features.ts';
import { appendPromptVersion, deletePromptVersions, listVersionsForPrompt } from './prompt-versions.ts';
import type { VibeClient } from './vibe.ts';
import { engineChat, engineView, updateEngine } from './engine.ts';
import {
  answerOptimization, compressOptimization, createFolder, getOwned, listFolders, listOptimizations, ownFolder, reindex, rowToOptimization, runOptimization,
} from './optimizer.ts';
import { OPT_LIMITS, answerRequestSchema, engineUpdateSchema, optimizeRequestSchema, promptIdSchema, promptRevisionSchema, OPT_WORKFLOWS } from '../../../shared/src/index.ts';

export interface OptimizerRouteDeps { db: Db; vibe: VibeClient; me: (req: FastifyRequest) => Identity; admin: (req: FastifyRequest) => Identity; fetchImpl?: typeof fetch }

/** Prompt optimizer: engine settings, four workflows, compression, library with folders. All routes are under /api/optimizer. */
export function registerOptimizerRoutes(app: FastifyInstance, d: OptimizerRouteDeps): void {
  const { db, me, admin } = d; const deps = { vibe: d.vibe, fetchImpl: d.fetchImpl };
  const limit = (userId: string) => { const l = rateLimit(`opt:${userId}`, 10, 60_000); if (!l.ok) throw new AppError(429, 'rate_limited', 'Слишком много запросов к оптимизатору', l.retryAfter); };

  // ---- engine settings (read for everyone, write for admins; the key is never returned) ----
  app.get('/api/optimizer/engine', async () => engineView(db));
  app.put('/api/optimizer/engine', async (req) => { admin(req); return updateEngine(db, engineUpdateSchema.parse(req.body)); });
  app.post('/api/optimizer/engine/test', async (req, reply) => {
    const identity = admin(req);
    limit(identity.userId);
    const t0 = Date.now();
    return withPromptStream(req, reply, async () => {
      const r = await engineChat(db, deps, [{ role: 'user', content: 'Reply with the single word: ok' }], { maxTokens: 1024 });
      return { ok: true, latency_ms: Date.now() - t0, provider: r.provider, model: r.model };
    });
  });

  // ---- workflows ----
  app.post('/api/optimizer/run', async (req, reply) => {
    const { userId } = me(req);
    limit(userId);
    const input = optimizeRequestSchema.parse(req.body);
    return withPromptStream(req, reply, () => runOptimization(db, { userId, deps }, input));
  });
  app.post('/api/optimizer/items/:id/answer', async (req, reply) => {
    const { userId } = me(req);
    limit(userId);
    const { id } = promptIdSchema.parse(req.params);
    const input = answerRequestSchema.parse(req.body);
    return withPromptStream(req, reply, () => answerOptimization(db, { userId, deps }, id, input));
  });
  app.post('/api/optimizer/items/:id/compress', async (req, reply) => {
    const { userId } = me(req);
    limit(userId);
    const { id } = promptIdSchema.parse(req.params);
    return withPromptStream(req, reply, () => compressOptimization(db, { userId, deps }, id));
  });

  app.post('/api/optimizer/items/:id/suggest', async (req, reply) => {
    const who = me(req);
    const { id } = promptIdSchema.parse(req.params);
    const item = rowToOptimization(getOwned(db, id, who.userId));
    if (item.status !== 'draft_questions' || !item.clarifying_questions.length) {
      throw new AppError(409, 'not_awaiting_answers', 'Уточнение уже завершено');
    }
    limit(who.userId);
    return withPromptStream(req, reply, () => suggestAnswers(db, deps, item.raw_input, item.clarifying_questions));
  });

  const savedPrompt = (req: FastifyRequest) => {
    const row = getOwned(db, promptIdSchema.parse(req.params).id, me(req).userId);
    if (row.status !== 'ok') throw new AppError(409, 'not_ready', 'Сначала сформируйте промпт');
    return row;
  };
  app.get('/api/optimizer/items/:id/versions', async (req) => {
    const row = savedPrompt(req);
    const source = { id: row.id, body: row.final_prompt, created_at: row.created_at };
    return listVersionsForPrompt(db, 'optimization', source, versionQuery.parse(req.query).before);
  });
  app.put('/api/optimizer/items/:id/prompt', async (req) => {
    const { body, expected_version } = promptRevisionSchema.parse(req.body);
    return db.tx(() => {
      const row = savedPrompt(req);
      appendPromptVersion(db, 'optimization', { id: row.id, body: row.final_prompt, created_at: row.created_at }, body, expected_version);
      if (body === row.final_prompt) return rowToOptimization(row);
      db.run(`UPDATE optimizations SET final_prompt = ?, compressed_prompt = NULL, tokens_before = NULL, tokens_after = NULL,
        initial_score = NULL, optimized_score = NULL, initial_critique = '', changelog = '[]', framework_used = '', updated_at = ? WHERE id = ?`,
        body, nowIso(), row.id);
      const next = savedPrompt(req);
      reindex(db, next);
      return rowToOptimization(next);
    });
  });

  // ---- library ----
  app.get('/api/optimizer/items', async (req) => {
    const id = me(req);
    const q = z.object({ page: z.coerce.number().int().min(1).default(1), q: z.string().max(200).optional(), folder: z.string().max(60).optional(),
      favorites: z.enum(['0', '1']).optional(), workflow: z.enum(OPT_WORKFLOWS).optional() }).parse(req.query);
    return listOptimizations(db, id.userId, { q: q.q, folder: q.folder, favorites: q.favorites === '1', workflow: q.workflow, page: q.page });
  });
  app.get('/api/optimizer/items/:id', async (req) => rowToOptimization(getOwned(db, promptIdSchema.parse(req.params).id, me(req).userId)));
  app.patch('/api/optimizer/items/:id', async (req) => {
    const id = me(req); const row = getOwned(db, promptIdSchema.parse(req.params).id, id.userId);
    const body = z.object({ is_favorite: z.boolean().optional(), folder_id: z.string().max(60).nullable().optional(),
      var_values: z.record(z.string().max(60), z.string().max(OPT_LIMITS.variableValue)).optional(), tags: z.array(z.string().trim().min(1).max(30)).max(8).optional() }).parse(req.body);
    if (body.folder_id != null) ownFolder(db, body.folder_id, id.userId);
    return db.tx(() => {
      if (body.is_favorite !== undefined) db.run('UPDATE optimizations SET is_favorite = ?, favorited_at = ? WHERE id = ?', body.is_favorite ? 1 : 0, body.is_favorite ? nowIso() : null, row.id);
      if (body.folder_id !== undefined) db.run('UPDATE optimizations SET folder_id = ? WHERE id = ?', body.folder_id, row.id);
      if (body.var_values) db.run('UPDATE optimizations SET var_values = ? WHERE id = ?', JSON.stringify(body.var_values), row.id);
      if (body.tags) db.run('UPDATE optimizations SET tags = ? WHERE id = ?', JSON.stringify([...new Set(body.tags)]), row.id);
      db.run('UPDATE optimizations SET updated_at = ? WHERE id = ?', nowIso(), row.id);
      const next = getOwned(db, row.id, id.userId);
      if (body.tags) reindex(db, next);
      return rowToOptimization(next);
    });
  });
  app.delete('/api/optimizer/items/:id', async (req) => {
    const id = me(req); const row = getOwned(db, promptIdSchema.parse(req.params).id, id.userId);
    db.tx(() => {
      db.run('DELETE FROM optimizations WHERE id = ?', row.id);
      unindexDoc(db, 'opt', row.id);
      deletePromptVersions(db, 'optimization', row.id);
    });
    return { ok: true };
  });

  // ---- folders ----
  app.get('/api/optimizer/folders', async (req) => ({ items: listFolders(db, me(req).userId) }));
  app.post('/api/optimizer/folders', async (req) => createFolder(db, me(req).userId, z.object({ name: z.string().max(OPT_LIMITS.folderName * 2) }).parse(req.body).name));
  app.patch('/api/optimizer/folders/:id', async (req) => {
    const id = me(req); const f = ownFolder(db, promptIdSchema.parse(req.params).id, id.userId);
    if (f.default_key) throw new AppError(409, 'folder_protected', 'Стандартную папку нельзя переименовать');
    const name = z.object({ name: z.string().trim().min(1).max(OPT_LIMITS.folderName) }).parse(req.body).name;
    if (db.get('SELECT 1 FROM folders WHERE user_id = ? AND name = ? AND id <> ?', id.userId, name, f.id)) throw new AppError(409, 'folder_exists', 'Папка с таким названием уже есть');
    db.run('UPDATE folders SET name = ? WHERE id = ?', name, f.id);
    return listFolders(db, id.userId).find((x) => x.id === f.id);
  });
  app.delete('/api/optimizer/folders/:id', async (req) => {
    const id = me(req); const f = ownFolder(db, promptIdSchema.parse(req.params).id, id.userId);
    if (f.default_key) throw new AppError(409, 'folder_protected', 'Стандартную папку нельзя удалить');
    db.tx(() => { db.run('UPDATE optimizations SET folder_id = NULL WHERE user_id = ? AND folder_id = ?', id.userId, f.id); db.run('DELETE FROM folders WHERE id = ?', f.id); });
    return { ok: true };
  });
}
