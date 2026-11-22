import type { FastifyInstance, FastifyRequest } from 'fastify';
import { z } from 'zod';
import type { Identity } from './auth.ts';
import { config } from './config.ts';
import type { Db } from './db.ts';
import { versionQuery } from './prompt-features.ts';
import { appendPromptVersion, currentVersion, deletePromptVersions, listVersionsForPrompt } from './prompt-versions.ts';
import { AppError, nowIso, uid } from './util.ts';
import { promptRevisionSchema, teamFolderInput, teamPromptInput, type TeamFolder, type TeamFolderInput, type TeamPrompt } from '../../../shared/src/index.ts';

const folderParam = z.object({ folderId: z.string().min(1).max(60) });
const itemParams = folderParam.extend({ id: z.string().min(1).max(60) });
const pageSchema = z.object({ page: z.coerce.number().int().min(1).max(10000).default(1) });
const portalId = z.uuid();
const NOT_FOUND = () => new AppError(404, 'not_found', 'Папка или промпт не найдены');
type Principal = { portal: string; user: string; admin: boolean };
type FolderRow = { id: string; name: string; visibility: TeamFolder['visibility']; role: 'reader' | 'editor' | null };
type PromptRow = Omit<TeamPrompt, 'version'> & { created_at: string };

function principal(req: FastifyRequest, identity: Identity): Principal | undefined {
  if (config.devAuthBypass) return { portal: 'dev.local', user: identity.userId, admin: true };
  // The Gateway sends the portal UUID separately from the account domain.
  const portal = portalId.safeParse(req.headers['x-vibe-portal-id']);
  const user = req.headers['x-vibe-user-id'];
  if (!portal.success || typeof user !== 'string' || !/^\d{1,18}$/.test(user) || user !== identity.userId) return undefined;
  return { portal: portal.data.toLowerCase(), user, admin: req.headers['x-vibe-user-role'] === 'ADMIN' };
}

function canRead(folder: FolderRow, who: Principal): boolean {
  return who.admin || folder.visibility === 'portal' || folder.role !== null;
}
function canEdit(folder: FolderRow, who: Principal): boolean {
  return who.admin || folder.role === 'editor';
}
function asFolder(folder: FolderRow, who: Principal): TeamFolder {
  return { id: folder.id, name: folder.name, visibility: folder.visibility, can_edit: canEdit(folder, who) };
}

export function registerTeamRoutes(app: FastifyInstance, db: Db, me: (req: FastifyRequest) => Identity): void {
  function requirePrincipal(req: FastifyRequest): Principal {
    const who = principal(req, me(req));
    if (!who) throw new AppError(403, 'portal_required', 'Откройте приложение как сотрудник портала Bitrix24');
    return who;
  }
  function requireAdmin(req: FastifyRequest): Principal {
    const who = requirePrincipal(req);
    if (!who.admin) throw new AppError(403, 'admin_required', 'Требуются права администратора портала');
    return who;
  }
  function folderRows(who: Principal, id?: string): FolderRow[] {
    return db.all<FolderRow>(
      `SELECT f.id, f.name, f.visibility, m.role FROM team_folders f
       LEFT JOIN team_folder_members m ON m.folder_id = f.id AND m.user_id = ?
       WHERE f.portal_id = ?${id ? ' AND f.id = ?' : ''} ORDER BY f.name, f.id`,
      who.user, who.portal, ...(id ? [id] : []),
    );
  }
  function folder(who: Principal, id: string, write = false): FolderRow {
    const current = folderRows(who, id)[0];
    if (!current || !canRead(current, who)) throw NOT_FOUND();
    if (write && !canEdit(current, who)) throw new AppError(403, 'read_only', 'Папка доступна только для чтения');
    return current;
  }
  function item(folderId: string, id: string): PromptRow {
    const row = db.get<PromptRow>('SELECT id, title, body, created_at, updated_at FROM team_prompts WHERE id = ? AND folder_id = ?', id, folderId);
    if (!row) throw NOT_FOUND();
    return row;
  }
  function toPrompt(row: PromptRow): TeamPrompt {
    return { id: row.id, title: row.title, body: row.body, updated_at: row.updated_at, version: currentVersion(db, 'team', row.id) };
  }
  function writeFolder(who: Principal, id: string, body: TeamFolderInput, create: boolean): TeamFolder {
    return db.tx(() => {
      if (db.get('SELECT 1 FROM team_folders WHERE portal_id = ? AND name = ? AND id <> ?', who.portal, body.name, id)) {
        throw new AppError(409, 'folder_exists', 'Папка с таким названием уже есть');
      }
      if (create) {
        const count = db.get<{ n: number }>('SELECT COUNT(*) AS n FROM team_folders WHERE portal_id = ?', who.portal)!.n;
        if (count >= 100) throw new AppError(409, 'folder_limit', 'Достигнут лимит командных папок');
        db.run('INSERT INTO team_folders(id, portal_id, name, visibility) VALUES (?, ?, ?, ?)', id, who.portal, body.name, body.visibility);
      } else {
        folder(who, id, true);
        db.run('UPDATE team_folders SET name = ?, visibility = ? WHERE id = ? AND portal_id = ?', body.name, body.visibility, id, who.portal);
        db.run('DELETE FROM team_folder_members WHERE folder_id = ?', id);
      }
      for (const member of body.members) {
        db.run('INSERT INTO team_folder_members(folder_id, user_id, role) VALUES (?, ?, ?)', id, member.user_id, member.role);
      }
      return asFolder(folder(who, id), who);
    });
  }

  app.get('/api/team/folders', async (req) => {
    const who = principal(req, me(req));
    return who ? { items: folderRows(who).filter((row) => canRead(row, who)).map((row) => asFolder(row, who)), can_manage: who.admin }
      : { items: [], can_manage: false };
  });
  app.post('/api/team/folders', async (req) => writeFolder(requireAdmin(req), uid(), teamFolderInput.parse(req.body), true));
  app.get('/api/team/folders/:folderId/settings', async (req) => {
    const who = requireAdmin(req);
    const row = folder(who, folderParam.parse(req.params).folderId);
    const members = db.all<TeamFolderInput['members'][number]>('SELECT user_id, role FROM team_folder_members WHERE folder_id = ? ORDER BY user_id', row.id);
    return { name: row.name, visibility: row.visibility, members };
  });
  app.put('/api/team/folders/:folderId/settings', async (req) =>
    writeFolder(requireAdmin(req), folderParam.parse(req.params).folderId, teamFolderInput.parse(req.body), false));

  app.get('/api/team/folders/:folderId/prompts', async (req) => {
    const row = folder(requirePrincipal(req), folderParam.parse(req.params).folderId);
    const { page } = pageSchema.parse(req.query);
    const rows = db.all<{ id: string; title: string; preview: string; updated_at: string; version: number }>(
      `SELECT p.id, p.title, substr(p.body, 1, 220) AS preview, p.updated_at,
        COALESCE((SELECT MAX(v.version) FROM prompt_versions v WHERE v.scope = 'team' AND v.prompt_id = p.id), 1) AS version
       FROM team_prompts p WHERE p.folder_id = ? ORDER BY p.updated_at DESC, p.id LIMIT 21 OFFSET ?`,
      row.id, (page - 1) * 20,
    );
    return { items: rows.slice(0, 20), has_more: rows.length > 20 };
  });
  app.post('/api/team/folders/:folderId/prompts', async (req) => {
    const row = folder(requirePrincipal(req), folderParam.parse(req.params).folderId, true);
    const { title, body } = teamPromptInput.parse(req.body);
    const id = uid();
    const now = nowIso();
    db.run('INSERT INTO team_prompts(id, folder_id, title, body, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)', id, row.id, title, body, now, now);
    return toPrompt(item(row.id, id));
  });
  app.get('/api/team/folders/:folderId/prompts/:id', async (req) => {
    const params = itemParams.parse(req.params);
    folder(requirePrincipal(req), params.folderId);
    return toPrompt(item(params.folderId, params.id));
  });
  app.get('/api/team/folders/:folderId/prompts/:id/versions', async (req) => {
    const params = itemParams.parse(req.params);
    folder(requirePrincipal(req), params.folderId, true);
    return listVersionsForPrompt(db, 'team', item(params.folderId, params.id), versionQuery.parse(req.query).before);
  });
  app.put('/api/team/folders/:folderId/prompts/:id', async (req) => {
    const params = itemParams.parse(req.params);
    const who = requirePrincipal(req);
    const { body, expected_version } = promptRevisionSchema.parse(req.body);
    return db.tx(() => {
      folder(who, params.folderId, true);
      const old = item(params.folderId, params.id);
      appendPromptVersion(db, 'team', old, body, expected_version);
      if (old.body !== body) db.run('UPDATE team_prompts SET body = ?, updated_at = ? WHERE id = ?', body, nowIso(), old.id);
      return toPrompt(item(params.folderId, params.id));
    });
  });
  app.delete('/api/team/folders/:folderId/prompts/:id', async (req) => {
    const params = itemParams.parse(req.params);
    const who = requirePrincipal(req);
    db.tx(() => {
      folder(who, params.folderId, true);
      const old = item(params.folderId, params.id);
      deletePromptVersions(db, 'team', old.id);
      db.run('DELETE FROM team_prompts WHERE id = ?', old.id);
    });
    return { ok: true };
  });
}
