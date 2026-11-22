import type { FastifyInstance, FastifyRequest } from 'fastify';
import { z } from 'zod';
import { unindexDoc, type Db } from './db.ts';
import type { Identity } from './auth.ts';
import { rateLimit } from './auth.ts';
import { AppError, nowIso } from './util.ts';
import type { VibeClient } from './vibe.ts';
import { engineChat, engineView, updateEngine } from './engine.ts';
import {
  answerOptimization, compressOptimization, createFolder, getOwned, listFolders, listOptimizations, ownFolder, reindex, rowToOptimization, runOptimization,
} from './optimizer.ts';
import { OPT_LIMITS, answerRequestSchema, engineUpdateSchema, optimizeRequestSchema, OPT_WORKFLOWS } from '../../../shared/src/index.ts';

export interface OptimizerRouteDeps { db: Db; vibe: VibeClient; me: (req: FastifyRequest) => Identity; admin: (req: FastifyRequest) => Identity; fetchImpl?: typeof fetch }

const paramsSchema = z.object({ id: z.string().min(1).max(60) });

/** Prompt optimizer: engine settings, four workflows, compression, library with folders. All routes are under /api/optimizer. */
export function registerOptimizerRoutes(app: FastifyInstance, d: OptimizerRouteDeps): void {
  const { db, me, admin } = d; const deps = { vibe: d.vibe, fetchImpl: d.fetchImpl };
  const limit = (userId: string) => { const l = rateLimit(`opt:${userId}`, 10, 60_000); if (!l.ok) throw new AppError(429, 'rate_limited', 'Слишком много запросов к оптимизатору', l.retryAfter); };

  // ---- engine settings (read for everyone, write for admins; the key is never returned) ----
  app.get('/api/optimizer/engine', async () => engineView(db));
  app.put('/api/optimizer/engine', async (req) => { admin(req); return updateEngine(db, engineUpdateSchema.parse(req.body)); });
  app.post('/api/optimizer/engine/test', async (req) => {
    const identity = admin(req);
    limit(identity.userId);
    const t0 = Date.now();
    const r = await engineChat(db, deps, [{ role: 'user', content: 'Reply with the single word: ok' }], { maxTokens: 1024 });
    return { ok: true, latency_ms: Date.now() - t0, provider: r.provider, model: r.model };
  });

  // ---- workflows ----
  app.post('/api/optimizer/run', async (req) => { const id = me(req); limit(id.userId); return runOptimization(db, { userId: id.userId, deps }, optimizeRequestSchema.parse(req.body)); });
  app.post('/api/optimizer/items/:id/answer', async (req) => { const id = me(req); limit(id.userId); return answerOptimization(db, { userId: id.userId, deps }, paramsSchema.parse(req.params).id, answerRequestSchema.parse(req.body)); });
  app.post('/api/optimizer/items/:id/compress', async (req) => { const id = me(req); limit(id.userId); return compressOptimization(db, { userId: id.userId, deps }, paramsSchema.parse(req.params).id); });

  // ---- library ----
  app.get('/api/optimizer/items', async (req) => {
    const id = me(req);
    const q = z.object({ page: z.coerce.number().int().min(1).default(1), q: z.string().max(200).optional(), folder: z.string().max(60).optional(),
      favorites: z.enum(['0', '1']).optional(), workflow: z.enum(OPT_WORKFLOWS).optional() }).parse(req.query);
    return listOptimizations(db, id.userId, { q: q.q, folder: q.folder, favorites: q.favorites === '1', workflow: q.workflow, page: q.page });
  });
  app.get('/api/optimizer/items/:id', async (req) => rowToOptimization(getOwned(db, paramsSchema.parse(req.params).id, me(req).userId)));
  app.patch('/api/optimizer/items/:id', async (req) => {
    const id = me(req); const row = getOwned(db, paramsSchema.parse(req.params).id, id.userId);
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
    const id = me(req); const row = getOwned(db, paramsSchema.parse(req.params).id, id.userId);
    db.tx(() => {
      db.run('DELETE FROM optimizations WHERE id = ?', row.id);
      unindexDoc(db, 'opt', row.id);
    });
    return { ok: true };
  });

  // ---- folders ----
  app.get('/api/optimizer/folders', async (req) => ({ items: listFolders(db, me(req).userId) }));
  app.post('/api/optimizer/folders', async (req) => createFolder(db, me(req).userId, z.object({ name: z.string().max(OPT_LIMITS.folderName * 2) }).parse(req.body).name));
  app.patch('/api/optimizer/folders/:id', async (req) => {
    const id = me(req); const f = ownFolder(db, paramsSchema.parse(req.params).id, id.userId);
    if (f.default_key) throw new AppError(409, 'folder_protected', 'Стандартную папку нельзя переименовать');
    const name = z.object({ name: z.string().trim().min(1).max(OPT_LIMITS.folderName) }).parse(req.body).name;
    if (db.get('SELECT 1 FROM folders WHERE user_id = ? AND name = ? AND id <> ?', id.userId, name, f.id)) throw new AppError(409, 'folder_exists', 'Папка с таким названием уже есть');
    db.run('UPDATE folders SET name = ? WHERE id = ?', name, f.id);
    return listFolders(db, id.userId).find((x) => x.id === f.id);
  });
  app.delete('/api/optimizer/folders/:id', async (req) => {
    const id = me(req); const f = ownFolder(db, paramsSchema.parse(req.params).id, id.userId);
    if (f.default_key) throw new AppError(409, 'folder_protected', 'Стандартную папку нельзя удалить');
    db.tx(() => { db.run('UPDATE optimizations SET folder_id = NULL WHERE user_id = ? AND folder_id = ?', id.userId, f.id); db.run('DELETE FROM folders WHERE id = ?', f.id); });
    return { ok: true };
  });
}
