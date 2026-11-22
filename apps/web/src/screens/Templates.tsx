import { useEffect, useMemo, useState } from 'react';
import { Plus, MoreHorizontal } from 'lucide-react';
import { SYSTEM_IDS, extractVariables, substituteVariables, LIMITS, type PromptVersions, type SystemId, type TemplateDTO } from '../../../../shared/src/index.ts';
import { t } from '../strings.ru.ts';
import { get, post, patch, del, ApiError } from '../api.ts';
import { PromptActions } from '../components/PromptActions.tsx';
import { PromptFields, PromptChecklist } from '../components/PromptFields.tsx';
import { VersionHistory } from '../components/PromptVersionEditor.tsx';
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
      <div className="surface card"><input className="field" value={q} placeholder={t.common.search} aria-label={t.common.search} onChange={(e) => setQ(e.target.value)} /></div>
      {!items ? <Skeletons /> : items.length === 0 ? <Empty title={t.templates.empty} hint={t.templates.emptyHint} /> : (
        <div className="grid-cards stagger">{items.map((tp) => (
          <article key={tp.id} className="surface card hover col" style={{ position: 'relative' }}>
            <div className="row spread"><h3 style={{ fontSize: 16 }}>{tp.title}</h3><div className="row">{tp.is_seed && <span className="badge info">{t.templates.seed}</span>}<span className="badge">{tp.language.toUpperCase()}</span></div></div>
            <p className="tx2 small" style={{ margin: 0, display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>{tp.description || tp.body}</p>
            <div className="row wrap">{tp.default_systems.map((s) => <SystemChip key={s} id={s} />)}</div>
            <div className="row wrap">{tp.tags.map((x) => <span key={x} className="badge">#{x}</span>)}</div>
            <div className="row spread"><span className="small tx3">{t.templates.used} {tp.usage_count} {t.templates.times}</span>
              <div className="row"><button className="btn sm primary" onClick={() => setUsing(tp)}>{t.templates.use}</button>
                <button className="icon-btn" aria-label={t.common.more} aria-haspopup="menu" aria-expanded={menu === tp.id} onClick={() => setMenu(menu === tp.id ? null : tp.id)}><MoreHorizontal size={18} /></button></div></div>
            {menu === tp.id && <div className="surface col" role="menu" style={{ position: 'absolute', right: 12, bottom: 56, padding: 8, gap: 2, zIndex: 3 }}>
              {!tp.is_seed && <button className="nav-item" role="menuitem" onClick={() => { setMenu(null); setEditing(tp); }}>{t.common.edit}</button>}
              <button className="nav-item" role="menuitem" onClick={() => { setMenu(null); void dup(tp); }}>{t.common.duplicate}</button>
              {!tp.is_seed && <button className="nav-item" role="menuitem" style={{ color: 'var(--color-danger)' }} onClick={() => { setMenu(null); setRemoving(tp); }}>{t.common.delete}</button>}</div>}
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
    <PromptFields names={tp.variables} values={values} onChange={(name, value) => setValues((current) => ({ ...current, [name]: value }))} />
    <div><span className="label">{t.templates.preview}</span><div className="prompt-box" tabIndex={0}>{preview}</div></div>
    <PromptActions text={preview} />
    <PromptChecklist text={preview} />
  </Modal>;
}

function EditorModal({ tp, onClose, onSaved }: { tp: TemplateDTO | null; onClose: () => void; onSaved: () => void }) {
  const toast = useToast(); const [title, setTitle] = useState(tp?.title ?? ''); const [description, setDescription] = useState(tp?.description ?? ''); const [body, setBody] = useState(tp?.body ?? '');
  const [language, setLanguage] = useState<'ru' | 'en'>(tp?.language ?? 'ru'); const [systems, setSystems] = useState<SystemId[]>(tp?.default_systems ?? [...SYSTEM_IDS]); const [tags, setTags] = useState((tp?.tags ?? []).join(', ')); const [busy, setBusy] = useState(false);
  const vars = extractVariables(body);
  const tooMany = vars.length > LIMITS.maxTemplateVars;
  const [versions, setVersions] = useState<PromptVersions | null>(null);
  const [problem, setProblem] = useState('');
  const versionsUrl = tp ? `/api/templates/${tp.id}/versions` : undefined;
  useEffect(() => {
    if (!versionsUrl) return;
    let live = true;
    void get<PromptVersions>(versionsUrl).then((data) => {
      if (!live) return;
      setVersions(data);
      if (data.items[0]) setBody(data.items[0].body);
    }).catch((error) => { if (live) setProblem(error instanceof Error ? error.message : t.common.error); });
    return () => { live = false; };
  }, [versionsUrl]);
  const toggle = (id: SystemId) => setSystems((s) => (s.includes(id) ? (s.length > 1 ? s.filter((x) => x !== id) : s) : [...s, id]));
  const save = async () => {
    setBusy(true);
    setProblem('');
    const payload = { title, description, body, language, default_systems: systems, tags: tags.split(',').map((x) => x.trim()).filter(Boolean),
      expected_version: versions?.current_version };
    try { tp ? await patch(`/api/templates/${tp.id}`, payload) : await post('/api/templates', payload); toast(t.templates.saved, 'ok'); onSaved(); } catch (error) { setProblem(error instanceof Error ? error.message : t.common.error); } finally { setBusy(false); }
  };
  return <Modal title={t.templates.editor} wide onClose={onClose} footer={<><button className="btn" onClick={onClose}>{t.common.cancel}</button><button className="btn primary" disabled={busy || !!tp && !versions || !title.trim() || !body.trim() || tooMany} onClick={save}>{busy && <Spinner />}{t.common.save}</button></>}>
    {problem && <p className="banner err" role="alert">{problem}</p>}
    <div><label className="label" htmlFor="e-title">{t.templates.titleField}</label><input id="e-title" className="field" value={title} maxLength={120} onChange={(e) => setTitle(e.target.value)} /></div>
    <div><label className="label" htmlFor="e-desc">{t.templates.descField}</label><input id="e-desc" className="field" value={description} maxLength={400} onChange={(e) => setDescription(e.target.value)} /></div>
    <div><label className="label" htmlFor="e-body">{t.templates.bodyField}</label>
      <textarea id="e-body" className="field mono" rows={9} maxLength={LIMITS.template} value={body}
        disabled={!!tp && !versions} onChange={(event) => setBody(event.target.value)} />
      <div className="row wrap small">
        <span className="tx3">{t.templates.variables}</span>{vars.map((variable) => <span key={variable} className="badge">{variable}</span>)}
        {tooMany && <span className="badge err">{t.templates.maxVars}</span>}
      </div>
    </div>
    {versions && versionsUrl && <VersionHistory url={versionsUrl} current={versions} onSelect={setBody} />}
    <div className="row wrap" style={{ gap: 16 }}><Seg label="language" value={language} onChange={setLanguage} options={[{ value: 'ru', label: 'RU' }, { value: 'en', label: 'EN' }]} />
      <div className="row wrap">{SYSTEM_IDS.map((id) => <button key={id} type="button" className={`chip ${systems.includes(id) ? 'on' : ''}`} aria-pressed={systems.includes(id)} onClick={() => toggle(id)}>{id}</button>)}</div></div>
    <div><label className="label" htmlFor="e-tags">{t.templates.tagsField}</label><input id="e-tags" className="field" value={tags} onChange={(e) => setTags(e.target.value)} /></div>
  </Modal>;
}
