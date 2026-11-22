import { useEffect, useMemo, useRef, useState } from 'react';
import { Wand2, ChevronDown } from 'lucide-react';
import { SYSTEM_IDS, SYSTEM_NAMES, LIMITS, type GenerateRequest, type GenOptions, type ResultDTO, type SystemId } from '../../../../shared/src/index.ts';
import { t } from '../strings.ru.ts';
import { streamGenerate, post, patch, ApiError } from '../api.ts';
import { useApp } from '../context.tsx';
import { Seg, Switch, Spinner, SystemDot, useToast } from '../ui.tsx';
import { ClarificationForm } from '../components/ClarificationForm.tsx';
import { ResultCard } from '../components/ResultCard.tsx';
import { TemplateSaveModal } from '../components/TemplateSaveModal.tsx';

type CardState = { status: 'loading' | 'ok' | 'error'; variants: ResultDTO[]; error?: string };

export function GeneratorScreen({ starter, onBusy }: { starter?: GenerateRequest; onBusy?: (busy: boolean) => void } = {}) {
  const app = useApp(); const toast = useToast();
  const [raw, setRaw] = useState(''); const [systems, setSystems] = useState<SystemId[]>(starter?.systems ?? [...SYSTEM_IDS]); const [language, setLanguage] = useState<'ru' | 'en'>(starter?.language ?? 'ru');
  const [opts, setOpts] = useState<GenOptions>({ task_type: 'auto', detail: 'standard', assumptions_mode: 'assume', include_format: true });
  const [running, setRunning] = useState(false); const [stage, setStage] = useState(''); const [cards, setCards] = useState<Record<string, CardState>>({}); const [order, setOrder] = useState<SystemId[]>([]);
  const [active, setActive] = useState<SystemId | null>(null); const [genId, setGenId] = useState(''); const [questions, setQuestions] = useState<string[] | null>(null); const [answers, setAnswers] = useState<string[]>([]);
  const [compare, setCompare] = useState(false); const [cmp, setCmp] = useState<SystemId[]>([]); const [tpl, setTpl] = useState<ResultDTO | null>(null); const [busyCard, setBusyCard] = useState<string | null>(null);
  const [polling, setPolling] = useState(false); const [advOpen, setAdvOpen] = useState(false);
  const ta = useRef<HTMLTextAreaElement>(null); const defaultsApplied = useRef(!!starter); const started = useRef(false);

  useEffect(() => { // defaults from settings (once)
    const s = app.settings; if (!s || defaultsApplied.current || app.prefill) return; defaultsApplied.current = true;
    setLanguage(s.default_language); setSystems(s.default_systems); setOpts((o) => ({ ...o, detail: s.default_detail, assumptions_mode: s.default_assumptions_mode }));
  }, [app.settings, app.prefill]);
  useEffect(() => { // prefill from history/templates
    const p = app.prefill; if (!p || starter) return; defaultsApplied.current = true;
    setRaw(p.raw_input); if (p.systems?.length) setSystems(p.systems); if (p.language) setLanguage(p.language); if (p.options) setOpts((o) => ({ ...o, ...p.options }));
    setTimeout(() => ta.current?.focus(), 50);
  }, [app.prefill?.nonce]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { const el = ta.current; if (!el) return; el.style.height = 'auto'; const line = 24; el.style.height = `${Math.min(Math.max(el.scrollHeight, line * 4 + 24), line * 12 + 24)}px`; }, [raw]);

  const toggle = (id: SystemId) => setSystems((s) => (s.includes(id) ? (s.length > 1 ? s.filter((x) => x !== id) : s) : SYSTEM_IDS.filter((x) => x === id || s.includes(x))));
  const allOn = systems.length === SYSTEM_IDS.length;
  const valid = raw.trim().length >= LIMITS.rawInputMin && raw.length <= LIMITS.rawInputMax;

  const resetCards = (sys: SystemId[]) => { setOrder(sys); setCards(Object.fromEntries(sys.map((s) => [s, { status: 'loading', variants: [] } as CardState]))); setActive(sys[0] ?? null); setCmp([]); };
  const run = async (path: string, body: unknown, sys: SystemId[], continueDraft = false) => {
    onBusy?.(true);
    setRunning(true); setStage(t.gen.stages.analyze); if (!continueDraft) setQuestions(null); setPolling(false); resetCards(sys);
    await streamGenerate(path, body, {
      onStart: setGenId, onIntent: () => setStage(t.gen.stages.transform), onFallback: () => setPolling(true),
      onCard: (r) => { setQuestions(null); setCards((c) => ({ ...c, [r.skill_id]: { status: 'ok', variants: [...(c[r.skill_id]?.variants ?? []), r] } })); },
      onCardError: (s, e, r) => setCards((c) => ({ ...c, [s]: { status: 'error', variants: r ? [...(c[s]?.variants ?? []), r] : c[s]?.variants ?? [], error: e } })),
      onQuestions: (list, id) => { setQuestions(list); setAnswers(list.map(() => '')); setGenId(id); setCards({}); setOrder([]); },
      onDone: (_id, status) => { if (status !== 'draft_questions') setQuestions(null); setRunning(false); setStage(''); },
      onError: (e) => { setRunning(false); setStage(''); setCards({}); setOrder([]); toast(e.status === 429 ? `${e.message}${e.retryAfter ? ` (${e.retryAfter} c)` : ''}` : e.message, 'err'); },
    });
    setRunning(false);
    onBusy?.(false);
  };
  const submit = () => { if (!valid || running) return; void run('/api/generate', { raw_input: raw.trim(), systems, language, options: opts }, systems); };
  const answer = () => { if (!genId || running) return; void run(`/api/generate/${genId}/answer`, { answers }, systems, true); };
  useEffect(() => {
    if (!starter || started.current) return;
    started.current = true;
    void run('/api/generate', starter, starter.systems);
  }, [starter]); // A Home submission starts one run, including under StrictMode.
  useEffect(() => { if (starter) return; const h = (e: KeyboardEvent) => { if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') { e.preventDefault(); submit(); } }; window.addEventListener('keydown', h); return () => window.removeEventListener('keydown', h); });

  const favorite = async (r: ResultDTO, v: boolean) => {
    try { await patch(`/api/results/${r.id}/favorite`, { value: v }); setCards((c) => ({ ...c, [r.skill_id]: { ...c[r.skill_id]!, variants: c[r.skill_id]!.variants.map((x) => (x.id === r.id ? { ...x, is_favorite: v } : x)) } })); }
    catch (e) { toast((e as ApiError).message, 'err'); }
  };
  const regenerate = async (r: ResultDTO, feedback: string) => {
    setBusyCard(r.skill_id);
    try { const nr = await post<ResultDTO>(`/api/generations/${r.generation_id}/results/${r.id}/regenerate`, feedback ? { feedback } : {}); setCards((c) => ({ ...c, [r.skill_id]: { status: nr.status === 'ok' ? 'ok' : 'error', variants: [...c[r.skill_id]!.variants, nr], error: nr.error ?? undefined } })); }
    catch (e) { toast((e as ApiError).message, 'err'); } finally { setBusyCard(null); }
  };
  const cardEl = (s: SystemId) => { const c = cards[s]; return <ResultCard key={s} system={s} variants={c?.variants ?? []} loading={c?.status === 'loading'} error={c?.status === 'error' && !c.variants.length ? c.error : null} busy={busyCard === s} onFavorite={favorite} onRegenerate={regenerate} onTemplate={setTpl} />; };
  const done = useMemo(() => order.filter((s) => cards[s]?.status === 'ok'), [order, cards]);
  const cmpSet = cmp.length === 2 ? cmp : done.slice(0, 2);

  return (
    <div className="col">
      {!starter && <section className="surface card col" aria-labelledby="gen-title" style={{ padding: 24 }}>
        <h1 id="gen-title">{t.gen.title}</h1>
        <div><textarea ref={ta} className="field" value={raw} maxLength={LIMITS.rawInputMax} placeholder={t.gen.placeholder} onChange={(e) => setRaw(e.target.value)} aria-label={t.gen.title} />
          <div className="row spread small tx3" style={{ marginTop: 6 }}><span>{raw.length > 0 && raw.trim().length < LIMITS.rawInputMin ? t.gen.tooShort : ''}</span><span>{raw.length} / {LIMITS.rawInputMax} {t.gen.counter}</span></div></div>
        <div className="row wrap" role="group" aria-label={t.gen.systems}>
          {SYSTEM_IDS.map((id) => <button key={id} type="button" className={`chip ${systems.includes(id) ? 'on' : ''}`} aria-pressed={systems.includes(id)} onClick={() => toggle(id)}><SystemDot id={id} />{SYSTEM_NAMES[id]}</button>)}
          <button type="button" className={`chip ${allOn ? 'on' : ''}`} onClick={() => setSystems([...SYSTEM_IDS])}>{t.gen.allSystems}</button>
          <div className="grow" /><Seg label={t.gen.language} value={language} onChange={setLanguage} options={[{ value: 'ru', label: 'RU' }, { value: 'en', label: 'EN' }]} />
        </div>
        <div><button className="btn ghost sm" onClick={() => setAdvOpen(!advOpen)} aria-expanded={advOpen}><ChevronDown size={15} style={{ transform: advOpen ? 'rotate(180deg)' : undefined }} />{t.gen.advanced}</button>
          {advOpen && <div className="row wrap" style={{ marginTop: 12, gap: 18, alignItems: 'flex-end' }}>
            <div><label className="label" htmlFor="g-type">{t.gen.taskType}</label><select id="g-type" className="field" value={opts.task_type} onChange={(e) => setOpts({ ...opts, task_type: e.target.value as GenOptions['task_type'] })}>{Object.entries(t.gen.taskTypes).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></div>
            <div><span className="label">{t.gen.detail}</span><Seg label={t.gen.detail} value={opts.detail} onChange={(v) => setOpts({ ...opts, detail: v })} options={Object.entries(t.gen.details).map(([value, label]) => ({ value: value as GenOptions['detail'], label }))} /></div>
            <div><span className="label">{t.gen.assumptions}</span><Seg label={t.gen.assumptions} value={opts.assumptions_mode} onChange={(v) => setOpts({ ...opts, assumptions_mode: v })} options={Object.entries(t.gen.modes).map(([value, label]) => ({ value: value as GenOptions['assumptions_mode'], label }))} /></div>
            <div className="row"><Switch on={opts.include_format} onChange={(v) => setOpts({ ...opts, include_format: v })} label={t.gen.includeFormat} /><span>{t.gen.includeFormat}</span></div>
          </div>}</div>
        <div className="row wrap"><button className="btn primary" disabled={!valid || running} onClick={submit}>{running ? <Spinner /> : <Wand2 size={17} />}{running ? stage : t.gen.submit}</button><span className="small tx3">{t.gen.hint}</span>{polling && <span className="small tx2">{t.gen.fallbackPoll}</span>}</div>
      </section>}

      {questions && <ClarificationForm key={genId} questions={questions} answers={answers} setAnswers={setAnswers}
        suggestUrl={`/api/generate/${genId}/suggest`} busy={running} onContinue={answer} />}

      {starter && running && !order.length && <div role="status"><Spinner /> {stage}</div>}
      {order.length > 0 && <section className="col" aria-live="polite">
        {order.length > 1 && <div className="row wrap" role="group" aria-label={t.gen.systems}>
          {order.map((s) => { const c = cards[s]; const dot = !c || c.status === 'loading' ? 'run' : c.status === 'ok' ? 'ok' : 'err'; return <button key={s} aria-pressed={active === s} className={`tab ${active === s ? 'on' : ''}`} onClick={() => { setActive(s); if (compare) setCmp((x) => (x.includes(s) ? x.filter((y) => y !== s) : [...x, s].slice(-2))); }}><span className={`dot ${dot}`} />{SYSTEM_NAMES[s]}</button>; })}
          {done.length > 1 && <><div className="grow" /><div className="row"><span className="small tx2">{t.gen.compare}</span><Switch on={compare} onChange={setCompare} label={t.gen.compare} /></div></>}
        </div>}
        {compare && done.length > 1 ? <div className="grid-cards stagger" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 340px), 1fr))' }}>{cmpSet.map(cardEl)}</div>
          : <div className="stagger">{active && cardEl(active)}</div>}
      </section>}
      {tpl && <TemplateSaveModal prompt={tpl.prompt_text} language={language} systems={[tpl.skill_id]} onClose={() => setTpl(null)} />}
    </div>
  );
}
