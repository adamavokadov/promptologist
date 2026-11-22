import { useCallback, useEffect, useState } from 'react';
import { FolderPlus, Pencil, Trash2 } from 'lucide-react';
import { OPT_WORKFLOWS, type FolderDTO, type OptWorkflow, type OptimizationDTO } from '../../../../shared/src/index.ts';
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
  const [name, setName] = useState(''); const [adding, setAdding] = useState(false);
  const fail = (e: unknown) => toast((e as ApiError).message ?? t.common.error, 'err');
  const loadFolders = useCallback(() => get<{ items: FolderDTO[] }>('/api/optimizer/folders').then((d) => setFolders(d.items)).catch(() => {}), []);
  const load = useCallback(() => {
    const p = new URLSearchParams({ page: String(page) }); if (dq) p.set('q', dq); if (wf) p.set('workflow', wf);
    if (folder === 'fav') p.set('favorites', '1'); else if (folder === 'none') p.set('folder', 'none'); else if (folder !== 'all') p.set('folder', folder);
    return get<{ items: Row[]; total: number }>(`/api/optimizer/items?${p}`).then((d) => { setRows(d.items); setTotal(d.total); }).catch((e) => { fail(e); setRows([]); });
  }, [page, dq, wf, folder]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { void loadFolders(); }, [loadFolders]);
  useEffect(() => { setPage(1); }, [dq, wf, folder]);
  useEffect(() => { void load(); }, [load]);
  const current = folders.find((f) => f.id === folder);
  const openItem = async (id: string) => { try { setOpen(await get<OptimizationDTO>(`/api/optimizer/items/${id}`)); } catch (e) { fail(e); } };
  const star = async (r: Row) => { try { await patch(`/api/optimizer/items/${r.id}`, { is_favorite: !r.is_favorite }); void load(); } catch (e) { fail(e); } };
  const addFolder = async () => { try { const f = await post<FolderDTO>('/api/optimizer/folders', { name }); setName(''); setAdding(false); await loadFolders(); setFolder(f.id); } catch (e) { fail(e); } };
  const rename = async () => { if (!current) return; const n = window.prompt(t.library.folderName, current.name); if (!n || n === current.name) return; try { await patch(`/api/optimizer/folders/${current.id}`, { name: n }); void loadFolders(); } catch (e) { fail(e); } };
  const FolderBtn = ({ id, label, count }: { id: string; label: string; count?: number }) => <button className={`nav-item ${folder === id ? 'on' : ''}`} aria-current={folder === id ? 'true' : undefined} onClick={() => setFolder(id)}><span className="nav-label grow">{label}</span>{count !== undefined && <span className="small tx3">{count}</span>}</button>;
  void app;
  return (
    <div className="col" style={{ gap: 'var(--space-6)' }}>
      <h1>{t.library.title}</h1>
      <div className="row wrap" style={{ alignItems: 'flex-start', gap: 'var(--space-6)' }}>
        <nav className="col" style={{ width: 220, gap: 'var(--space-1)' }} aria-label={t.library.folders}>
          <FolderBtn id="all" label={t.library.all} /><FolderBtn id="fav" label={t.library.favorites} /><FolderBtn id="none" label={t.library.unfiled} />
          <div className="divider" />
          {folders.map((f) => <FolderBtn key={f.id} id={f.id} label={f.name} count={f.count} />)}
          {adding ? <div className="col" style={{ gap: 'var(--space-2)' }}><input className="inset-field" autoFocus aria-label={t.library.folderName} placeholder={t.library.folderName} maxLength={60} value={name} onChange={(e) => setName(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter' && name.trim()) void addFolder(); if (e.key === 'Escape') setAdding(false); }} />
            <div className="row"><button className="btn sm primary" disabled={!name.trim()} onClick={addFolder}>{t.common.save}</button><button className="btn sm" onClick={() => setAdding(false)}>{t.common.cancel}</button></div></div>
            : <button className="btn sm ghost" onClick={() => setAdding(true)}><FolderPlus size={14} aria-hidden />{t.library.newFolder}</button>}
          {current && !current.is_default && <div className="row"><button className="btn sm ghost" onClick={rename}><Pencil size={14} aria-hidden />{t.library.rename}</button><button className="btn sm ghost danger" onClick={() => setConfirm('folder')}><Trash2 size={14} aria-hidden />{t.common.delete}</button></div>}
        </nav>
        <div className="col grow" style={{ minWidth: 280 }}>
          <div className="row wrap">
            <input className="inset-field grow" type="search" aria-label={t.library.search} placeholder={t.library.search} value={q} onChange={(e) => setQ(e.target.value)} />
            <select className="inset-field" style={{ width: 'auto' }} aria-label={t.library.workflowFilter} value={wf} onChange={(e) => setWf(e.target.value as OptWorkflow | '')}><option value="">{t.library.allWorkflows}</option>{OPT_WORKFLOWS.map((w) => <option key={w} value={w}>{t.opt.workflows[w]}</option>)}</select>
          </div>
          {rows === null ? <Skeletons /> : rows.length === 0 ? <Empty title={t.library.empty} hint={t.library.emptyHint} cta={<button className="btn primary" onClick={() => app.go('optimizer')}>{t.library.cta}</button>} /> : (
            <div className="col stagger">
              {rows.map((r) => (
                <div key={r.id} className="glass card col" style={{ gap: 'var(--space-2)' }}>
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
      {open && <Modal title={open.raw_input.slice(0, 80)} wide onClose={() => { setOpen(null); void load(); void loadFolders(); }} footer={<button className="btn danger" onClick={() => setConfirm('item')}><Trash2 size={15} aria-hidden />{t.common.delete}</button>}>
        <OptimizationView item={open} folders={folders} onChange={setOpen} /></Modal>}
      {confirm === 'item' && open && <ConfirmModal title={t.common.delete} text={t.library.confirmDelete} danger onClose={() => setConfirm(null)} onConfirm={async () => { try { await del(`/api/optimizer/items/${open.id}`); toast(t.library.deleted, 'ok'); setOpen(null); setConfirm(null); void load(); void loadFolders(); } catch (e) { fail(e); } }} />}
      {confirm === 'folder' && current && <ConfirmModal title={t.common.delete} text={t.library.confirmDeleteFolder} danger onClose={() => setConfirm(null)} onConfirm={async () => { try { await del(`/api/optimizer/folders/${current.id}`); setConfirm(null); setFolder('all'); void loadFolders(); void load(); } catch (e) { fail(e); } }} />}
    </div>
  );
}
