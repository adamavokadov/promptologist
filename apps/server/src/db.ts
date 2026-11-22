import { DatabaseSync, type SQLInputValue } from 'node:sqlite';
import fs from 'node:fs';
import path from 'node:path';
import { config } from './config.ts';

export type Row = Record<string, any>;
export interface Db {
  raw: DatabaseSync;
  fts: boolean;
  all<T = Row>(sql: string, ...params: SQLInputValue[]): T[];
  get<T = Row>(sql: string, ...params: SQLInputValue[]): T | undefined;
  run(sql: string, ...params: SQLInputValue[]): { changes: number | bigint };
  tx<T>(fn: () => T): T;
}

const MIGRATIONS: string[] = [
  /* v1 */ `
CREATE TABLE skills (
  id TEXT PRIMARY KEY, display_name TEXT NOT NULL, current_version_id TEXT, model_lineup TEXT NOT NULL DEFAULT '[]',
  sources TEXT NOT NULL DEFAULT '[]', last_check_at TEXT, next_check_at TEXT,
  status TEXT NOT NULL DEFAULT 'fresh', consecutive_failures INTEGER NOT NULL DEFAULT 0,
  canary_remaining INTEGER NOT NULL DEFAULT 0, canary_failures INTEGER NOT NULL DEFAULT 0,
  paused INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE skill_versions (
  id TEXT PRIMARY KEY, skill_id TEXT NOT NULL, version INTEGER NOT NULL, frontmatter TEXT NOT NULL, body_md TEXT NOT NULL,
  changelog TEXT NOT NULL DEFAULT '[]', sources TEXT NOT NULL DEFAULT '[]', origin TEXT NOT NULL,
  golden_result TEXT, created_at TEXT NOT NULL, UNIQUE(skill_id, version)
);
CREATE TABLE generations (
  id TEXT PRIMARY KEY, user_id TEXT NOT NULL, raw_input TEXT NOT NULL, language TEXT NOT NULL, options TEXT NOT NULL,
  systems TEXT NOT NULL DEFAULT '[]', intent TEXT, questions TEXT, status TEXT NOT NULL, tokens_used INTEGER NOT NULL DEFAULT 0,
  latency_ms INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, deleted_at TEXT
);
CREATE TABLE generation_results (
  id TEXT PRIMARY KEY, generation_id TEXT NOT NULL, skill_id TEXT NOT NULL, skill_version_id TEXT NOT NULL,
  prompt_text TEXT NOT NULL DEFAULT '', improvements TEXT NOT NULL DEFAULT '[]', assumptions TEXT NOT NULL DEFAULT '[]',
  usage_notes TEXT NOT NULL DEFAULT '', status TEXT NOT NULL, error TEXT, tokens_used INTEGER NOT NULL DEFAULT 0,
  latency_ms INTEGER NOT NULL DEFAULT 0, is_favorite INTEGER NOT NULL DEFAULT 0, favorited_at TEXT,
  variant_of TEXT, created_at TEXT NOT NULL
);
CREATE TABLE templates (
  id TEXT PRIMARY KEY, user_id TEXT, title TEXT NOT NULL, description TEXT NOT NULL DEFAULT '', body TEXT NOT NULL,
  language TEXT NOT NULL, default_systems TEXT NOT NULL DEFAULT '[]', tags TEXT NOT NULL DEFAULT '[]',
  is_seed INTEGER NOT NULL DEFAULT 0, usage_count INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL, deleted_at TEXT
);
CREATE TABLE refresh_runs (
  id TEXT PRIMARY KEY, skill_id TEXT NOT NULL, trigger TEXT NOT NULL, job_run_id TEXT, status TEXT NOT NULL,
  step TEXT NOT NULL DEFAULT 'plan', payload TEXT NOT NULL DEFAULT '{}', budget_used TEXT NOT NULL DEFAULT '{}',
  error TEXT, started_at TEXT NOT NULL, finished_at TEXT
);
CREATE TABLE reports (
  id TEXT PRIMARY KEY, run_id TEXT NOT NULL, skill_id TEXT NOT NULL, verdict TEXT NOT NULL, summary_ru TEXT NOT NULL,
  changelog TEXT NOT NULL DEFAULT '[]', sources TEXT NOT NULL DEFAULT '[]', golden TEXT, budget TEXT,
  version_from INTEGER, version_to INTEGER, created_at TEXT NOT NULL
);
CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE job_dedupe (run_id TEXT PRIMARY KEY, received_at TEXT NOT NULL, response_status INTEGER NOT NULL DEFAULT 202, processed_at TEXT);
CREATE TABLE app_lock (name TEXT PRIMARY KEY, holder TEXT NOT NULL, expires_at TEXT NOT NULL);
CREATE TABLE search_docs (ref_type TEXT NOT NULL, ref_id TEXT NOT NULL, user_id TEXT, body TEXT NOT NULL, PRIMARY KEY (ref_type, ref_id));
CREATE INDEX idx_generations_user_created ON generations(user_id, created_at);
CREATE INDEX idx_results_generation ON generation_results(generation_id);
CREATE INDEX idx_results_fav ON generation_results(is_favorite, favorited_at);
CREATE INDEX idx_skills_next ON skills(next_check_at);
CREATE INDEX idx_runs_skill ON refresh_runs(skill_id, started_at);
CREATE INDEX idx_templates_user ON templates(user_id);
`,
  /* v2: prompt optimizer library (history, favorites, folders) */ `
CREATE TABLE optimizations (
  id TEXT PRIMARY KEY, user_id TEXT NOT NULL, workflow TEXT NOT NULL, status TEXT NOT NULL, raw_input TEXT NOT NULL,
  options TEXT NOT NULL DEFAULT '{}', questions TEXT NOT NULL DEFAULT '[]', answers TEXT NOT NULL DEFAULT '[]',
  initial_score REAL, initial_critique TEXT NOT NULL DEFAULT '', optimized_score REAL, changelog TEXT NOT NULL DEFAULT '[]',
  final_prompt TEXT NOT NULL DEFAULT '', framework_used TEXT NOT NULL DEFAULT '', var_values TEXT NOT NULL DEFAULT '{}',
  compressed_prompt TEXT, tokens_before INTEGER, tokens_after INTEGER, is_favorite INTEGER NOT NULL DEFAULT 0, favorited_at TEXT,
  folder_id TEXT, tags TEXT NOT NULL DEFAULT '[]', provider TEXT NOT NULL DEFAULT '', model TEXT NOT NULL DEFAULT '',
  tokens_used INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, deleted_at TEXT
);
CREATE INDEX idx_opt_user_created ON optimizations(user_id, created_at);
CREATE INDEX idx_opt_folder ON optimizations(user_id, folder_id);
CREATE TABLE folders (
  id TEXT PRIMARY KEY, user_id TEXT NOT NULL, name TEXT NOT NULL, default_key TEXT, created_at TEXT NOT NULL,
  UNIQUE(user_id, name)
);
CREATE INDEX idx_folders_user ON folders(user_id);
`,
];

export function openDb(file?: string): Db {
  let target = file;
  if (target === undefined) {
    fs.mkdirSync(config.dataDir, { recursive: true });
    target = path.join(config.dataDir, 'promptolog.db');
  }
  const raw = new DatabaseSync(target);
  raw.exec('PRAGMA journal_mode = WAL; PRAGMA foreign_keys = OFF; PRAGMA busy_timeout = 5000;');
  const version = (raw.prepare('PRAGMA user_version').get() as { user_version: number }).user_version;
  for (let v = version; v < MIGRATIONS.length; v++) {
    raw.exec('BEGIN');
    try {
      raw.exec(MIGRATIONS[v]!);
      raw.exec(`PRAGMA user_version = ${v + 1}`);
      raw.exec('COMMIT');
    } catch (e) { raw.exec('ROLLBACK'); throw e; }
  }
  let fts = false;
  try {
    raw.exec("CREATE VIRTUAL TABLE IF NOT EXISTS search_fts USING fts5(ref_key UNINDEXED, body, tokenize='unicode61 remove_diacritics 2')");
    fts = true;
  } catch { fts = false; }
  const stmtCache = new Map<string, ReturnType<DatabaseSync['prepare']>>();
  const prep = (sql: string) => {
    let s = stmtCache.get(sql);
    if (!s) { s = raw.prepare(sql); stmtCache.set(sql, s); }
    return s;
  };
  let depth = 0;
  return {
    raw, fts,
    all: <T = Row>(sql: string, ...p: SQLInputValue[]) => prep(sql).all(...p) as T[],
    get: <T = Row>(sql: string, ...p: SQLInputValue[]) => prep(sql).get(...p) as T | undefined,
    run: (sql: string, ...p: SQLInputValue[]) => prep(sql).run(...p),
    tx<T>(fn: () => T): T {
      if (depth > 0) return fn();
      raw.exec('BEGIN IMMEDIATE');
      depth++;
      try { const r = fn(); raw.exec('COMMIT'); return r; }
      catch (e) { raw.exec('ROLLBACK'); throw e; }
      finally { depth--; }
    },
  };
}

// ----- settings helpers -----
import { DEFAULT_SETTINGS, settingsSchema, type Settings } from '../../../shared/src/index.ts';

export function getSettings(db: Db): Settings {
  const merged: Record<string, unknown> = { ...DEFAULT_SETTINGS };
  for (const r of db.all<{ key: string; value: string }>('SELECT key, value FROM settings')) {
    try { merged[r.key] = JSON.parse(r.value); } catch { /* ignore corrupt */ }
  }
  const parsed = settingsSchema.safeParse(merged);
  return parsed.success ? parsed.data : { ...DEFAULT_SETTINGS };
}
export function setSettings(db: Db, patch: Partial<Settings>): Settings {
  db.tx(() => {
    for (const [k, v] of Object.entries(patch)) {
      db.run('INSERT INTO settings(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value', k, JSON.stringify(v));
    }
  });
  return getSettings(db);
}

// ----- search index (FTS5 when available, LIKE otherwise) -----
export function indexDoc(db: Db, refType: string, refId: string, userId: string | null, body: string): void {
  const key = `${refType}:${refId}`;
  db.run('INSERT INTO search_docs(ref_type, ref_id, user_id, body) VALUES(?,?,?,?) ON CONFLICT(ref_type, ref_id) DO UPDATE SET body = excluded.body', refType, refId, userId, body);
  if (db.fts) {
    db.run('DELETE FROM search_fts WHERE ref_key = ?', key);
    db.run('INSERT INTO search_fts(ref_key, body) VALUES(?, ?)', key, body);
  }
}
export function unindexDoc(db: Db, refType: string, refId: string): void {
  db.run('DELETE FROM search_docs WHERE ref_type = ? AND ref_id = ?', refType, refId);
  if (db.fts) db.run('DELETE FROM search_fts WHERE ref_key = ?', `${refType}:${refId}`);
}
/** Returns matching ref ids of the given type (optionally scoped by user). */
export function searchDocs(db: Db, refType: string, userId: string | null, query: string): string[] {
  const tokens = query.toLowerCase().split(/[^\p{L}\p{N}]+/u).filter(Boolean).slice(0, 8);
  if (tokens.length === 0) return [];
  if (db.fts) {
    const match = tokens.map((t) => `"${t.replace(/"/g, '')}"*`).join(' ');
    const rows = db.all<{ ref_key: string }>('SELECT ref_key FROM search_fts WHERE search_fts MATCH ? LIMIT 2000', match);
    const ids = rows.filter((r) => r.ref_key.startsWith(`${refType}:`)).map((r) => r.ref_key.slice(refType.length + 1));
    if (userId === null || ids.length === 0) return ids;
    const owned = db.all<{ ref_id: string }>(
      `SELECT ref_id FROM search_docs WHERE ref_type = ? AND user_id = ? AND ref_id IN (${ids.map(() => '?').join(',')})`, refType, userId, ...ids);
    return owned.map((r) => r.ref_id);
  }
  const where = tokens.map(() => 'LOWER(body) LIKE ?').join(' AND ');
  const likeParams = tokens.map((t) => `%${t.replace(/[%_]/g, '')}%`);
  const sql = `SELECT ref_id FROM search_docs WHERE ref_type = ? ${userId === null ? '' : 'AND user_id = ?'} AND ${where} LIMIT 2000`;
  const params: SQLInputValue[] = userId === null ? [refType, ...likeParams] : [refType, userId, ...likeParams];
  return db.all<{ ref_id: string }>(sql, ...params).map((r) => r.ref_id);
}

// ----- generic lock with TTL (global refresh mutex) -----
export function acquireLock(db: Db, name: string, holder: string, ttlMs: number, now = Date.now()): boolean {
  return db.tx(() => {
    const cur = db.get<{ holder: string; expires_at: string }>('SELECT holder, expires_at FROM app_lock WHERE name = ?', name);
    if (cur && Date.parse(cur.expires_at) > now && cur.holder !== holder) return false;
    db.run('INSERT INTO app_lock(name, holder, expires_at) VALUES(?,?,?) ON CONFLICT(name) DO UPDATE SET holder = excluded.holder, expires_at = excluded.expires_at',
      name, holder, new Date(now + ttlMs).toISOString());
    return true;
  });
}
export function releaseLock(db: Db, name: string, holder: string): void {
  db.run('DELETE FROM app_lock WHERE name = ? AND holder = ?', name, holder);
}
