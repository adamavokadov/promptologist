import { useEffect, useMemo, useRef, useState } from 'react';
import { Plus, MoreHorizontal, Sparkles } from 'lucide-react';
import { SYSTEM_IDS, extractVariables, substituteVariables, LIMITS, type SystemId, type TemplateDTO } from '../../../../shared/src/index.ts';
import { t } from '../strings.ru.ts';
import { get, post, patch, del, ApiError } from '../api.ts';
import { useApp } from '../context.tsx';
import { Empty, Skeletons, Modal, ConfirmModal, SystemChip, Spinner, Seg, useToast, useDebounced } from '../ui.tsx';

export function TemplatesScreen() {
  const toast = useToast(); const app = useApp();
  const [q, setQ] = useState(''); const dq = useDebounced(q); const [items, setItems] = useState<TemplateDTO[] | null>(null);
  const [using, setUsing] = useState<TemplateDTO | null>(null); const [editing, setEditing] = useState<TemplateDTO | 'new' | null>(null); const [removing, setRemoving] = useState<TemplateDTO | null>(null); const [menu, setMenu] = useState<string | null>(null);
  const load = () => get<{ items: TemplateDTO[] }>(`/api/templates${dq ? `?q=${encodeURIComponent(dq)}` : ''}`).then((d) => setItems(d.items)).catch((e) => toast((e as ApiError).message, 'err'));
  useEffect(() => { void load(); }, [dq]); // eslint-disable-line react-hooks/exhaustive-deps
  const dup = async (tp: TemplateDTO) => { try { await post(`/api/templates/${tp.id}/duplicate`); await load(); } catch (e) { toast((e as ApiError).message, 'err'); } };
  const remove = async (tp: TemplateDTO) => { try { await del(`/api/templates/${tp.id}`); await load(); } catch (e) { toast((e as ApiError).message, 'err'); } };
  return (
    <div className="col" style={{ gap: 16 }}>
      <div className="row spread wrap"><h1>{t.templates.title}</h1><button className="btn primary" onClick={() => setEditing('new')}><Plus size={17} />{t.templates.new}</button></div>
      <div className="glass card"><input className="inset-field" value={q} placeholder={t.common.search} aria-label={t.common.search} onChange={(e) => setQ(e.target.value)} /></div>
      {!items ? <Skeletons /> : items.length === 0 ? <Empty title={t.templates.empty} hint={t.templates.emptyHint} /> : (
        <div className="grid-cards stagger">{items.map((tp) => (
          <article key={tp.id} className="glass card hover col" style={{ position: 'relative' }}>
            <div className="row spread"><h3 style={{ fontSize: 16 }}>{tp.title}</h3><div className="row">{tp.is_seed && <span className="badge info">{t.templates.seed}</span>}<span className="badge">{tp.language.toUpperCase()}</span></div></div>
            <p className="tx2 small" style={{ margin: 0, display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>{tp.description || tp.body}</p>
            <div className="row wrap">{tp.default_systems.map((s) => <SystemChip key={s} id={s} />)}</div>
            <div className="row wrap">{tp.tags.map((x) => <span key={x} className="badge">#{x}</span>)}</div>
            <div className="row spread"><span className="small tx3">{t.templates.used} {tp.usage_count} {t.templates.times}</span>
              <div className="row"><button className="btn sm primary" onClick={() => setUsing(tp)}>{t.templates.use}</button>
                <button className="icon-btn" aria-label={t.common.more} aria-haspopup="menu" aria-expanded={menu === tp.id} onClick={() => setMenu(menu === tp.id ? null : tp.id)}><MoreHorizontal size={18} /></button></div></div>
            {menu === tp.id && <div className="glass dense col" role="menu" style={{ position: 'absolute', right: 12, bottom: 56, padding: 8, gap: 2, zIndex: 3 }}>
              {!tp.is_seed && <button className="nav-item" role="menuitem" onClick={() => { setMenu(null); setEditing(tp); }}>{t.common.edit}</button>}
              <button className="nav-item" role="menuitem" onClick={() => { setMenu(null); void dup(tp); }}>{t.common.duplicate}</button>
              {!tp.is_seed && <button className="nav-item" role="menuitem" style={{ color: 'var(--err)' }} onClick={() => { setMenu(null); setRemoving(tp); }}>{t.common.delete}</button>}</div>}
          </article>))}</div>)}
      {using && <UseModal tp={using} onClose={() => setUsing(null)} onGo={(text) => { app.setPrefill({ raw_input: text, systems: using.default_systems, language: using.language }); setUsing(null); void load(); }} />}
      {editing && <EditorModal tp={editing === 'new' ? null : editing} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); void load(); }} />}
      {removing && <ConfirmModal title={t.common.delete} text={t.templates.confirmDelete} danger onConfirm={() => remove(removing)} onClose={() => setRemoving(null)} />}
    </div>
  );
}

function UseModal({ tp, onClose, onGo }: { tp: TemplateDTO; onClose: () => void; onGo: (text: string) => void }) {
  const toast = useToast(); const [values, setValues] = useState<Record<string, string>>({}); const [busy, setBusy] = useState(false);
  const preview = useMemo(() => substituteVariables(tp.body, values), [tp.body, values]);
  const go = async () => { setBusy(true); try { const r = await post<{ text: string }>(`/api/templates/${tp.id}/use`, { values }); onGo(r.text); } catch (e) { toast((e as ApiError).message, 'err'); } finally { setBusy(false); } };
  return <Modal title={`${t.templates.useTitle}: ${tp.title}`} wide onClose={onClose} footer={<><button className="btn" onClick={onClose}>{t.common.cancel}</button><button className="btn primary" disabled={busy} onClick={go}>{busy && <Spinner />}{t.templates.toGenerator}</button></>}>
    {tp.variables.map((v) => <div key={v}><label className="label" htmlFor={`v-${v}`}>{v}</label>{/(notes|text|error|body|content)/.test(v)
      ? <textarea id={`v-${v}`} className="inset-field" rows={4} value={values[v] ?? ''} onChange={(e) => setValues({ ...values, [v]: e.target.value })} />
      : <input id={`v-${v}`} className="inset-field" value={values[v] ?? ''} onChange={(e) => setValues({ ...values, [v]: e.target.value })} />}</div>)}
    <div><span className="label">{t.templates.preview}</span><div className="prompt-box">{preview}</div></div>
  </Modal>;
}

function EditorModal({ tp, onClose, onSaved }: { tp: TemplateDTO | null; onClose: () => void; onSaved: () => void }) {
  const toast = useToast(); const [title, setTitle] = useState(tp?.title ?? ''); const [description, setDescription] = useState(tp?.description ?? ''); const [body, setBody] = useState(tp?.body ?? '');
  const [language, setLanguage] = useState<'ru' | 'en'>(tp?.language ?? 'ru'); const [systems, setSystems] = useState<SystemId[]>(tp?.default_systems ?? [...SYSTEM_IDS]); const [tags, setTags] = useState((tp?.tags ?? []).join(', ')); const [busy, setBusy] = useState(false);
  const bd = useRef<HTMLDivElement>(null); const vars = extractVariables(body); const tooMany = vars.length > LIMITS.maxTemplateVars;
  const hl = body.split(/(\{\{\s*[a-z0-9_]+\s*\}\})/g).map((p, i) => (/^\{\{/.test(p) ? <mark key={i} style={{ background: 'rgba(124,92,255,.35)', color: 'transparent', borderRadius: 4 }}>{p}</mark> : <span key={i}>{p}</span>));
  const toggle = (id: SystemId) => setSystems((s) => (s.includes(id) ? (s.length > 1 ? s.filter((x) => x !== id) : s) : [...s, id]));
  const save = async () => {
    setBusy(true); const payload = { title, description, body, language, default_systems: systems, tags: tags.split(',').map((x) => x.trim()).filter(Boolean) };
    try { tp ? await patch(`/api/templates/${tp.id}`, payload) : await post('/api/templates', payload); toast(t.templates.saved, 'ok'); onSaved(); } catch (e) { toast((e as ApiError).message, 'err'); } finally { setBusy(false); }
  };
  const mono = { fontFamily: "'JetBrains Mono', monospace", fontSize: 13, lineHeight: 1.6, padding: 12, whiteSpace: 'pre-wrap' as const, wordBreak: 'break-word' as const, border: '1px solid transparent' };
  return <Modal title={t.templates.editor} wide onClose={onClose} footer={<><button className="btn" onClick={onClose}>{t.common.cancel}</button><button className="btn primary" disabled={busy || !title.trim() || !body.trim() || tooMany} onClick={save}>{busy && <Spinner />}{t.common.save}</button></>}>
    <div><label className="label" htmlFor="e-title">{t.templates.titleField}</label><input id="e-title" className="inset-field" value={title} maxLength={120} onChange={(e) => setTitle(e.target.value)} /></div>
    <div><label className="label" htmlFor="e-desc">{t.templates.descField}</label><input id="e-desc" className="inset-field" value={description} maxLength={400} onChange={(e) => setDescription(e.target.value)} /></div>
    <div><label className="label" htmlFor="e-body">{t.templates.bodyField}</label>
      <div style={{ position: 'relative', background: 'var(--inset)', borderRadius: 14, border: '1px solid var(--glass-border)' }}>
        <div ref={bd} aria-hidden style={{ ...mono, position: 'absolute', inset: 0, overflow: 'hidden', pointerEvents: 'none', color: 'transparent' }}>{hl}{'\n'}</div>
        <textarea id="e-body" rows={9} value={body} onChange={(e) => setBody(e.target.value)} onScroll={(e) => { if (bd.current) bd.current.scrollTop = e.currentTarget.scrollTop; }}
          style={{ ...mono, position: 'relative', width: '100%', background: 'transparent', color: 'var(--tx)', outline: 'none', resize: 'vertical', borderRadius: 14, display: 'block' }} /></div>
      <div className="row wrap small" style={{ marginTop: 6 }}><span className="tx3">{t.templates.variables}:</span>{vars.map((v) => <span key={v} className="badge">{`{{${v}}}`}</span>)}{tooMany && <span style={{ color: 'var(--err)' }}>{t.templates.maxVars}</span>}</div></div>
    <div className="row wrap" style={{ gap: 16 }}><Seg label="language" value={language} onChange={setLanguage} options={[{ value: 'ru', label: 'RU' }, { value: 'en', label: 'EN' }]} />
      <div className="row wrap">{SYSTEM_IDS.map((id) => <button key={id} type="button" className={`chip ${systems.includes(id) ? 'on' : ''}`} aria-pressed={systems.includes(id)} onClick={() => toggle(id)}>{id}</button>)}</div></div>
    <div><label className="label" htmlFor="e-tags">{t.templates.tagsField}</label><input id="e-tags" className="inset-field" value={tags} onChange={(e) => setTags(e.target.value)} /></div>
  </Modal>;
}
void Sparkles;
