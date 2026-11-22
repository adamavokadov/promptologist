import { useCallback, useEffect, useRef, useState } from 'react';
import { FolderPlus, Pencil, Trash2 } from 'lucide-react';
import { OPT_LIMITS, OPT_WORKFLOWS, type FolderDTO, type OptWorkflow, type OptimizationDTO } from '../../../../shared/src/index.ts';
import { t } from '../strings.ru.ts';
import { del, get, patch, post, ApiError } from '../api.ts';
import { useApp } from '../context.tsx';
import { OptimizationView } from '../components/OptimizationView.tsx';
import { ConfirmModal, Empty, Modal, Skeletons, StarButton, fmtDate, useDebounced, useToast } from '../ui.tsx';

interface Row { id: string; workflow: OptWorkflow; preview: string; prompt_preview: string; initial_score: number | null; optimized_score: number | null; is_favorite: boolean; folder_id: string | null; tags: string[]; created_at: string; has_variables: boolean }

export function LibraryScreen() {
  const toast = useToast(); const app = useApp();
  const [folders, setFolders] = useState<FolderDTO[]>([]); const [folder, setFolder] = useState<string>('all'); const [wf, setWf] = useState<OptWorkflow | ''>('');
  const [q, setQ] = useState(''); const dq = useDebounced(q); const [page, setPage] = useState(1);
  const [rows, setRows] = useState<Row[] | null>(null); const [total, setTotal] = useState(0);
  const [open, setOpen] = useState<OptimizationDTO | null>(null); const [confirm, setConfirm] = useState<'item' | 'folder' | null>(null);
  const [name, setName] = useState('');
  const [editMode, setEditMode] = useState<'create' | 'rename' | null>(null);
  const [folderBusy, setFolderBusy] = useState(false);
  const [revision, setRevision] = useState(0);
  const requestId = useRef(0);
  const itemRequestId = useRef(0);
  const fail = useCallback((e: unknown) => toast((e as ApiError).message ?? t.common.error, 'err'), [toast]);
  const loadFolders = useCallback(() => get<{ items: FolderDTO[] }>('/api/optimizer/folders').then((d) => setFolders(d.items)).catch(() => {}), []);
  const load = useCallback(async () => {
    const latest = ++requestId.current;
    const params = new URLSearchParams({ page: String(page) });
    if (dq) params.set('q', dq);
    if (wf) params.set('workflow', wf);
    if (folder === 'fav') params.set('favorites', '1');
    else if (folder !== 'all') params.set('folder', folder);
    try {
      const data = await get<{ items: Row[]; total: number }>(`/api/optimizer/items?${params}`);
      if (latest !== requestId.current) return;
      const lastPage = Math.max(1, Math.ceil(data.total / 20));
      if (page > lastPage) { setPage(lastPage); return; }
      setRows(data.items);
      setTotal(data.total);
    } catch (error) {
      if (latest !== requestId.current) return;
      fail(error);
      setRows([]);
      setTotal(0);
    }
  }, [page, dq, wf, folder, fail]);
  useEffect(() => { void loadFolders(); }, [loadFolders]);
  useEffect(() => {
    void load();
    return () => { requestId.current += 1; };
  }, [load, revision]);
  const refreshItems = () => setRevision((value) => value + 1);
  const selectFolder = (id: string) => {
    setEditMode(null);
    setPage(1);
    setFolder(id);
  };
  const current = folders.find((f) => f.id === folder);
  const openItem = async (id: string) => {
    const latest = ++itemRequestId.current;
    try {
      const item = await get<OptimizationDTO>(`/api/optimizer/items/${id}`);
      if (latest === itemRequestId.current) setOpen(item);
    } catch (error) { if (latest === itemRequestId.current) fail(error); }
  };
  const star = async (r: Row) => { try { await patch(`/api/optimizer/items/${r.id}`, { is_favorite: !r.is_favorite }); refreshItems(); } catch (e) { fail(e); } };
  const saveFolder = async () => {
    setFolderBusy(true);
    try {
      if (editMode === 'rename' && current) {
        await patch(`/api/optimizer/folders/${current.id}`, { name });
      } else if (editMode === 'create') {
        const created = await post<FolderDTO>('/api/optimizer/folders', { name });
        selectFolder(created.id);
      }
      setEditMode(null);
      await loadFolders();
    } catch (error) { fail(error); }
    finally { setFolderBusy(false); }
  };
  const folderButton = (id: string, label: string, count?: number) => (
    <button key={id} className="nav-item" aria-current={folder === id ? 'true' : undefined}
      onClick={() => selectFolder(id)}>
      <span className="library-folder-name grow">{label}</span>{count !== undefined && <span className="small tx3">{count}</span>}
    </button>
  );
  return (
    <div className="col" style={{ gap: 'var(--space-6)' }}>
      <h1>{t.library.title}</h1>
      <div className="library-layout">
        <nav className="surface card col library-folders" aria-label={t.library.folders}>
          {folderButton('all', t.library.all)}
          {folderButton('fav', t.library.favorites)}
          {folderButton('none', t.library.unfiled)}
          <div className="divider" />
          {folders.map((f) => folderButton(f.id, f.name, f.count))}
          {editMode ? (
            <form className="col" onSubmit={(event) => { event.preventDefault(); if (name.trim() && !folderBusy) void saveFolder(); }}>
              <input className="field" autoFocus aria-label={t.library.folderName} placeholder={t.library.folderName}
                maxLength={OPT_LIMITS.folderName} value={name} onChange={(event) => setName(event.target.value)}
                onKeyDown={(event) => { if (event.key === 'Escape') setEditMode(null); }} />
              <div className="row wrap">
                <button type="submit" className="btn sm primary" disabled={!name.trim() || folderBusy}>{t.common.save}</button>
                <button type="button" className="btn sm" disabled={folderBusy} onClick={() => setEditMode(null)}>{t.common.cancel}</button>
              </div>
            </form>
          ) : (
            <div className="row wrap">
              <button className="btn sm ghost" onClick={() => { setName(''); setEditMode('create'); }}><FolderPlus size={14} aria-hidden />{t.library.newFolder}</button>
              {current && !current.is_default && <>
                <button className="btn sm ghost" onClick={() => { setName(current.name); setEditMode('rename'); }}><Pencil size={14} aria-hidden />{t.library.rename}</button>
                <button className="btn sm ghost danger" onClick={() => setConfirm('folder')}><Trash2 size={14} aria-hidden />{t.common.delete}</button>
              </>}
            </div>
          )}
        </nav>
        <div className="col grow">
          <div className="row wrap">
            <input className="field grow" type="search" aria-label={t.library.search} placeholder={t.library.search} value={q} onChange={(e) => { setPage(1); setQ(e.target.value); }} />
            <select className="field" style={{ width: 'auto' }} aria-label={t.library.workflowFilter} value={wf} onChange={(e) => { setPage(1); setWf(e.target.value as OptWorkflow | ''); }}><option value="">{t.library.allWorkflows}</option>{OPT_WORKFLOWS.map((w) => <option key={w} value={w}>{t.opt.workflows[w]}</option>)}</select>
          </div>
          {rows === null ? <Skeletons /> : rows.length === 0 ? <Empty title={t.library.empty} hint={t.library.emptyHint} cta={<button className="btn primary" onClick={() => app.go('optimizer')}>{t.library.cta}</button>} /> : (
            <div className="col stagger">
              {rows.map((r) => (
                <div key={r.id} className="surface card col" style={{ gap: 'var(--space-2)' }}>
                  <div className="row spread wrap">
                    <div className="row wrap"><span className="badge">{t.opt.workflows[r.workflow]}</span>{r.has_variables && <span className="badge info">{t.library.template}</span>}
                      {r.optimized_score !== null && <span className="badge ok">{r.initial_score?.toFixed(1)} → {r.optimized_score.toFixed(1)}</span>}<span className="small tx3">{fmtDate(r.created_at)}</span></div>
                    <div className="row"><StarButton on={r.is_favorite} onClick={() => star(r)} /><button className="btn sm" onClick={() => openItem(r.id)}>{t.library.open}</button></div>
                  </div>
                  <div style={{ fontWeight: 500 }}>{r.preview}</div>
                  <div className="small tx2" style={{ overflowWrap: 'anywhere' }}>{r.prompt_preview}</div>
                  {r.tags.length > 0 && <div className="row wrap">{r.tags.map((x) => <span key={x} className="chip static">{x}</span>)}</div>}
                </div>
              ))}
              {total > 20 && <div className="row"><button className="btn sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>{t.common.prev}</button><span className="small tx2">{t.common.page} {page} / {Math.ceil(total / 20)}</span><button className="btn sm" disabled={page >= Math.ceil(total / 20)} onClick={() => setPage(page + 1)}>{t.common.next}</button></div>}
            </div>
          )}
        </div>
      </div>
      {open && <Modal title={open.raw_input.slice(0, 80)} wide onClose={() => { setOpen(null); refreshItems(); void loadFolders(); }} footer={<button className="btn danger" onClick={() => setConfirm('item')}><Trash2 size={15} aria-hidden />{t.common.delete}</button>}>
        <OptimizationView key={open.id} item={open} folders={folders} onChange={setOpen} /></Modal>}
      {confirm === 'item' && open && <ConfirmModal title={t.common.delete} text={t.library.confirmDelete} danger onClose={() => setConfirm(null)} onConfirm={async () => { try { await del(`/api/optimizer/items/${open.id}`); toast(t.library.deleted, 'ok'); setOpen(null); setConfirm(null); refreshItems(); void loadFolders(); } catch (e) { fail(e); } }} />}
      {confirm === 'folder' && current && <ConfirmModal title={t.common.delete} text={t.library.confirmDeleteFolder} danger onClose={() => setConfirm(null)} onConfirm={async () => { try { await del(`/api/optimizer/folders/${current.id}`); setConfirm(null); selectFolder('all'); void loadFolders(); } catch (e) { fail(e); } }} />}
    </div>
  );
}
