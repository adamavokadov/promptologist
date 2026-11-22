import { useCallback, useEffect, useState } from 'react';
import { RefreshCw } from 'lucide-react';
import { SYSTEM_NAMES, type SkillDTO, type SystemId } from '../../../../shared/src/index.ts';
import { t } from '../strings.ru.ts';
import { get, post, patch, ApiError } from '../api.ts';
import { useApp } from '../context.tsx';
import { Skeletons, Drawer, ConfirmModal, Markdown, Switch, SystemDot, Spinner, useToast, daysFrom, fmtDate } from '../ui.tsx';

interface VersionRow { id: string; version: number; origin: 'seed' | 'agent' | 'rollback'; created_at: string; is_current: boolean; changelog: { change: string; reason: string; source_url: string }[]; verdict: string | null }
interface SkillDetail { skill: SkillDTO; version: { id: string; version: number; body_md: string; changelog: { change: string; reason: string; source_url: string }[]; sources: { url: string; title: string; checked_at: string }[]; frontmatter: Record<string, any> } }

const statusDot = (s: SkillDTO['status']) => (s === 'fresh' ? 'ok' : s === 'running' ? 'run' : s === 'failed' ? 'err' : s === 'due' ? 'warn' : '');

export function SkillsScreen() {
  const app = useApp(); const toast = useToast(); const admin = !!app.me?.is_admin;
  const [items, setItems] = useState<SkillDTO[] | null>(null); const [open, setOpen] = useState<SystemId | null>(null); const [busy, setBusy] = useState<string | null>(null);
  const load = useCallback(() => get<{ items: SkillDTO[] }>('/api/skills').then((d) => setItems(d.items)).catch((e) => toast((e as ApiError).message, 'err')), []); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { void load(); }, [load]);
  useEffect(() => { if (!items?.some((s) => s.status === 'running')) return; const id = setInterval(() => void load(), 5000); return () => clearInterval(id); }, [items, load]);
  const refresh = async (s: SkillDTO) => { setBusy(s.id); try { await post(`/api/skills/${s.id}/refresh`); toast(t.skills.started, 'ok'); await load(); } catch (e) { toast((e as ApiError).message, 'err'); } finally { setBusy(null); } };
  const pause = async (s: SkillDTO, v: boolean) => { try { await patch(`/api/skills/${s.id}`, { paused: v }); await load(); } catch (e) { toast((e as ApiError).message, 'err'); } };
  const checkAll = async () => { try { await post('/api/skills/refresh-all'); toast(t.skills.started, 'ok'); await load(); } catch (e) { toast((e as ApiError).message, 'err'); } };
  return (
    <div className="col" style={{ gap: 16 }}>
      <div className="row spread wrap"><h1>{t.skills.title}</h1><button className="btn" disabled={!admin} title={admin ? '' : t.common.noAccess} onClick={checkAll}><RefreshCw size={16} />{t.skills.refreshAll}</button></div>
      {!items ? <Skeletons n={5} h={150} /> : <div className="grid-cards stagger">{items.map((s) => {
        const last = daysFrom(s.last_check_at); const next = daysFrom(s.next_check_at);
        const tip = !admin ? t.common.noAccess : s.refresh_blocked_reason === 'cooldown' ? t.skills.cooldown : s.refresh_blocked_reason === 'busy' ? t.skills.busy : '';
        return <article key={s.id} className="surface card hover col">
          <div className="row spread"><div className="row"><SystemDot id={s.id} /><h3>{s.display_name}</h3><span className="badge info">v{s.current_version}</span></div>
            <span className="row small tx2"><span className={`dot ${statusDot(s.status)}`} />{t.skills.status[s.status]}</span></div>
          <p className="small tx2" style={{ margin: 0 }}>{s.model_lineup.join(' · ')}</p>
          <div className="small tx3 col" style={{ gap: 2 }}><span>{t.skills.checkedAgo}: {last === null ? t.common.never : last >= 0 ? t.common.today : `${-last} ${t.skills.ago}`}</span><span>{t.skills.nextCheck}: {next === null ? '—' : `${t.skills.approx}${Math.max(0, next)} ${t.agent.days}`}</span></div>
          <div className="row spread"><div className="row"><button className="btn sm" onClick={() => setOpen(s.id)}>{t.common.open}</button>
            <button className="btn sm" disabled={!admin || !s.can_refresh || busy === s.id} title={tip} onClick={() => refresh(s)}>{busy === s.id || s.status === 'running' ? <Spinner /> : <RefreshCw size={14} />}{t.skills.checkNow}</button></div>
            <div className="row small tx2"><span>{t.skills.pause}</span><Switch on={s.paused} onChange={(v) => pause(s, v)} label={`${t.skills.pause}: ${s.display_name}`} disabled={!admin} /></div></div>
        </article>; })}</div>}
      {open && <SkillDrawer id={open} admin={admin} onClose={() => setOpen(null)} onChanged={load} />}
    </div>
  );
}

function SkillDrawer({ id, admin, onClose, onChanged }: { id: SystemId; admin: boolean; onClose: () => void; onChanged: () => void }) {
  const toast = useToast(); const [tab, setTab] = useState<'skill' | 'versions' | 'sources'>('skill'); const [d, setD] = useState<SkillDetail | null>(null); const [vers, setVers] = useState<VersionRow[]>([]);
  const [sel, setSel] = useState<number[]>([]); const [diff, setDiff] = useState<{ from: number; to: number; parts: { added: boolean; removed: boolean; value: string }[] } | null>(null); const [rb, setRb] = useState<VersionRow | null>(null);
  const load = useCallback(() => { get<SkillDetail>(`/api/skills/${id}`).then(setD); get<{ items: VersionRow[] }>(`/api/skills/${id}/versions`).then((x) => setVers(x.items)); }, [id]);
  useEffect(load, [load]);
  useEffect(() => { if (sel.length === 2) { const [a, b] = [...sel].sort((x, y) => x - y); get<any>(`/api/skills/${id}/versions/${a}/diff/${b}`).then(setDiff).catch((e) => toast((e as ApiError).message, 'err')); } else setDiff(null); }, [sel, id]); // eslint-disable-line react-hooks/exhaustive-deps
  const rollback = async (v: VersionRow) => { try { await post(`/api/skills/${id}/rollback`, { version_id: v.id }); load(); onChanged(); } catch (e) { toast((e as ApiError).message, 'err'); } };
  const toggleSel = (n: number) => setSel((s) => (s.includes(n) ? s.filter((x) => x !== n) : [...s, n].slice(-2)));
  return (
    <Drawer title={<span className="row"><SystemDot id={id} />{SYSTEM_NAMES[id]} {d && <span className="badge info">v{d.skill.current_version}</span>}</span>} onClose={onClose}>
      {!d ? <Skeletons n={2} h={140} /> : <div className="col">
        {d.version.changelog.length > 0 && <div className="surface card"><span className="label">{t.skills.changelog}</span><ul className="tx2 small" style={{ margin: 0, paddingLeft: 18 }}>{d.version.changelog.map((c, i) => <li key={i}>{c.change}</li>)}</ul></div>}
        <div className="row wrap" role="tablist">{(['skill', 'versions', 'sources'] as const).map((k) => <button key={k} role="tab" aria-selected={tab === k} className={`tab ${tab === k ? 'on' : ''}`} onClick={() => setTab(k)}>{t.skills.tabs[k]}</button>)}</div>
        {tab === 'skill' && <><div className="small tx3">{t.skills.lineup}: {d.skill.model_lineup.join(' · ')}</div><Markdown md={d.version.body_md} /></>}
        {tab === 'versions' && <div className="col">
          <p className="small tx3" style={{ margin: 0 }}>{t.skills.pickTwo}</p>
          {vers.map((v) => <div key={v.id} className="surface card row wrap" style={{ padding: 12 }}>
            <input type="checkbox" checked={sel.includes(v.version)} onChange={() => toggleSel(v.version)} aria-label={`${t.skills.diff} v${v.version}`} />
            <strong>v{v.version}</strong><span className="badge">{t.skills.origin[v.origin]}</span>{v.is_current && <span className="badge ok">{t.skills.current}</span>}<span className="small tx3 grow">{fmtDate(v.created_at)}</span>
            {!v.is_current && <button className="btn sm" disabled={!admin} title={admin ? '' : t.common.noAccess} onClick={() => setRb(v)}>{t.skills.rollback}</button>}</div>)}
          {diff && <div className="prompt-box full" aria-label={`${t.skills.diff} v${diff.from} → v${diff.to}`}>{diff.parts.map((p, i) => <div key={i} className={p.added ? 'diff-add' : p.removed ? 'diff-del' : ''} style={{ opacity: !p.added && !p.removed ? 0.7 : 1 }}>{p.value.split('\n').filter((l, j, a) => j < a.length - 1 || l).map((l, j) => <div key={j}>{p.added ? '+ ' : p.removed ? '- ' : '  '}{l}</div>)}</div>)}</div>}
        </div>}
        {tab === 'sources' && <div className="col">{d.version.sources.length === 0 ? <p className="tx3">—</p> : d.version.sources.map((s) => <div key={s.url} className="surface card" style={{ padding: 12 }}><a href={s.url} target="_blank" rel="noopener noreferrer">{s.title || s.url}</a><div className="small tx3">{new URL(s.url).hostname} · {s.checked_at}</div></div>)}</div>}
      </div>}
      {rb && <ConfirmModal title={`${t.skills.rollback} v${rb.version}`} text={t.skills.rollbackConfirm} onConfirm={() => rollback(rb)} onClose={() => setRb(null)} />}
    </Drawer>
  );
}
