import { useEffect, useState } from 'react';
import { ChevronLeft, ChevronRight, RefreshCw, FilePlus2, ChevronDown } from 'lucide-react';
import { SYSTEM_NAMES, type ResultDTO, type SystemId } from '../../../../shared/src/index.ts';
import { t } from '../strings.ru.ts';
import { PromptActions } from './PromptActions.tsx';
import { PromptChecklist } from './PromptFields.tsx';
import { PublishPrompt } from './PublishPrompt.tsx';
import { StarButton, HighlightedPrompt, SystemDot, Spinner } from '../ui.tsx';

export function groupBySystem(results: ResultDTO[]): Map<SystemId, ResultDTO[]> {
  const m = new Map<SystemId, ResultDTO[]>();
  for (const r of [...results].sort((a, b) => a.created_at.localeCompare(b.created_at))) { const l = m.get(r.skill_id) ?? []; l.push(r); m.set(r.skill_id, l); }
  return m;
}

export function ResultCard({ system, variants, loading, error, onFavorite, onRegenerate, onTemplate, busy }: {
  system: SystemId; variants: ResultDTO[]; loading?: boolean; error?: string | null; busy?: boolean;
  onFavorite: (r: ResultDTO, v: boolean) => void; onRegenerate: (r: ResultDTO, feedback: string) => void; onTemplate: (r: ResultDTO) => void;
}) {
  const [publishing, setPublishing] = useState(false);
  const [idx, setIdx] = useState(Math.max(0, variants.length - 1)); const [expanded, setExpanded] = useState(false); const [fb, setFb] = useState(''); const [fbOpen, setFbOpen] = useState(false);
  useEffect(() => { setIdx(Math.max(0, variants.length - 1)); }, [variants.length]);
  const r = variants[Math.min(idx, variants.length - 1)];
  if (loading && !r) return <div className="surface card col" aria-busy><div className="row"><SystemDot id={system} /><h3>{SYSTEM_NAMES[system]}</h3><Spinner /></div><div className="skeleton" style={{ height: 220 }} /></div>;
  if (!r) return null;
  const failed = r.status === 'failed';
  return (
    <article className="surface card col" aria-label={SYSTEM_NAMES[system]}>
      <div className="row wrap spread">
        <div className="row"><SystemDot id={system} /><h3>{SYSTEM_NAMES[system]}</h3>{!failed && <span className="badge info result-meta">{t.gen.skillBadge} v{r.skill_version}</span>}{!failed && <span className="badge result-meta">{(r.latency_ms / 1000).toFixed(1)} c</span>}</div>
        {variants.length > 1 && <div className="row" aria-label={t.gen.variant}><button className="icon-btn" aria-label={t.common.prev} disabled={idx === 0} onClick={() => setIdx(idx - 1)}><ChevronLeft size={18} /></button><span className="small tx2">{t.gen.variant} {idx + 1}/{variants.length}</span><button className="icon-btn" aria-label={t.common.next} disabled={idx >= variants.length - 1} onClick={() => setIdx(idx + 1)}><ChevronRight size={18} /></button></div>}
      </div>
      {failed ? (
        <div className="banner err" role="alert" style={{ margin: 0 }}><span className="grow">{t.gen.failed}{r.error ? `: ${r.error}` : ''}</span><button className="btn sm" disabled={busy} onClick={() => onRegenerate(r, '')}><RefreshCw size={14} />{t.common.retry}</button></div>
      ) : (<>
        <div className={`prompt-box ${expanded ? 'full' : ''}`} tabIndex={0}><HighlightedPrompt text={r.prompt_text} /></div>
        {r.prompt_text.length > 700 && <button className="btn sm ghost" style={{ alignSelf: 'flex-start' }} onClick={() => setExpanded(!expanded)}>{expanded ? t.common.collapse : t.common.expand}</button>}
        <PromptActions key={r.id} text={r.prompt_text} />
        <PromptChecklist text={r.prompt_text} />
        <details className="result-details"><summary>{t.prompt.details}</summary>
        <div className="row wrap">
          <StarButton on={r.is_favorite} onClick={() => onFavorite(r, !r.is_favorite)} />
          <button className="btn sm" onClick={() => setPublishing(true)}>{t.team.publish}</button>
          <button className="btn sm" onClick={() => onTemplate(r)}><FilePlus2 size={15} />{t.common.toTemplate}</button>
          <button className="btn sm" disabled={busy} onClick={() => setFbOpen(!fbOpen)} aria-expanded={fbOpen}>{busy ? <Spinner /> : <RefreshCw size={15} />}{t.gen.regenerate}</button>
        </div>
        {fbOpen && <div className="row"><input className="field" value={fb} maxLength={500} placeholder={t.gen.feedbackPlaceholder} onChange={(e) => setFb(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter') { onRegenerate(r, fb); setFbOpen(false); setFb(''); } }} aria-label={t.gen.feedbackPlaceholder} /><button className="btn primary sm" onClick={() => { onRegenerate(r, fb); setFbOpen(false); setFb(''); }}>{t.gen.applyFeedback}</button></div>}
        <details><summary><ChevronDown size={14} style={{ verticalAlign: -2 }} /> {t.gen.improved}</summary>
          <ul className="tx2" style={{ margin: '0 0 10px', paddingLeft: 20 }}>{r.improvements.map((x, i) => <li key={i}>{x}</li>)}</ul>
          {r.assumptions.length > 0 && <><span className="label">{t.gen.assumptionsTitle}</span><div className="row wrap" style={{ marginBottom: 10 }}>{r.assumptions.map((a, i) => <span key={i} className="chip static" style={{ whiteSpace: 'normal' }}>{a}</span>)}</div></>}
          {r.usage_notes && <><span className="label">{t.gen.usageNotes}</span><p className="tx2" style={{ margin: 0 }}>{r.usage_notes}</p></>}
        </details></details>
        {publishing && <PublishPrompt body={r.prompt_text} onClose={() => setPublishing(false)} />}
      </>)}
      {error && !failed && <p className="small" style={{ color: 'var(--color-danger)' }}>{error}</p>}
    </article>
  );
}
