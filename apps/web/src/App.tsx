import { Component, useCallback, useEffect, useRef, useState, type ReactNode } from 'react';
import { Sparkles, History, LayoutTemplate, Star, Cpu, ScrollText, Settings as Cog, Wand2, PanelLeft, Sun, Moon, Monitor, MoreHorizontal } from 'lucide-react';
import type { Settings } from '../../../shared/src/index.ts';
import { t } from './strings.ru.ts';
import { get, onWake, ApiError } from './api.ts';
import { AppCtx, type AgentStatus, type Me, type Prefill, type Screen, type AppState } from './context.tsx';
import { ToastProvider, Spinner, Modal } from './ui.tsx';
import { GeneratorScreen } from './screens/Generator.tsx';
import { HistoryScreen } from './screens/History.tsx';
import { TemplatesScreen } from './screens/Templates.tsx';
import { FavoritesScreen } from './screens/Favorites.tsx';
import { SkillsScreen } from './screens/Skills.tsx';
import { ReportsScreen } from './screens/Reports.tsx';
import { SettingsScreen } from './screens/Settings.tsx';

const NAV: { id: Screen; label: string; icon: typeof Sparkles }[] = [
  { id: 'generator', label: t.nav.generator, icon: Wand2 }, { id: 'history', label: t.nav.history, icon: History }, { id: 'templates', label: t.nav.templates, icon: LayoutTemplate },
  { id: 'favorites', label: t.nav.favorites, icon: Star }, { id: 'skills', label: t.nav.skills, icon: Cpu }, { id: 'reports', label: t.nav.reports, icon: ScrollText }, { id: 'settings', label: t.nav.settings, icon: Cog },
];
const store = { get: (k: string) => { try { return localStorage.getItem(k); } catch { return null; } }, set: (k: string, v: string) => { try { localStorage.setItem(k, v); } catch { /* storage may be blocked in iframes */ } } };

class Boundary extends Component<{ children: ReactNode }, { err: boolean }> {
  state = { err: false };
  static getDerivedStateFromError() { return { err: true }; }
  render() {
    if (!this.state.err) return this.props.children;
    return <div className="empty glass" style={{ margin: 40 }}><h3>{t.boundary.title}</h3><button className="btn primary" style={{ marginTop: 14 }} onClick={() => this.setState({ err: false })}>{t.boundary.retry}</button></div>;
  }
}

const Logo = () => <svg className="logo" viewBox="0 0 32 32" aria-hidden><defs><linearGradient id="lg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#7C5CFF" /><stop offset="1" stopColor="#22D3EE" /></linearGradient></defs><path d="M16 2l12 7v14l-12 7L4 23V9z" fill="url(#lg)" /><path d="M16 9l1.8 4.6L22.5 15l-4.7 1.4L16 21l-1.8-4.6L9.5 15l4.7-1.4z" fill="#fff" opacity=".92" /></svg>;
const initials = (n: string) => (n.trim().split(/\s+/).map((p) => p[0]).slice(0, 2).join('') || '•').toUpperCase();

export default function App() {
  const [screen, setScreen] = useState<Screen>(() => (location.hash.replace('#/', '') as Screen) || 'generator');
  const [me, setMe] = useState<Me | null>(null); const [settings, setSettingsState] = useState<Settings | null>(null); const [agent, setAgent] = useState<AgentStatus | null>(null);
  const [authErr, setAuthErr] = useState(false); const [waking, setWaking] = useState(false); const [railOpen, setRailOpen] = useState(false); const [compact, setCompact] = useState(false); const [moreOpen, setMoreOpen] = useState(false);
  const [prefill, setPrefillState] = useState<Prefill | null>(null); const [openGenerationId, setOpenGenerationId] = useState<string | null>(null);
  const [theme, setThemeState] = useState<'dark' | 'light' | 'system'>(() => (store.get('theme') as any) || 'dark');
  const shellRef = useRef<HTMLDivElement>(null);

  const go = useCallback((s: Screen) => { setScreen(s); setMoreOpen(false); try { history.replaceState(null, '', `#/${s}`); } catch { /* ignore */ } }, []);
  const reload = useCallback(() => {
    get<Me>('/api/me').then(setMe).catch((e) => { if (e instanceof ApiError && e.status === 401) setAuthErr(true); });
    get<Settings>('/api/settings').then(setSettingsState).catch(() => {});
    get<AgentStatus>('/api/agent/status').then(setAgent).catch(() => {});
  }, []);
  useEffect(() => { reload(); const id = setInterval(() => get<AgentStatus>('/api/agent/status').then(setAgent).catch(() => {}), 60_000); return () => clearInterval(id); }, [reload]);
  useEffect(() => onWake(setWaking), []);
  useEffect(() => { const ro = new ResizeObserver(([e]) => setCompact((e?.contentRect.width ?? 1000) < 800)); ro.observe(document.body); return () => ro.disconnect(); }, []);
  useEffect(() => { // theme
    const apply = () => { const dark = theme === 'system' ? matchMedia('(prefers-color-scheme: dark)').matches : theme === 'dark'; document.documentElement.dataset.theme = dark ? 'dark' : 'light'; };
    apply(); const mq = matchMedia('(prefers-color-scheme: dark)'); mq.addEventListener('change', apply); return () => mq.removeEventListener('change', apply);
  }, [theme]);
  useEffect(() => { if (settings && !store.get('theme')) setThemeState(settings.theme); }, [settings]);
  useEffect(() => { // iframe auto-height contract: window.parent.postMessage({type:'vibe:resize', height})
    const el = shellRef.current; if (!el) return;
    const send = () => { try { window.parent?.postMessage({ type: 'vibe:resize', height: Math.ceil(Math.max(el.scrollHeight, el.offsetHeight)) + 8 }, '*'); } catch { /* ignore */ } };
    const ro = new ResizeObserver(send); ro.observe(el); send(); return () => ro.disconnect();
  });
  useEffect(() => { const h = () => { const s = location.hash.replace('#/', '') as Screen; if (NAV.some((n) => n.id === s)) setScreen(s); }; window.addEventListener('hashchange', h); return () => window.removeEventListener('hashchange', h); }, []);

  const state: AppState = {
    me, settings, agent, go, prefill, reload, theme,
    setPrefill: (p, doGo = true) => { setPrefillState({ ...p, nonce: Date.now() }); if (doGo) go('generator'); },
    setSettings: setSettingsState, openGeneration: (id) => { setOpenGenerationId(id); go('history'); }, openGenerationId, clearOpenGeneration: () => setOpenGenerationId(null),
    setTheme: (v) => { setThemeState(v); store.set('theme', v); },
  };
  const days = agent?.next_check_at ? Math.max(0, Math.round((Date.parse(agent.next_check_at) - Date.now()) / 86_400_000)) : null;
  const agentLabel = !agent ? '…' : agent.paused_reason ? t.agent.paused : !agent.auto_refresh_enabled ? t.agent.off : agent.busy ? t.agent.busy : `${t.agent.active}${days !== null ? ` · ${t.agent.soon} ${days} ${t.agent.days}` : ''}`;
  const agentDot = !agent ? '' : agent.paused_reason ? 'warn' : !agent.auto_refresh_enabled ? '' : agent.busy ? 'run' : 'ok';
  const ThemeIcon = theme === 'dark' ? Moon : theme === 'light' ? Sun : Monitor;
  const mainNav = compact ? NAV.slice(0, 4) : NAV; const moreNav = compact ? NAV.slice(4) : [];

  if (authErr) return <ToastProvider><div className="bg-layer"><div className="aurora a1" /><div className="aurora a2" /></div><div style={{ position: 'relative', zIndex: 1, padding: 40 }}><div className="empty glass"><Logo /><h3 style={{ marginTop: 12 }}>{t.appName}</h3><p className="tx2">{t.auth.required}</p></div></div></ToastProvider>;

  return (
    <AppCtx.Provider value={state}><ToastProvider>
      <div className="bg-layer" aria-hidden><div className="aurora a1" /><div className="aurora a2" /><div className="aurora a3" /><div className="aurora a4" /><div className="grid" /><div className="noise" /></div>
      <div className={`shell ${compact ? 'compact' : ''}`} ref={shellRef}>
        <nav className={`rail glass ${railOpen ? 'open' : ''}`} aria-label="Главное меню" onMouseEnter={() => !compact && setRailOpen(true)} onMouseLeave={() => setRailOpen(false)}>
          <button className="nav-item" onClick={() => setRailOpen((v) => !v)} aria-label="Свернуть или развернуть меню"><PanelLeft size={20} /><span className="nav-label">{t.appName}</span></button>
          {NAV.map((n) => <button key={n.id} className={`nav-item ${screen === n.id ? 'on' : ''}`} onClick={() => go(n.id)} aria-current={screen === n.id ? 'page' : undefined} title={n.label}><n.icon size={20} /><span className="nav-label">{n.label}</span></button>)}
        </nav>
        <div className="main">
          <header className="topbar">
            <Logo /><h2 style={{ fontSize: 20 }}>{t.appName}</h2><div className="grow" />
            <button className="chip" onClick={() => go('reports')} aria-label={agentLabel} style={{ maxWidth: '55vw' }}><span className={`dot ${agentDot}`} /><span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{agentLabel}</span></button>
            <button className="icon-btn" aria-label={`Тема: ${t.settings.theme[theme]}`} onClick={() => state.setTheme(theme === 'dark' ? 'light' : theme === 'light' ? 'system' : 'dark')}><ThemeIcon size={18} /></button>
            <span className="avatar" title={me?.name ?? ''} aria-label={me?.name ?? 'Пользователь'}>{initials(me?.name ?? '')}</span>
          </header>
          <main className="content">
            {agent?.paused_reason && <div className="banner err" role="alert"><span className="grow">{agent.paused_reason.startsWith('quota') ? t.banner.quota : t.banner.paused}</span></div>}
            {agent?.scheduler_mode === 'lazy' && <div className="banner warn"><span className="grow">{t.banner.fallback}</span></div>}
            <Boundary key={screen}>
              {screen === 'generator' && <GeneratorScreen />}{screen === 'history' && <HistoryScreen />}{screen === 'templates' && <TemplatesScreen />}
              {screen === 'favorites' && <FavoritesScreen />}{screen === 'skills' && <SkillsScreen />}{screen === 'reports' && <ReportsScreen />}{screen === 'settings' && <SettingsScreen />}
            </Boundary>
          </main>
        </div>
        <nav className="bottom-tabs glass" aria-label="Навигация">
          {mainNav.map((n) => <button key={n.id} className={`nav-item ${screen === n.id ? 'on' : ''}`} onClick={() => go(n.id)} aria-label={n.label}><n.icon size={20} /><span>{n.label}</span></button>)}
          {moreNav.length > 0 && <button className="nav-item" onClick={() => setMoreOpen(true)} aria-label={t.nav.more}><MoreHorizontal size={20} /><span>{t.nav.more}</span></button>}
        </nav>
        {moreOpen && <Modal title={t.nav.more} onClose={() => setMoreOpen(false)}>{moreNav.map((n) => <button key={n.id} className="nav-item" onClick={() => go(n.id)}><n.icon size={20} />{n.label}</button>)}</Modal>}
      </div>
      {waking && <div className="overlay" style={{ zIndex: 80 }} role="alert"><div className="glass dense empty" style={{ maxWidth: 420 }}><Logo /><h3 style={{ margin: '12px 0 6px' }}>{t.wake.title}</h3><p className="tx2" style={{ margin: '0 0 12px' }}>{t.wake.hint}</p><Spinner /></div></div>}
    </ToastProvider></AppCtx.Provider>
  );
}
