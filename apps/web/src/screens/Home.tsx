import { useState, type FormEvent } from 'react';
import {
  LIMITS, OPT_LIMITS, SYSTEM_IDS, SYSTEM_NAMES, START_MODES, inferPromptRoute, isHypothesisTask,
  type GenerateRequest, type OptimizeRequest, type StartMode, type SystemId,
} from '../../../../shared/src/index.ts';
import { useApp } from '../context.tsx';
import { t } from '../strings.ru.ts';
import { Spinner } from '../ui.tsx';
import { GeneratorScreen } from './Generator.tsx';
import { OptimizerScreen } from './Optimizer.tsx';

type Role = keyof typeof t.home.examples;
type Job = { id: number; mode: 'generate'; request: GenerateRequest } | { id: number; mode: 'optimize'; request: OptimizeRequest };
const ROLES = ['marketing', 'hr', 'leader'] as const;

export function HomeScreen() {
  const { settings } = useApp();
  const [input, setInput] = useState('');
  const [mode, setMode] = useState<StartMode>('auto');
  const [role, setRole] = useState<Role | null>(null);
  const [system, setSystem] = useState<SystemId | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [busy, setBusy] = useState(false);
  const resolved = mode === 'auto' ? inferPromptRoute(input) : mode;
  const selectedSystem = system ?? settings?.default_systems[0] ?? 'chatgpt';
  const min = resolved === 'generate' ? LIMITS.rawInputMin : OPT_LIMITS.rawMin;
  const max = resolved === 'generate' ? LIMITS.rawInputMax : OPT_LIMITS.rawMax;
  const valid = input.trim().length >= min && input.trim().length <= max;
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!valid || busy) return;
    const raw_input = input.trim();
    const id = (job?.id ?? 0) + 1;
    setBusy(true);
    if (resolved === 'generate') {
      setJob({ id, mode: 'generate', request: { raw_input, systems: [selectedSystem], language: settings?.default_language ?? 'ru',
        options: { task_type: isHypothesisTask(raw_input) ? 'hypothesis' : 'auto', detail: settings?.default_detail ?? 'standard', assumptions_mode: 'assume', include_format: true } } });
    } else {
      setJob({ id, mode: 'optimize', request: { raw_input, workflow: resolved, preset: 'auto', output_format: 'none', tone: 'none', bridge: false } });
    }
  };
  const pickExample = (value: string) => { setInput(value); setMode('auto'); };
  return (
    <div className="col home-workspace">
      <form className="surface card col" onSubmit={submit}>
        <h1>{t.home.title}</h1>
        <div>
          <label className="label" htmlFor="home-input">{t.home.input}</label>
          <textarea className="field" id="home-input" rows={4} maxLength={OPT_LIMITS.rawMax} value={input}
            placeholder={t.home.placeholder} onChange={(event) => setInput(event.target.value)} />
        </div>
        <div className="row wrap spread">
          <div className="row wrap">
            <button className="btn primary" type="submit" disabled={!valid || busy}>{busy && <Spinner />}{busy ? t.opt.running : t.home.submit}</button>
            {input.trim().length >= min && <span className="small tx2">{t.home.modes[resolved]}</span>}
          </div>
          {input.trim().length > max && <span className="small tx2">{t.home.inputLimit.replace('{limit}', String(max))}</span>}
        </div>
        <details className="result-details">
          <summary>{t.home.modeLabel}</summary>
          <div className="row wrap">
            <select className="field prompt-select" aria-label={t.home.modeLabel} value={mode} onChange={(event) => setMode(event.target.value as StartMode)}>
              {START_MODES.map((value) => <option key={value} value={value}>{t.home.modes[value]}</option>)}
            </select>
            {resolved === 'generate' && <select className="field prompt-select" aria-label={t.gen.systems} value={selectedSystem}
              onChange={(event) => setSystem(event.target.value as SystemId)}>
              {SYSTEM_IDS.map((id) => <option key={id} value={id}>{SYSTEM_NAMES[id]}</option>)}
            </select>}
          </div>
          <p className="small tx3">{t.home.routingHint}</p>
          <button type="button" className="btn sm ghost prompt-start" onClick={() => pickExample(t.home.hypothesis)}>{t.home.hypothesisLabel}</button>
        </details>
      </form>
      {job?.mode === 'generate' && <GeneratorScreen key={job.id} starter={job.request} onBusy={setBusy} />}
      {job?.mode === 'optimize' && <OptimizerScreen key={job.id} starter={job.request} onBusy={setBusy} />}
      {!job && <details className="surface card result-details role-examples">
        <summary>{t.home.examplesTitle}</summary>
        <div className="col">
          <div className="row wrap" role="group" aria-label={t.home.examplesTitle}>
            {ROLES.map((value) => <button key={value} type="button" className={`chip ${role === value ? 'on' : ''}`}
              aria-pressed={role === value} onClick={() => setRole(value)}>{t.home.roles[value]}</button>)}
          </div>
          {role && <div className="form-grid">{t.home.examples[role].map(({ before, after }) => (
            <article key={before} className="col surface card">
              <p className="small"><strong>{t.home.before}</strong> {before}</p>
              <p className="small tx2"><strong>{t.home.after}</strong> {after}</p>
              <button className="btn sm prompt-start" type="button" onClick={() => pickExample(before)}>{t.home.useExample}</button>
            </article>
          ))}</div>}
        </div>
      </details>}
    </div>
  );
}
