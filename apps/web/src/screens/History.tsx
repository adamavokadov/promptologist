import { useCallback, useEffect, useState } from 'react';
import { Trash2, RotateCcw } from 'lucide-react';
import { SYSTEM_NAMES, type GenerationDTO, type ResultDTO, type SystemId } from '../../../../shared/src/index.ts';
import { t } from '../strings.ru.ts';
import { get, del, patch, post, ApiError } from '../api.ts';
import { useApp } from '../context.tsx';
import { Empty, Skeletons, Drawer, ConfirmModal, SystemChip, useToast, useDebounced, fmtDate } from '../ui.tsx';
import { ResultCard, groupBySystem } from '../components/ResultCard.tsx';
import { TemplateSaveModal } from '../components/TemplateSaveModal.tsx';

interface Item { id: string; created_at: string; preview: string; language: 'ru' | 'en'; status: string; systems: SystemId[]; cards: number; has_favorite: boolean }

export function HistoryScreen() {
  const app = useApp(); const toast = useToast();
  const [q, setQ] = useState(''); const dq = useDebounced(q); const [system, setSystem] = useState<SystemId | ''>(''); const [language, setLanguage] = useState(''); const [fav, setFav] = useState(false); const [from, setFrom] = useState(''); const [to, setTo] = useState('');
  const [page, setPage] = useState(1); const [data, setData] = useState<{ items: Item[]; total: number } | null>(null); const [openId, setOpenId] = useState<string | null>(app.openGenerationId); const [reload, setReload] = useState(0);
  useEffect(() => { setPage(1); }, [dq, system, language, fav, from, to]);
  useEffect(() => {
    const p = new URLSearchParams({ page: String(page) }); if (dq) p.set('q', dq); if (system) p.set('system', system); if (language) p.set('language', language); if (fav) p.set('favorites', '1'); if (from) p.set('from', from); if (to) p.set('to', to);
    let alive = true; get<{ items: Item[]; total: number }>(`/api/generations?${p}`).then((d) => alive && setData(d)).catch((e) => toast((e as ApiError).message, 'err'));
    return () => { alive = false; };
  }, [dq, system, language, fav, from, to, page, reload]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (app.openGenerationId) { setOpenId(app.openGenerationId); app.clearOpenGeneration(); } }, [app.openGenerationId]); // eslint-disable-line react-hooks/exhaustive-deps
  const pages = data ? Math.max(1, Math.ceil(data.total / 20)) : 1;
  return (
    <div className="col" style={{ gap: 16 }}>
      <h1>{t.history.title}</h1>
      <div className="surface card row wrap" style={{ gap: 12 }}>
        <input className="field" style={{ flex: '2 1 220px' }} value={q} placeholder={t.history.searchPlaceholder} aria-label={t.common.search} onChange={(e) => setQ(e.target.value)} />
        <select className="field" style={{ flex: '1 1 130px' }} value={system} aria-label={t.gen.systems} onChange={(e) => setSystem(e.target.value as SystemId | '')}><option value="">{t.common.all}</option>{Object.entries(SYSTEM_NAMES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>
        <select className="field" style={{ flex: '1 1 100px' }} value={language} aria-label={t.history.language} onChange={(e) => setLanguage(e.target.value)}><option value="">{t.history.language}: {t.common.all}</option><option value="ru">RU</option><option value="en">EN</option></select>
        <input className="field" style={{ flex: '1 1 140px' }} type="date" value={from} aria-label={t.history.from} onChange={(e) => setFrom(e.target.value)} />
        <input className="field" style={{ flex: '1 1 140px' }} type="date" value={to} aria-label={t.history.to} onChange={(e) => setTo(e.target.value)} />
        <label className="row small"><input type="checkbox" checked={fav} onChange={(e) => setFav(e.target.checked)} />{t.history.onlyFav}</label>
      </div>
      {!data ? <Skeletons /> : data.items.length === 0 ? <Empty title={t.history.empty} hint={t.history.emptyHint} cta={<button className="btn primary" onClick={() => app.go('generator')}>{t.history.cta}</button>} /> : (
        <div className="col stagger">{data.items.map((g) => (
          <button key={g.id} className="surface card hover row wrap" style={{ textAlign: 'left', color: 'inherit', cursor: 'pointer', font: 'inherit' }} onClick={() => setOpenId(g.id)}>
            <div className="col grow" style={{ gap: 8 }}><span className="small tx3">{fmtDate(g.created_at)}</span><span>{g.preview}</span><div className="row wrap">{g.systems.map((s) => <SystemChip key={s} id={s} />)}</div></div>
            <span className="badge">{g.language.toUpperCase()}</span><span className="badge ok">{g.cards} {t.history.cards}</span>{g.has_favorite && <span className="badge warn">★</span>}
          </button>))}
          {pages > 1 && <div className="row" style={{ justifyContent: 'center' }}><button className="btn sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>{t.common.prev}</button><span className="small tx2">{t.common.page} {page} / {pages}</span><button className="btn sm" disabled={page >= pages} onClick={() => setPage(page + 1)}>{t.common.next}</button></div>}
        </div>)}
      {openId && <GenerationDrawer id={openId} onClose={() => setOpenId(null)} onChanged={() => setReload((x) => x + 1)} />}
    </div>
  );
}

export function GenerationDrawer({ id, onClose, onChanged }: { id: string; onClose: () => void; onChanged: () => void }) {
  const app = useApp(); const toast = useToast();
  const [g, setG] = useState<GenerationDTO | null>(null); const [confirm, setConfirm] = useState(false); const [tpl, setTpl] = useState<ResultDTO | null>(null); const [busy, setBusy] = useState<string | null>(null);
  const load = useCallback(() => { get<GenerationDTO>(`/api/generations/${id}`).then(setG).catch((e) => { toast((e as ApiError).message, 'err'); onClose(); }); }, [id]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(load, [load]);
  const favorite = async (r: ResultDTO, v: boolean) => { try { await patch(`/api/results/${r.id}/favorite`, { value: v }); load(); onChanged(); } catch (e) { toast((e as ApiError).message, 'err'); } };
  const regenerate = async (r: ResultDTO, feedback: string) => { setBusy(r.skill_id); try { await post(`/api/generations/${r.generation_id}/results/${r.id}/regenerate`, feedback ? { feedback } : {}); load(); } catch (e) { toast((e as ApiError).message, 'err'); } finally { setBusy(null); } };
  const remove = async () => { try { await del(`/api/generations/${id}`); toast(t.history.deleted, 'ok'); onChanged(); onClose(); } catch (e) { toast((e as ApiError).message, 'err'); } };
  const groups = g ? [...groupBySystem(g.results)] : [];
  return (
    <Drawer title={t.history.title} onClose={onClose}>
      {!g ? <Skeletons n={2} h={160} /> : <div className="col">
        <div className="surface card col"><span className="small tx3">{fmtDate(g.created_at)} · {g.language.toUpperCase()}</span><p style={{ margin: 0, whiteSpace: 'pre-wrap' }}>{g.raw_input}</p>
          <div className="row wrap"><button className="btn sm primary" onClick={() => { app.setPrefill({ raw_input: g.raw_input, systems: groups.map(([s]) => s), language: g.language, options: g.options }); onClose(); }}><RotateCcw size={15} />{t.common.reuse}</button>
            <button className="btn sm danger" onClick={() => setConfirm(true)}><Trash2 size={15} />{t.common.delete}</button></div></div>
        {groups.map(([s, vs]) => <ResultCard key={s} system={s} variants={vs} busy={busy === s} onFavorite={favorite} onRegenerate={regenerate} onTemplate={setTpl} />)}
      </div>}
      {confirm && <ConfirmModal title={t.common.delete} text={t.history.confirmDelete} danger onConfirm={remove} onClose={() => setConfirm(false)} />}
      {tpl && g && <TemplateSaveModal prompt={tpl.prompt_text} language={g.language} systems={[tpl.skill_id]} onClose={() => setTpl(null)} />}
    </Drawer>
  );
}
