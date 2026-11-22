import { useEffect, useState } from 'react';
import { ExternalLink, FilePlus2, Star } from 'lucide-react';
import { SYSTEM_NAMES, type ResultDTO, type SystemId } from '../../../../shared/src/index.ts';
import { t } from '../strings.ru.ts';
import { get, patch, ApiError } from '../api.ts';
import { useApp } from '../context.tsx';
import { Empty, Skeletons, CopyButton, SystemChip, useToast, useDebounced, fmtDate } from '../ui.tsx';
import { TemplateSaveModal } from '../components/TemplateSaveModal.tsx';

type Fav = ResultDTO & { raw_preview: string; language: 'ru' | 'en' };
export function FavoritesScreen() {
  const app = useApp(); const toast = useToast();
  const [q, setQ] = useState(''); const dq = useDebounced(q); const [system, setSystem] = useState<SystemId | ''>(''); const [items, setItems] = useState<Fav[] | null>(null); const [tpl, setTpl] = useState<Fav | null>(null);
  const load = () => { const p = new URLSearchParams(); if (dq) p.set('q', dq); if (system) p.set('system', system); get<{ items: Fav[] }>(`/api/favorites?${p}`).then((d) => setItems(d.items)).catch((e) => toast((e as ApiError).message, 'err')); };
  useEffect(load, [dq, system]); // eslint-disable-line react-hooks/exhaustive-deps
  const unstar = async (r: Fav) => { try { await patch(`/api/results/${r.id}/favorite`, { value: false }); setItems((x) => x?.filter((i) => i.id !== r.id) ?? null); } catch (e) { toast((e as ApiError).message, 'err'); } };
  return (
    <div className="col" style={{ gap: 16 }}>
      <h1>{t.favorites.title}</h1>
      <div className="glass card row wrap" style={{ gap: 12 }}>
        <input className="inset-field" style={{ flex: '2 1 240px' }} value={q} placeholder={t.common.search} aria-label={t.common.search} onChange={(e) => setQ(e.target.value)} />
        <select className="inset-field" style={{ flex: '1 1 150px' }} value={system} aria-label={t.gen.systems} onChange={(e) => setSystem(e.target.value as SystemId | '')}><option value="">{t.common.all}</option>{Object.entries(SYSTEM_NAMES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>
      </div>
      {!items ? <Skeletons /> : items.length === 0 ? <Empty title={t.favorites.empty} hint={t.favorites.emptyHint} /> : (
        <div className="grid-cards stagger">{items.map((r) => (
          <article key={r.id} className="glass card hover col">
            <div className="row spread"><SystemChip id={r.skill_id} /><span className="small tx3">{fmtDate(r.created_at)}</span></div>
            <div className="prompt-box" style={{ maxHeight: 88, overflow: 'hidden' }}>{r.prompt_text.slice(0, 260)}</div>
            <p className="small tx3" style={{ margin: 0 }}>{r.raw_preview}</p>
            <div className="row wrap"><CopyButton text={r.prompt_text} primary />
              <button className="btn sm" onClick={() => app.openGeneration(r.generation_id)}><ExternalLink size={14} />{t.favorites.open}</button>
              <button className="btn sm" onClick={() => setTpl(r)}><FilePlus2 size={14} />{t.common.toTemplate}</button>
              <button className="icon-btn" aria-label={t.common.unfavorite} onClick={() => unstar(r)}><Star size={18} fill="var(--color-warning)" color="var(--color-warning)" /></button></div>
          </article>))}</div>)}
      {tpl && <TemplateSaveModal prompt={tpl.prompt_text} language={tpl.language} systems={[tpl.skill_id]} onClose={() => setTpl(null)} />}
    </div>
  );
}
