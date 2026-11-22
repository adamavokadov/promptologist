import type { Db } from './db.ts';
import { AppError, nowIso } from './util.ts';
import type { PromptVersion, PromptVersions } from '../../../shared/src/prompt.ts';

type Scope = 'optimization' | 'template' | 'team';
type Source = { id: string; body: string; created_at: string };

export function currentVersion(db: Db, scope: Scope, id: string): number {
  return db.get<{ version: number }>(
    'SELECT version FROM prompt_versions WHERE scope = ? AND prompt_id = ? ORDER BY version DESC LIMIT 1', scope, id,
  )?.version ?? 1;
}

export function listVersionsForPrompt(db: Db, scope: Scope, source: Source, before?: number): PromptVersions {
  const version = currentVersion(db, scope, source.id);
  if (version === 1) {
    return { current_version: version, items: before === undefined || before > 1 ? [{ version, body: source.body, created_at: source.created_at }] : [] };
  }
  const items = db.all<PromptVersion>(
    'SELECT version, body, created_at FROM prompt_versions WHERE scope = ? AND prompt_id = ? AND version < ? ORDER BY version DESC LIMIT 20',
    scope, source.id, before ?? version + 1,
  );
  return { current_version: version, items };
}

/** Call inside the transaction that updates the current prompt. */
export function appendPromptVersion(db: Db, scope: Scope, source: Source, body: string, expected?: number): number {
  const version = currentVersion(db, scope, source.id);
  if (expected !== undefined && expected !== version) {
    throw new AppError(409, 'version_conflict', 'Промпт уже изменён. Откройте актуальную версию.');
  }
  if (body === source.body) return version;
  const sql = 'INSERT INTO prompt_versions(scope, prompt_id, version, body, created_at) VALUES (?, ?, ?, ?, ?)';
  if (version === 1) db.run(sql, scope, source.id, 1, source.body, source.created_at);
  db.run(sql, scope, source.id, version + 1, body, nowIso());
  return version + 1;
}

export function deletePromptVersions(db: Db, scope: Scope, id: string): void {
  db.run('DELETE FROM prompt_versions WHERE scope = ? AND prompt_id = ?', scope, id);
}
