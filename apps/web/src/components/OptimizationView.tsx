import { useMemo, useState } from 'react';
import { Minimize2 } from 'lucide-react';
import { estimateTokens, OPT_LIMITS, substituteBracketVars, type FolderDTO, type OptimizationDTO } from '../../../../shared/src/index.ts';
import { t } from '../strings.ru.ts';
import { patch, post, ApiError } from '../api.ts';
import { CopyButton, Spinner, StarButton, useToast } from '../ui.tsx';

type Compressed = OptimizationDTO & { no_gain?: boolean; saved_pct?: number };

const ScoreBar = ({ label, value }: { label: string; value: number | null }) => (
  <div className="score-field">
    <div className="row spread small"><span className="tx2">{label}</span><strong className="mono">{value === null ? '—' : value.toFixed(1)}/10</strong></div>
    <div role="img" aria-label={`${label}: ${value ?? 0} / 10`} style={{ height: 'var(--space-2)', borderRadius: 'var(--radius-full)', background: 'var(--color-surface-secondary)', border: '1px solid var(--color-border)', marginTop: 'var(--space-1)' }}>
      <div style={{ width: `${Math.round(((value ?? 0) / 10) * 100)}%`, height: '100%', borderRadius: 'var(--radius-full)', background: 'var(--color-accent)' }} />
    </div>
  </div>
);

export function OptimizationView({ item, folders, onChange }: { item: OptimizationDTO; folders: FolderDTO[]; onChange: (i: OptimizationDTO) => void }) {
  const toast = useToast();
  const [values, setValues] = useState<Record<string, string>>(item.var_values);
  const [busy, setBusy] = useState(false); const [view, setView] = useState<'full' | 'compressed'>(item.compressed_prompt ? 'compressed' : 'full');
  const [note, setNote] = useState<string>(''); const [tags, setTags] = useState(item.tags.join(', '));
  const base = view === 'compressed' && item.compressed_prompt ? item.compressed_prompt : item.final_prompt;
  const master = useMemo(() => substituteBracketVars(base, values), [base, values]);
  const fail = (e: unknown) => toast((e as ApiError).message ?? t.common.error, 'err');
  const save = async (body: Record<string, unknown>) => { try { onChange(await patch<OptimizationDTO>(`/api/optimizer/items/${item.id}`, body)); } catch (e) { fail(e); } };
  const compress = async () => {
    setBusy(true);
    try {
      const r = await post<Compressed>(`/api/optimizer/items/${item.id}/compress`); onChange(r);
      setNote(r.no_gain ? t.opt.noGain : t.opt.compressed.replace('{a}', String(r.tokens_before)).replace('{b}', String(r.tokens_after)).replace('{p}', String(r.saved_pct)));
      if (!r.no_gain) setView('compressed');
    } catch (e) { fail(e); } finally { setBusy(false); }
  };
  return (
    <div className="col">
      <div className="surface card col" aria-label={t.opt.optimized}>
        <div className="form-grid"><ScoreBar label={t.opt.initial} value={item.initial_score} /><ScoreBar label={t.opt.optimized} value={item.optimized_score} /></div>
        {item.initial_critique && <p className="small tx2" style={{ margin: 0 }}>{item.initial_critique}</p>}
        <p className="small tx3" style={{ margin: 0 }}>{t.opt.scoreNote}{item.framework_used ? ` · ${t.opt.framework}: ${item.framework_used}` : ''}</p>
      </div>
      <div className="surface card col">
        <div className="row spread wrap">
          <h3>{t.opt.finalPrompt}</h3>
          <div className="row wrap">
            {item.compressed_prompt && <div className="seg" role="group" aria-label={t.opt.finalPrompt}>
              <button className={view === 'full' ? 'on' : ''} aria-pressed={view === 'full'} onClick={() => setView('full')}>{t.opt.showOriginal}</button>
              <button className={view === 'compressed' ? 'on' : ''} aria-pressed={view === 'compressed'} onClick={() => setView('compressed')}>{t.opt.showCompressed}</button></div>}
            <StarButton on={item.is_favorite} onClick={() => save({ is_favorite: !item.is_favorite })} />
            <CopyButton text={master} primary />
          </div>
        </div>
        <div className="prompt-box" tabIndex={0} aria-label={t.opt.finalPrompt}>{master}</div>
        <div className="row wrap">
          <button className="btn" onClick={compress} disabled={busy}>{busy ? <Spinner /> : <Minimize2 size={15} aria-hidden />}{busy ? t.opt.compressing : t.opt.compress}</button>
          <span className="small tx3 mono">≈ {estimateTokens(master)} tok</span>
          {note && <span className="small tx2" role="status">{note}</span>}
        </div>
      </div>
      {item.variables.length > 0 && (
        <div className="surface card col">
          <h3>{t.opt.variables}</h3><p className="small tx2" style={{ margin: 0 }}>{t.opt.variablesHint}</p>
          <div className="grid-cards">
            {item.variables.map((v) => <div key={v}><label className="label" htmlFor={`var-${v}`}>{v}</label>
              <input id={`var-${v}`} className="field" maxLength={OPT_LIMITS.variableValue} value={values[v] ?? ''} onChange={(e) => setValues({ ...values, [v]: e.target.value })} onBlur={() => { if (JSON.stringify(values) !== JSON.stringify(item.var_values)) void save({ var_values: values }); }} /></div>)}
          </div>
        </div>
      )}
      {item.changelog_explanation.length > 0 && (
        <div className="surface card col"><h3>{t.opt.changelog}</h3><ul style={{ margin: 0, paddingLeft: 'var(--space-5)' }}>{item.changelog_explanation.map((c, i) => <li key={i} className="small" style={{ marginBottom: 'var(--space-1)' }}>{c}</li>)}</ul></div>
      )}
      <div className="surface card form-grid">
        <div><label className="label" htmlFor={`folder-${item.id}`}>{t.opt.folder}</label>
          <select id={`folder-${item.id}`} className="field" value={item.folder_id ?? ''} onChange={(e) => save({ folder_id: e.target.value || null })}>
            <option value="">{t.opt.noFolder}</option>{folders.map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}</select></div>
        <div className="grow"><label className="label" htmlFor={`tags-${item.id}`}>{t.opt.tags}</label>
          <input id={`tags-${item.id}`} className="field" value={tags} onChange={(e) => setTags(e.target.value)} onBlur={() => { const list = tags.split(',').map((x) => x.trim()).filter(Boolean).slice(0, 8); if (JSON.stringify(list) !== JSON.stringify(item.tags)) void save({ tags: list }); }} /></div>
        <span className="small tx3">{t.opt.engine}: <span className="mono">{item.model || '—'}</span></span>
      </div>
    </div>
  );
}
