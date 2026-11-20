import { useState } from 'react';
import { Sparkles } from 'lucide-react';
import { type SystemId } from '../../../../shared/src/index.ts';
import { t } from '../strings.ru.ts';
import { Modal, Spinner, useToast } from '../ui.tsx';
import { post, ApiError } from '../api.ts';

export function TemplateSaveModal({ prompt, language, systems, onClose, onSaved }: { prompt: string; language: 'ru' | 'en'; systems: SystemId[]; onClose: () => void; onSaved?: () => void }) {
  const [title, setTitle] = useState(''); const [description, setDescription] = useState(''); const [tags, setTags] = useState(''); const [body, setBody] = useState(prompt);
  const [busy, setBusy] = useState(false); const [gen, setGen] = useState(false); const toast = useToast();
  const generalize = async () => {
    setGen(true);
    try { const r = await post<{ title: string; description: string; body: string }>('/api/templates/generalize', { prompt }); setBody(r.body); if (!title) setTitle(r.title); if (!description) setDescription(r.description); }
    catch (e) { toast((e as ApiError).message, 'err'); } finally { setGen(false); }
  };
  const save = async () => {
    setBusy(true);
    try { await post('/api/templates', { title, description, body, language, default_systems: systems, tags: tags.split(',').map((x) => x.trim()).filter(Boolean).slice(0, 8) }); toast(t.templates.saved, 'ok'); onSaved?.(); onClose(); }
    catch (e) { toast((e as ApiError).message, 'err'); } finally { setBusy(false); }
  };
  return <Modal title={t.gen.saveTemplate} onClose={onClose} wide footer={<><button className="btn" onClick={onClose}>{t.common.cancel}</button><button className="btn primary" disabled={busy || !title.trim() || !body.trim()} onClick={save}>{busy && <Spinner />}{t.common.save}</button></>}>
    <div><label className="label" htmlFor="ts-title">{t.templates.titleField}</label><input id="ts-title" className="inset-field" value={title} maxLength={120} onChange={(e) => setTitle(e.target.value)} /></div>
    <div><label className="label" htmlFor="ts-desc">{t.templates.descField}</label><input id="ts-desc" className="inset-field" value={description} maxLength={400} onChange={(e) => setDescription(e.target.value)} /></div>
    <div><label className="label" htmlFor="ts-tags">{t.templates.tagsField}</label><input id="ts-tags" className="inset-field" value={tags} onChange={(e) => setTags(e.target.value)} /></div>
    <div><div className="row spread"><label className="label" htmlFor="ts-body">{t.templates.bodyField}</label><button className="btn sm" onClick={generalize} disabled={gen}>{gen ? <Spinner /> : <Sparkles size={14} />}{gen ? t.templates.generalizing : t.templates.generalize}</button></div>
      <textarea id="ts-body" className="inset-field mono" rows={10} value={body} onChange={(e) => setBody(e.target.value)} style={{ fontSize: 13 }} /></div>
  </Modal>;
}
