import { useEffect, useRef, useState } from 'react';
import { Upload } from 'lucide-react';
import { FRAMEWORK_PRESETS, GOAL_PRESETS, OPT_LIMITS, OPT_WORKFLOWS, OUTPUT_FORMATS, TONES, type FolderDTO, type OptPreset, type OptWorkflow, type OptimizationDTO, type OptimizeRequest } from '../../../../shared/src/index.ts';
import { t } from '../strings.ru.ts';
import { get, postPrompt, ApiError } from '../api.ts';
import { ClarificationForm } from '../components/ClarificationForm.tsx';
import { OptimizationView } from '../components/OptimizationView.tsx';
import { Seg, Spinner, Switch, useToast } from '../ui.tsx';

const store = { get: (k: string) => { try { return localStorage.getItem(k); } catch { return null; } }, set: (k: string, v: string) => { try { localStorage.setItem(k, v); } catch { /* ignore */ } } };
const MAX_FILE = 200_000;
const Chip = ({ on, label, hint, onClick }: { on: boolean; label: string; hint?: string; onClick: () => void }) => (
  <button className={`chip ${on ? 'on' : ''}`} aria-pressed={on} title={hint} onClick={onClick}>{label}</button>
);

export function OptimizerScreen({ starter, onBusy }: { starter?: OptimizeRequest; onBusy?: (busy: boolean) => void } = {}) {
  const toast = useToast(); const file = useRef<HTMLInputElement>(null); const started = useRef(false);
  const [workflow, setWorkflow] = useState<OptWorkflow>('magic');
  const [mode, setMode] = useState<'beginner' | 'pro'>(() => (store.get('opt_mode') === 'pro' ? 'pro' : 'beginner'));
  const [goal, setGoal] = useState<OptPreset | null>(null); const [framework, setFramework] = useState<OptPreset>('auto');
  const [format, setFormat] = useState<(typeof OUTPUT_FORMATS)[number]>('none'); const [tone, setTone] = useState<(typeof TONES)[number]>('none');
  const [bridge, setBridge] = useState(false); const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false); const [item, setItem] = useState<OptimizationDTO | null>(null);
  const [answers, setAnswers] = useState<string[]>([]); const [folders, setFolders] = useState<FolderDTO[]>([]);
  useEffect(() => { get<{ items: FolderDTO[] }>('/api/optimizer/folders').then((d) => setFolders(d.items)).catch(() => {}); }, []);
  const preset: OptPreset = mode === 'pro' ? framework : goal ?? 'auto';
  const fail = (e: unknown) => toast((e as ApiError).message ?? t.common.error, 'err');
  const setModeSaved = (m: 'beginner' | 'pro') => { setMode(m); store.set('opt_mode', m); };
  const canRun = input.trim().length >= OPT_LIMITS.rawMin && !busy;
  const run = async (request?: OptimizeRequest) => {
    setBusy(true); onBusy?.(true); setItem(null);
    try { const r = await postPrompt<OptimizationDTO>('/api/optimizer/run', request ?? { workflow, raw_input: input.trim(), preset, output_format: format, tone, bridge }); setItem(r); setAnswers(r.clarifying_questions.map(() => '')); if (r.status === 'ok') toast(t.opt.saved, 'ok'); }
    catch (e) { fail(e); } finally { setBusy(false); onBusy?.(false); }
  };
  useEffect(() => {
    if (!starter || started.current) return;
    started.current = true;
    void run(starter);
  }, [starter]); // The Home entry is a single submitted task.
  const answer = async (auto: boolean) => {
    if (!item) return; setBusy(true); onBusy?.(true);
    try { const r = await postPrompt<OptimizationDTO>(`/api/optimizer/items/${item.id}/answer`, { answers: auto ? [] : answers, auto }); setItem(r); toast(t.opt.saved, 'ok'); } catch (e) { fail(e); } finally { setBusy(false); onBusy?.(false); }
  };
  const loadFile = async (f: File) => {
    if (f.size > MAX_FILE) { toast(t.opt.fileTooBig, 'err'); return; }
    try {
      const text = await f.text();
      if (text.length > OPT_LIMITS.rawMax) toast(t.opt.fileTruncated, 'info');
      setInput(text.slice(0, OPT_LIMITS.rawMax));
    } catch (error) { fail(error); }
  };
  return (
    <div className="col" style={{ gap: 'var(--space-6)' }}>
      {!starter && <>
      <div><h1>{t.opt.title}</h1><p className="tx2" style={{ margin: 'var(--space-1) 0 0' }}>{t.opt.subtitle}</p></div>
      <div className="workflow-picker" role="group" aria-label={t.opt.title}>
        {OPT_WORKFLOWS.map((w) => <button key={w} aria-pressed={workflow === w} disabled={busy} className={`tab ${workflow === w ? 'on' : ''}`} onClick={() => { setWorkflow(w); setItem(null); }}>{t.opt.workflows[w]}</button>)}
      </div>
      <section className="surface card col" aria-label={t.opt.workflows[workflow]}>
        <p className="small tx2" style={{ margin: 0 }}>{t.opt.workflowHints[workflow]}</p>
        <label className="label" htmlFor="opt-input">{workflow === 'reverse' ? t.opt.referenceLabel : t.opt.inputLabel}</label>
        <textarea id="opt-input" className="field" rows={workflow === 'reverse' ? 9 : 5} maxLength={OPT_LIMITS.rawMax} value={input} placeholder={t.opt.placeholders[workflow]} onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => { if ((e.ctrlKey || e.metaKey) && e.key === 'Enter' && canRun) void run(); }} />
        {workflow === 'reverse' && <div className="row wrap"><button className="btn sm" onClick={() => file.current?.click()}><Upload size={14} aria-hidden />{t.opt.fileHint}</button><span className="small tx3">{t.opt.imagesNote}</span>
          <input ref={file} type="file" hidden accept=".txt,.md,.csv,.json,text/plain,text/markdown,application/json,text/csv" onChange={(e) => { const f = e.target.files?.[0]; if (f) void loadFile(f); e.target.value = ''; }} /></div>}
        <details className="result-details"><summary>{t.prompt.settings}</summary><div className="col">
        <div className="row spread wrap">
          <div className="row wrap"><span className="label" style={{ margin: 0 }}>{t.opt.mode}</span>
            <Seg label={t.opt.mode} value={mode} onChange={setModeSaved} options={[{ value: 'beginner', label: t.opt.beginner }, { value: 'pro', label: t.opt.pro }]} /></div>
          <span className="small tx3">{input.length}/{OPT_LIMITS.rawMax}</span>
        </div>
        <div><span className="label">{mode === 'pro' ? t.opt.frameworks : t.opt.goals}</span>
          <div className="row wrap">
            {mode === 'pro'
              ? FRAMEWORK_PRESETS.map((p) => <Chip key={p} on={framework === p} label={t.opt.frameworkNames[p]} hint={t.opt.frameworkHints[p]} onClick={() => setFramework(p)} />)
              : GOAL_PRESETS.map((p) => <Chip key={p} on={goal === p} label={t.opt.goalNames[p]} hint={t.opt.goalHints[p]} onClick={() => setGoal(goal === p ? null : p)} />)}
          </div></div>
        <div className="form-grid">
          <div><span className="label">{t.opt.formatTitle}</span><div className="row wrap">{OUTPUT_FORMATS.map((f) => <Chip key={f} on={format === f} label={t.opt.formats[f]} onClick={() => setFormat(f)} />)}</div></div>
          <div><span className="label">{t.opt.toneTitle}</span><div className="row wrap">{TONES.map((x) => <Chip key={x} on={tone === x} label={t.opt.tones[x]} onClick={() => setTone(x)} />)}</div></div>
        </div>
        <div className="row"><Switch on={bridge} onChange={setBridge} label={t.opt.bridge} /><div><span>{t.opt.bridge}</span><div className="small tx3">{t.opt.bridgeHint}</div></div></div>
        </div></details>
        <div className="row"><button className="btn primary" disabled={!canRun} onClick={() => { void run(); }}>{busy ? <Spinner /> : null}{busy ? t.opt.running : t.opt.run[workflow]}</button><kbd className="small tx3 shortcut">{t.opt.runShortcut}</kbd></div>
      </section>
      </>}
      {starter && busy && !item && <div role="status"><Spinner /> {t.opt.running}</div>}
      {item?.status === 'draft_questions' && <ClarificationForm key={item.id} questions={item.clarifying_questions} answers={answers}
        setAnswers={setAnswers} suggestUrl={`/api/optimizer/items/${item.id}/suggest`} busy={busy}
        onContinue={() => { void answer(false); }} onSkip={() => { void answer(true); }} />}
      {item?.status === 'ok' && <OptimizationView key={item.id} item={item} folders={folders} onChange={setItem} />}
    </div>
  );
}
