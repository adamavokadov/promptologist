import { useEffect, useId, useState } from 'react';
import { fillPromptVariables, extractPromptVariables } from '../../../../shared/src/prompt.ts';
import { teamFolderInput, type TeamFolder, type TeamFolderInput, type TeamFolders, type TeamPrompt, type TeamPromptSummary } from '../../../../shared/src/team.ts';
import { del, get, post, put } from '../api.ts';
import { t } from '../strings.ru.ts';
import { ConfirmModal, Empty, fmtDate, Modal, Skeletons, Spinner } from '../ui.tsx';
import { PromptActions } from './PromptActions.tsx';
import { PromptChecklist, PromptFields } from './PromptFields.tsx';
import { PromptVersionEditor } from './PromptVersionEditor.tsx';

const folderPath = (id: string) => `/api/team/folders/${id}`;
const itemPath = (folder: string, item: string) => `${folderPath(folder)}/prompts/${item}`;
const message = (error: unknown) => error instanceof Error ? error.message : t.common.error;
type Listing = { items: TeamPromptSummary[]; has_more: boolean };

export function TeamLibrary() {
  const [folders, setFolders] = useState<TeamFolders | null>(null);
  const [folderId, setFolderId] = useState('');
  const [page, setPage] = useState(1);
  const [list, setList] = useState<Listing | null>(null);
  const [error, setError] = useState('');
  const [readyItem, setReadyItem] = useState<{ folderId: string; itemId: string } | null>(null);
  const [editor, setEditor] = useState<TeamFolder | 'create' | null>(null);
  const [refresh, setRefresh] = useState(0);
  const folder = folders?.items.find((item) => item.id === folderId) ?? folders?.items[0];
  const currentId = folder?.id;
  const reload = () => setRefresh((value) => value + 1);

  useEffect(() => {
    let live = true;
    void get<TeamFolders>('/api/team/folders').then((data) => { if (live) setFolders(data); })
      .catch((problem) => { if (live) setError(message(problem)); });
    return () => { live = false; };
  }, [refresh]);
  useEffect(() => {
    setList(null);
    setError('');
    if (!currentId) return;
    let live = true;
    void get<Listing>(`${folderPath(currentId)}/prompts?page=${page}`).then((data) => {
      if (!live) return;
      if (!data.items.length && page > 1) setPage(page - 1);
      else setList(data);
    }).catch((problem) => { if (live) setError(message(problem)); });
    return () => { live = false; };
  }, [currentId, page, refresh]);

  return (
    <div className="col">
      {error && <p className="banner err" role="alert">{error}</p>}
      {!folders && !error && <Skeletons />}
      {folders && <div className="library-layout">
        <nav className="surface card col library-folders" aria-label={t.team.scope}>
          {folders.items.map((item) => <button key={item.id} className="nav-item" aria-current={item.id === currentId ? 'true' : undefined}
            onClick={() => { setFolderId(item.id); setPage(1); }}>
            <span className="library-folder-name grow">{item.name}</span>
          </button>)}
          {folders.can_manage && <button className="btn sm" onClick={() => setEditor('create')}>{t.team.newFolder}</button>}
        </nav>
        <div className="col">
          {!folder && <Empty title={t.team.emptyFolders} hint={t.team.emptyFoldersHint} />}
          {folder && <>
            <header className="row wrap spread">
              <div className="row wrap"><h2>{folder.name}</h2>{!folder.can_edit && <span className="badge">{t.team.readOnly}</span>}</div>
              {folders.can_manage && <button className="btn sm" onClick={() => setEditor(folder)}>{t.team.manage}</button>}
            </header>
            {!list && !error && <Skeletons />}
            {list?.items.length === 0 && <Empty title={t.team.emptyPrompts} hint={folder.can_edit ? t.team.emptyPromptsHint : undefined} />}
            {list?.items.map((item) => <article className="surface card col" key={item.id}>
              <div className="row wrap spread"><h3>{item.title}</h3><span className="small tx3">v{item.version} · {fmtDate(item.updated_at)}</span></div>
              <p className="small tx2">{item.preview}</p>
              <button className="btn sm prompt-start" onClick={() => setReadyItem({ folderId: folder.id, itemId: item.id })}>{t.library.open}</button>
            </article>)}
            {list && (page > 1 || list.has_more) && <div className="row wrap">
              <button className="btn sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>{t.common.prev}</button>
              <span className="small tx2">{t.common.page} {page}</span>
              <button className="btn sm" disabled={!list.has_more} onClick={() => setPage(page + 1)}>{t.common.next}</button>
            </div>}
          </>}
        </div>
      </div>}
      {editor && <FolderSettings folder={editor === 'create' ? undefined : editor} onClose={() => setEditor(null)}
        onSaved={(id) => { setFolderId(id); setPage(1); reload(); }} />}
      {readyItem && <TeamItem key={readyItem.itemId} path={itemPath(readyItem.folderId, readyItem.itemId)}
        editable={folders?.items.find((item) => item.id === readyItem.folderId)?.can_edit ?? false}
        onClose={() => setReadyItem(null)} onChanged={reload} />}
    </div>
  );
}

function FolderSettings({ folder, onClose, onSaved }: { folder?: TeamFolder; onClose: () => void; onSaved: (id: string) => void }) {
  const prefix = useId();
  const [name, setName] = useState(folder?.name ?? '');
  const [visibility, setVisibility] = useState<TeamFolderInput['visibility']>(folder?.visibility ?? 'restricted');
  const [readers, setReaders] = useState('');
  const [editors, setEditors] = useState('');
  const [loading, setLoading] = useState(!!folder);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    if (!folder) return;
    let live = true;
    void get<TeamFolderInput>(`${folderPath(folder.id)}/settings`).then((data) => {
      if (!live) return;
      setName(data.name);
      setVisibility(data.visibility);
      setReaders(data.members.filter((member) => member.role === 'reader').map((member) => member.user_id).join(', '));
      setEditors(data.members.filter((member) => member.role === 'editor').map((member) => member.user_id).join(', '));
    }).catch((problem) => { if (live) { setError(message(problem)); setFailed(true); } })
      .finally(() => { if (live) setLoading(false); });
    return () => { live = false; };
  }, [folder?.id]);
  const save = async () => {
    const split = (s: string) => [...new Set(s.split(/[\s,;]+/).filter(Boolean))];
    const members = [
      ...split(readers).map((user_id) => ({ user_id, role: 'reader' as const })),
      ...split(editors).map((user_id) => ({ user_id, role: 'editor' as const })),
    ];
    const parsed = teamFolderInput.safeParse({ name, visibility, members });
    if (!parsed.success) { setError(t.team.invalidMembers); return; }
    setBusy(true);
    setError('');
    try {
      const saved = folder ? await put<TeamFolder>(`${folderPath(folder.id)}/settings`, parsed.data) : await post<TeamFolder>('/api/team/folders', parsed.data);
      onSaved(saved.id);
      onClose();
    } catch (problem) { setError(message(problem)); }
    finally { setBusy(false); }
  };
  return (
    <Modal title={folder ? t.team.manage : t.team.newFolder} onClose={onClose} footer={<>
      <button className="btn" disabled={busy} onClick={onClose}>{t.common.cancel}</button>
      <button className="btn primary" disabled={busy || loading || failed || !name.trim()} onClick={() => { void save(); }}>{busy && <Spinner />}{t.common.save}</button>
    </>}>
      {error && <p className="banner err" role="alert">{error}</p>}
      {loading ? <Spinner /> : <div className="col">
        <div><label className="label" htmlFor={`${prefix}-name`}>{t.library.folderName}</label>
          <input className="field" id={`${prefix}-name`} maxLength={60} value={name} onChange={(event) => setName(event.target.value)} /></div>
        <div><label className="label" htmlFor={`${prefix}-visibility`}>{t.team.visibility}</label>
          <select className="field" id={`${prefix}-visibility`} value={visibility} onChange={(event) => setVisibility(event.target.value === 'portal' ? 'portal' : 'restricted')}>
            <option value="restricted">{t.team.restricted}</option><option value="portal">{t.team.portal}</option>
          </select>
        </div>
        <p className="small tx2">{t.team.membersHint}</p>
        <div><label className="label" htmlFor={`${prefix}-readers`}>{t.team.readers}</label>
          <textarea className="field" id={`${prefix}-readers`} rows={2} maxLength={4000} value={readers} onChange={(event) => setReaders(event.target.value)} /></div>
        <div><label className="label" htmlFor={`${prefix}-editors`}>{t.team.editors}</label>
          <textarea className="field" id={`${prefix}-editors`} rows={2} maxLength={4000} value={editors} onChange={(event) => setEditors(event.target.value)} /></div>
      </div>}
    </Modal>
  );
}

function TeamItem({ path, editable, onClose, onChanged }: { path: string; editable: boolean; onClose: () => void; onChanged: () => void }) {
  const [item, setItem] = useState<TeamPrompt | null>(null);
  const [error, setError] = useState('');
  const [values, setValues] = useState<Record<string, string>>({});
  const [editing, setEditing] = useState(false);
  const [confirm, setConfirm] = useState(false);
  useEffect(() => {
    let live = true;
    void get<TeamPrompt>(path).then((data) => { if (live) setItem(data); })
      .catch((problem) => { if (live) setError(message(problem)); });
    return () => { live = false; };
  }, [path]);
  const text = item ? fillPromptVariables(item.body, values) : '';
  const remove = async () => {
    try { await del(path); onChanged(); onClose(); }
    catch (problem) { setError(message(problem)); }
  };
  return <>
    <Modal title={item?.title ?? t.team.scope} wide onClose={onClose} footer={editable && item ? <>
      <button className="btn sm" onClick={() => setEditing(true)}>{t.prompt.editVersion}</button>
      <button className="btn sm danger" onClick={() => setConfirm(true)}>{t.common.delete}</button>
    </> : undefined}>
      {error && <p className="banner err" role="alert">{error}</p>}
      {!item && !error && <Spinner />}
      {item && <>
        <PromptFields names={extractPromptVariables(item.body).slice(0, 20)} values={values} onChange={(name, value) => setValues((current) => ({ ...current, [name]: value }))} />
        <div className="prompt-box" tabIndex={0}>{text}</div>
        <PromptActions text={text} />
        <PromptChecklist text={text} />
      </>}
    </Modal>
    {editing && <PromptVersionEditor url={`${path}/versions`} onClose={() => setEditing(false)}
      onSave={async (body, expected_version) => { setItem(await put<TeamPrompt>(path, { body, expected_version })); onChanged(); }} />}
    {confirm && <ConfirmModal title={t.common.delete} text={t.team.confirmDelete} danger onClose={() => setConfirm(false)} onConfirm={remove} />}
  </>;
}
