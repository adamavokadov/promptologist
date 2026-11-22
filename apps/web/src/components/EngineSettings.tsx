import { useEffect, useState } from 'react';
import { DEFAULT_ENGINE_MODEL, PROVIDERS, supportsCustomTemperature, type EngineView, type Provider } from '../../../../shared/src/index.ts';
import { t } from '../strings.ru.ts';
import { get, postPrompt, put, ApiError } from '../api.ts';
import { Spinner, useToast } from '../ui.tsx';

const CUSTOM = '__custom__';
export function EngineSettings({ admin }: { admin: boolean }) {
  const toast = useToast();
  const [view, setView] = useState<EngineView | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [provider, setProvider] = useState<Provider>('platform'); const [model, setModel] = useState(''); const [custom, setCustom] = useState(false);
  const [baseUrl, setBaseUrl] = useState(''); const [temp, setTemp] = useState(0.4); const [key, setKey] = useState(''); const [clearKey, setClearKey] = useState(false);
  const [busy, setBusy] = useState(false);
  const apply = (v: EngineView) => { setView(v); setProvider(v.provider); setModel(v.model); setBaseUrl(v.base_url); setTemp(v.temperature); setKey(''); setClearKey(false);
    const list = v.provider === 'platform' || v.provider === 'custom' ? [] : v.catalog[v.provider]; setCustom(!list.some((m) => m.id === v.model)); };
  useEffect(() => { get<EngineView>('/api/optimizer/engine').then(apply).catch(() => setLoadError(true)); }, []);
  if (loadError) return <div className="banner err" role="alert">{t.engine.loadError}</div>;
  if (!view) return <Spinner />;
  const list = provider === 'platform' || provider === 'custom' ? [] : view.catalog[provider];
  const needsKey = provider !== 'platform';
  const destinationChanged = provider !== view.provider || baseUrl.trim().replace(/\/+$/, '') !== view.base_url.replace(/\/+$/, '');
  const keepStoredKey = view.has_key && !destinationChanged;
  const fail = (e: unknown) => toast((e as ApiError).message ?? t.common.error, 'err');
  const changeProvider = (p: Provider) => {
    setProvider(p);
    setBaseUrl('');
    setKey('');
    setClearKey(false);
    const first = p === 'platform' || p === 'custom' ? undefined : (view.catalog[p].find((m) => m.recommended) ?? view.catalog[p][0]);
    setCustom(!first);
    setModel(first?.id ?? (p === 'platform' ? DEFAULT_ENGINE_MODEL : ''));
  };
  const save = async () => {
    setBusy(true);
    try { apply(await put<EngineView>('/api/optimizer/engine', { provider, model, base_url: baseUrl, temperature: temp, ...(clearKey ? { api_key: '' } : key ? { api_key: key } : {}) })); toast(t.settings.saved, 'ok'); }
    catch (e) { fail(e); } finally { setBusy(false); }
  };
  const test = async () => { setBusy(true); try { const r = await postPrompt<{ latency_ms: number; model: string }>('/api/optimizer/engine/test'); toast(`${t.engine.testOk}: ${r.model}, ${r.latency_ms} ${t.engine.ms}`, 'ok'); } catch (e) { fail(e); } finally { setBusy(false); } };
  return (
    <section className="surface card col" aria-label={t.engine.title}>
      <h3>{t.engine.title}</h3>
      {!admin && <div className="banner warn">{t.engine.adminOnly}</div>}
      {needsKey && !view.secret_configured && <div className="banner err" role="alert">{t.engine.secretMissing}</div>}
      <div className="form-grid">
        <div><label className="label" htmlFor="eng-provider">{t.engine.provider}</label>
          <select id="eng-provider" className="field" disabled={!admin || busy} value={provider} onChange={(e) => changeProvider(e.target.value as Provider)}>{PROVIDERS.map((p) => <option key={p} value={p}>{t.engine.providers[p]}</option>)}</select></div>
        <div><label className="label" htmlFor="eng-model">{t.engine.model}</label>
          {list.length > 0 && <select id="eng-model" className="field" disabled={!admin || busy} value={custom ? CUSTOM : model} onChange={(e) => { if (e.target.value === CUSTOM) { setCustom(true); } else { setCustom(false); setModel(e.target.value); } }}>
            {list.map((m) => <option key={m.id} value={m.id}>{m.label}</option>)}<option value={CUSTOM}>{t.engine.customModel}</option></select>}
          {(custom || list.length === 0) && <input id={list.length ? 'eng-model-custom' : 'eng-model'} aria-label={t.engine.customModel} className="field" style={{ marginTop: list.length ? 'var(--space-2)' : 0 }} disabled={!admin || busy} value={model} onChange={(e) => setModel(e.target.value)} placeholder={t.engine.customModel} />}
        </div>
      </div>
      {needsKey && <div><label className="label" htmlFor="eng-base">{t.engine.baseUrl}</label><input id="eng-base" className="field" disabled={!admin || busy} value={baseUrl} placeholder={view.default_base_urls[provider] ?? 'https://'} onChange={(e) => { setBaseUrl(e.target.value); setClearKey(false); }} /><div className="small tx3">{t.engine.baseUrlHint}</div></div>}
      {supportsCustomTemperature(provider, model) && <div><label className="label" htmlFor="eng-temp">{t.engine.temperature}: <span className="mono">{temp.toFixed(1)}</span></label><input id="eng-temp" type="range" min={0} max={1.5} step={0.1} disabled={!admin || busy} value={temp} onChange={(e) => setTemp(Number(e.target.value))} /></div>}
      {needsKey && <div><label className="label" htmlFor="eng-key">{t.engine.apiKey}{keepStoredKey && !clearKey ? ` · ${t.engine.apiKeyKept} (${view.key_hint})` : ''}</label>
        <input id="eng-key" className="field" type="password" autoComplete="off" disabled={!admin || clearKey || busy} value={key} placeholder={t.engine.apiKeyNew} onChange={(e) => setKey(e.target.value)} />
        {keepStoredKey && admin && <label className="row small" style={{ marginTop: 'var(--space-2)' }}><input type="checkbox" checked={clearKey} onChange={(e) => setClearKey(e.target.checked)} />{t.engine.apiKeyClear}</label>}
        <div className="small tx3">{view.has_key && destinationChanged ? t.engine.keyDestinationChanged : t.engine.note}</div></div>}
      <div className="row wrap"><button className="btn primary" disabled={!admin || busy || !model.trim()} onClick={save}>{busy ? <Spinner /> : null}{t.engine.save}</button><button className="btn" disabled={!admin || busy} onClick={test}>{t.engine.test}</button></div>
    </section>
  );
}
