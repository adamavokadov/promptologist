import { useEffect, useState } from 'react';
import { SYSTEM_NAMES, type SystemId } from '../../../../shared/src/index.ts';
import { t } from '../strings.ru.ts';
import { get, ApiError } from '../api.ts';
import { Empty, Skeletons, SystemDot, useToast, fmtDate } from '../ui.tsx';

interface Report { id: string; skill_id: SystemId; verdict: keyof typeof t.reports.verdict; summary_ru: string; changelog: { change: string; reason: string; source_url: string }[]; sources: { url: string; title: string; date: string | null }[]; golden: { task: string; winner: string; verdict: { scores: Record<string, number> } | null }[] | null; budget: { search: number; research: number; llm: number; tokens: number } | null; version_from: number | null; version_to: number | null; created_at: string }
const tone = (v: string) => (v === 'updated' ? 'ok' : v === 'no_changes' ? 'info' : v === 'rolled_back' || v === 'rejected' ? 'warn' : 'err');

export function ReportsScreen() {
  const toast = useToast(); const [items, setItems] = useState<Report[] | null>(null); const [skill, setSkill] = useState(''); const [verdict, setVerdict] = useState(''); const [page, setPage] = useState(1); const [open, setOpen] = useState<string | null>(null);
  useEffect(() => { setPage(1); }, [skill, verdict]);
  useEffect(() => { const p = new URLSearchParams({ page: String(page) }); if (skill) p.set('skill', skill); if (verdict) p.set('verdict', verdict); get<{ items: Report[] }>(`/api/reports?${p}`).then((d) => setItems(d.items)).catch((e) => toast((e as ApiError).message, 'err')); }, [skill, verdict, page]); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <div className="col" style={{ gap: 16 }}>
      <h1>{t.reports.title}</h1>
      <div className="glass card row wrap" style={{ gap: 12 }}>
        <select className="inset-field" style={{ flex: '1 1 160px' }} value={skill} aria-label={t.gen.systems} onChange={(e) => setSkill(e.target.value)}><option value="">{t.common.all}</option>{Object.entries(SYSTEM_NAMES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>
        <select className="inset-field" style={{ flex: '1 1 180px' }} value={verdict} aria-label={t.reports.allVerdicts} onChange={(e) => setVerdict(e.target.value)}><option value="">{t.reports.allVerdicts}</option>{Object.entries(t.reports.verdict).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>
      </div>
      {!items ? <Skeletons /> : items.length === 0 ? <Empty title={t.reports.empty} hint={t.reports.emptyHint} /> : <div className="col stagger">{items.map((r) => (
        <article key={r.id} className="glass card col">
          <button className="row wrap" style={{ background: 'none', border: 0, color: 'inherit', font: 'inherit', textAlign: 'left', cursor: 'pointer', padding: 0 }} onClick={() => setOpen(open === r.id ? null : r.id)} aria-expanded={open === r.id}>
            <SystemDot id={r.skill_id} /><strong>{SYSTEM_NAMES[r.skill_id]}</strong><span className={`badge ${tone(r.verdict)}`}>{r.verdict === 'updated' && r.version_to ? `${t.reports.verdict.updated} → v${r.version_to}` : t.reports.verdict[r.verdict] ?? r.verdict}</span><span className="grow" /><span className="small tx3">{fmtDate(r.created_at)}</span></button>
          <p className="tx2" style={{ margin: 0 }}>{r.summary_ru}</p>
          {r.changelog.length > 0 && <ul className="small tx2" style={{ margin: 0, paddingLeft: 18 }}>{r.changelog.map((c, i) => <li key={i}>{c.change}</li>)}</ul>}
          {r.sources.length > 0 && <div className="row wrap">{r.sources.slice(0, 6).map((s) => <a key={s.url} className="chip static" href={s.url} target="_blank" rel="noopener noreferrer">{new URL(s.url).hostname}{s.date ? ` · ${s.date.slice(0, 10)}` : ''}</a>)}</div>}
          {open === r.id && <div className="col small tx2">
            {r.golden && <div><span className="label">{t.reports.golden}</span>{r.golden.map((g) => <div key={g.task} className="row wrap"><span className="badge">{g.task}</span><span className={`badge ${g.winner === 'old' ? 'err' : 'ok'}`}>{g.winner}</span>{g.verdict && <span className="mono">{Object.entries(g.verdict.scores).map(([k, v]) => `${k}:${v}`).join(' ')}</span>}</div>)}</div>}
            {r.budget && <div><span className="label">{t.reports.budget}</span><span className="mono">search {r.budget.search} · research {r.budget.research} · llm {r.budget.llm} · {r.budget.tokens} {t.reports.tokens}</span></div>}
          </div>}
        </article>))}
        <div className="row" style={{ justifyContent: 'center' }}><button className="btn sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>{t.common.prev}</button><span className="small tx2">{t.common.page} {page}</span><button className="btn sm" disabled={items.length < 20} onClick={() => setPage(page + 1)}>{t.common.next}</button></div></div>}
    </div>
  );
}
