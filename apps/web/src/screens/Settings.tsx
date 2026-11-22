import { useEffect, useRef, useState } from 'react';
import { Download, Upload, Trash2, RefreshCw } from 'lucide-react';
import { SYSTEM_IDS, SYSTEM_NAMES, type Settings } from '../../../../shared/src/index.ts';
import { t } from '../strings.ru.ts';
import { get, post, put, ApiError } from '../api.ts';
import { useApp } from '../context.tsx';
import { Seg, Switch, ConfirmModal, useToast } from '../ui.tsx';
import { EngineSettings } from '../components/EngineSettings.tsx';

interface Model { id: string; name: string; free: boolean; pricing: unknown }
const Section = ({ title, children }: { title: string; children: React.ReactNode }) => <section className="surface card col" aria-label={title}><h3>{title}</h3>{children}</section>;

export function SettingsScreen() {
  const app = useApp(); const toast = useToast(); const admin = !!app.me?.is_admin; const s = app.settings; const file = useRef<HTMLInputElement>(null);
  const [models, setModels] = useState<Model[]>([]); const [usage, setUsage] = useState<any>(null); const [confirm, setConfirm] = useState(false);
  useEffect(() => { get<{ items: Model[] }>('/api/models').then((d) => setModels(d.items)).catch(() => {}); get<any>('/api/usage').then(setUsage).catch(() => {}); }, []);
  if (!s) return null;
  const save = async (patch: Partial<Settings>) => { try { const r = await put<Settings>('/api/settings', patch); app.setSettings(r); toast(t.settings.saved, 'ok'); } catch (e) { toast((e as ApiError).message, 'err'); } };
  const exportJson = async () => { const d = await post<unknown>('/api/export'); const url = URL.createObjectURL(new Blob([JSON.stringify(d, null, 2)], { type: 'application/json' })); const a = document.createElement('a'); a.href = url; a.download = 'promptolog-export.json'; a.click(); URL.revokeObjectURL(url); };
  const importTpl = async (f: File) => { try { const j = JSON.parse(await f.text()); const r = await post<{ imported: number; errors: string[] }>('/api/import/templates', { templates: Array.isArray(j) ? j : j.templates ?? [] }); toast(`${t.settings.imported}: ${r.imported}${r.errors.length ? ` (ошибок: ${r.errors.length})` : ''}`, r.errors.length ? 'err' : 'ok'); } catch (e) { toast((e as ApiError).message || t.common.error, 'err'); } };
  const clear = async () => { try { const r = await post<{ removed: number }>('/api/history/clear'); toast(`${t.common.delete}: ${r.removed}`, 'ok'); } catch (e) { toast((e as ApiError).message, 'err'); } };
  const modelSelect = (id: string, value: string, key: 'transformer_model' | 'analyzer_model', label: string) => (
    <div><label className="label" htmlFor={id}>{label}</label><select id={id} className="field" disabled={!admin} value={value} onChange={(e) => save({ [key]: e.target.value })}>{[...new Set([value, ...models.map((m) => m.id)])].map((m) => <option key={m} value={m}>{m}{models.find((x) => x.id === m)?.free ? ` · ${t.settings.free}` : ''}</option>)}</select></div>);
  const schedulerText = app.agent?.scheduler_mode === 'job' ? t.agent.cron : t.agent.fallback;
  const next = app.agent?.next_check_at ? new Date(app.agent.next_check_at).toLocaleString('ru-RU') : '—';
  return (
    <div className="col" style={{ gap: 16 }}>
      <h1>{t.settings.title}</h1>
      {!admin && <div className="banner warn">{t.settings.adminOnly}</div>}
      <Section title={t.settings.models}>
        {modelSelect('m-t', s.transformer_model, 'transformer_model', t.settings.transformer)}{modelSelect('m-a', s.analyzer_model, 'analyzer_model', t.settings.analyzer)}
        {usage && <p className="small tx2" style={{ margin: 0 }}>{t.settings.usage}: <span className="mono">{typeof usage.total_tokens === 'number' ? usage.total_tokens.toLocaleString('ru-RU') : JSON.stringify(usage).slice(0, 120)}</span></p>}
      </Section>
      <Section title={t.settings.defaults}>
        <div className="row wrap" style={{ gap: 18 }}>
          <div><span className="label">{t.settings.defLanguage}</span><Seg label={t.settings.defLanguage} value={s.default_language} onChange={(v) => save({ default_language: v })} options={[{ value: 'ru', label: 'RU' }, { value: 'en', label: 'EN' }]} /></div>
          <div><span className="label">{t.gen.detail}</span><Seg label={t.gen.detail} value={s.default_detail} onChange={(v) => save({ default_detail: v })} options={Object.entries(t.gen.details).map(([value, label]) => ({ value: value as Settings['default_detail'], label }))} /></div>
          <div><span className="label">{t.gen.assumptions}</span><Seg label={t.gen.assumptions} value={s.default_assumptions_mode} onChange={(v) => save({ default_assumptions_mode: v })} options={Object.entries(t.gen.modes).map(([value, label]) => ({ value: value as Settings['default_assumptions_mode'], label }))} /></div>
        </div>
        <div><span className="label">{t.settings.defSystems}</span><div className="row wrap">{SYSTEM_IDS.map((id) => { const on = s.default_systems.includes(id); return <button key={id} className={`chip ${on ? 'on' : ''}`} aria-pressed={on} disabled={!admin} onClick={() => { const next = on ? s.default_systems.filter((x) => x !== id) : [...s.default_systems, id]; if (next.length) void save({ default_systems: next }); }}>{SYSTEM_NAMES[id]}</button>; })}</div></div>
        <div><label className="label" htmlFor="ret">{t.settings.retention}</label><input id="ret" className="field" type="number" min={20} max={5000} style={{ maxWidth: 160 }} disabled={!admin} defaultValue={s.history_retention} onBlur={(e) => { const v = Number(e.target.value); if (v >= 20 && v <= 5000 && v !== s.history_retention) void save({ history_retention: v }); }} /></div>
      </Section>
      <Section title={t.settings.agent}>
        <div className="row"><Switch on={s.auto_refresh_enabled} disabled={!admin} onChange={(v) => save({ auto_refresh_enabled: v })} label={t.settings.masterSwitch} /><span>{t.settings.masterSwitch}</span></div>
        <p className="small tx2" style={{ margin: 0 }}>{t.settings.interval}</p>
        <p className="small" style={{ margin: 0 }}><span className="tx3">{t.settings.scheduler}: </span>{schedulerText}</p>
        <p className="small" style={{ margin: 0 }}><span className="tx3">{t.settings.lastRuns}: </span>{next}</p>
        <p className="small" style={{ margin: 0 }}><span className="tx3">{t.settings.jobSecret}: </span>{app.agent?.job_secret_configured ? t.settings.secretOk : t.settings.secretMissing}</p>
        <div className="row wrap"><button className="btn" disabled={!admin} onClick={async () => { try { await post('/api/skills/refresh-all'); toast(t.skills.started, 'ok'); app.reload(); } catch (e) { toast((e as ApiError).message, 'err'); } }}><RefreshCw size={15} />{t.settings.checkAll}</button>
          {app.agent?.paused_reason && <button className="btn" disabled={!admin} onClick={async () => { await post('/api/settings/resume-agent'); app.reload(); }}>{t.banner.resume}</button>}</div>
      </Section>
      <EngineSettings admin={admin} />
      <Section title={t.settings.notifications}><div className="row"><Switch on={s.notifications_enabled} disabled={!admin} onChange={(v) => save({ notifications_enabled: v })} label={t.settings.notifOn} /><span>{t.settings.notifOn}</span></div><p className="small tx3" style={{ margin: 0 }}>{t.settings.notifNote}</p></Section>
      <Section title={t.settings.appearance}><Seg label={t.settings.appearance} value={app.theme} onChange={app.setTheme} options={(['dark', 'light', 'system'] as const).map((v) => ({ value: v, label: t.settings.theme[v] }))} /></Section>
      <Section title={t.settings.data}>
        <div className="row wrap"><button className="btn" onClick={exportJson}><Download size={15} />{t.settings.export}</button><button className="btn" onClick={() => file.current?.click()}><Upload size={15} />{t.settings.importTpl}</button>
          <input ref={file} type="file" accept="application/json" hidden onChange={(e) => { const f = e.target.files?.[0]; if (f) void importTpl(f); e.target.value = ''; }} />
          <button className="btn danger" onClick={() => setConfirm(true)}><Trash2 size={15} />{t.settings.clear}</button></div>
      </Section>
      {confirm && <ConfirmModal title={t.settings.clear} text={t.settings.clearConfirm} danger onConfirm={clear} onClose={() => setConfirm(false)} />}
    </div>
  );
}
