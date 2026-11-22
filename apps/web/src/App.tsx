import { Component, useCallback, useEffect, useRef, useState, type ReactNode } from 'react';
import { History, LayoutTemplate, Star, Cpu, ScrollText, Settings as Cog, Wand2, Plus, PanelLeftClose, PanelLeftOpen, BarChart3, Sparkles, Library, Sun, Moon, Monitor, MoreHorizontal } from 'lucide-react';
import { settingsSchema, type Settings } from '../../../shared/src/index.ts';
import { t } from './strings.ru.ts';
import { get, onWake, ApiError } from './api.ts';
import { AppCtx, type AgentStatus, type Me, type Prefill, type Screen, type AppState } from './context.tsx';
import { ToastProvider, Spinner, Modal } from './ui.tsx';
import { HomeScreen } from './screens/Home.tsx';
import { GeneratorScreen } from './screens/Generator.tsx';
import { HistoryScreen } from './screens/History.tsx';
import { TemplatesScreen } from './screens/Templates.tsx';
import { FavoritesScreen } from './screens/Favorites.tsx';
import { SkillsScreen } from './screens/Skills.tsx';
import { ReportsScreen } from './screens/Reports.tsx';
import { SettingsScreen } from './screens/Settings.tsx';
import { AnalyticsScreen } from './screens/Analytics.tsx';
import { OptimizerScreen } from './screens/Optimizer.tsx';
import { LibraryScreen } from './screens/Library.tsx';

interface NavDef { id: Screen; label: string; icon: typeof Wand2; adminOnly?: boolean }
const WORK: NavDef[] = [{ id: 'optimizer', label: t.nav.optimizer, icon: Sparkles }, { id: 'library', label: t.nav.library, icon: Library }, { id: 'history', label: t.nav.history, icon: History }, { id: 'generator', label: t.nav.generator, icon: Wand2 }, { id: 'favorites', label: t.nav.favorites, icon: Star }, { id: 'templates', label: t.nav.templates, icon: LayoutTemplate }];
const SYSTEM: NavDef[] = [{ id: 'skills', label: t.nav.skills, icon: Cpu }, { id: 'reports', label: t.nav.reports, icon: ScrollText }, { id: 'analytics', label: t.analytics.nav, icon: BarChart3, adminOnly: true }];
const NEW_PROMPT: NavDef = { id: 'home', label: t.nav.new, icon: Plus };
const SETTINGS: NavDef = { id: 'settings', label: t.nav.settings, icon: Cog };
const ALL_SCREENS: Screen[] = ['home', 'generator', 'optimizer', 'library', 'history', 'favorites', 'templates', 'skills', 'reports', 'analytics', 'settings'];
const parseHash = (): Screen => { const s = location.hash.replace('#/', '') as Screen; return ALL_SCREENS.includes(s) ? s : 'home'; };
const store = { get: (k: string) => { try { return localStorage.getItem(k); } catch { return null; } }, set: (k: string, v: string) => { try { localStorage.setItem(k, v); } catch { /* storage may be blocked in iframes */ } } };

const themeFromStorage = () => {
  const theme = settingsSchema.shape.theme.safeParse(store.get('theme'));
  return theme.success ? theme.data : undefined;
};
const embedded = window.parent !== window;

class Boundary extends Component<{ children: ReactNode }, { err: boolean }> {
  state = { err: false };
  static getDerivedStateFromError() { return { err: true }; }
  render() {
    if (!this.state.err) return this.props.children;
    return <div className="empty surface" style={{ margin: 'var(--space-10)' }}><h3>{t.boundary.title}</h3><button className="btn primary" style={{ marginTop: 'var(--space-4)' }} onClick={() => this.setState({ err: false })}>{t.boundary.retry}</button></div>;
  }
}

const Logo = () => <svg className="logo" viewBox="0 0 32 32" aria-hidden><path d="M16 2l12 7v14l-12 7L4 23V9z" fill="var(--color-accent)" /><path d="M16 9l1.8 4.6L22.5 15l-4.7 1.4L16 21l-1.8-4.6L9.5 15l4.7-1.4z" fill="var(--color-on-accent)" /></svg>;
const initials = (n: string) => (n.trim().split(/\s+/).map((p) => p[0]).slice(0, 2).join('') || '•').toUpperCase();

export default function App() {
  const [screen, setScreen] = useState<Screen>(parseHash);
  const [me, setMe] = useState<Me | null>(null); const [settings, setSettingsState] = useState<Settings | null>(null); const [agent, setAgent] = useState<AgentStatus | null>(null);
  const [authErr, setAuthErr] = useState(false); const [waking, setWaking] = useState(false); const [bodyW, setBodyW] = useState(() => document.documentElement.clientWidth); const [sidebarPref, setSidebarPref] = useState<'expanded' | 'collapsed' | null>(() => { const v = store.get('sidebar'); return v === 'expanded' || v === 'collapsed' ? v : null; }); const [moreOpen, setMoreOpen] = useState(false);
  const compact = bodyW < 800;
  const [prefill, setPrefillState] = useState<Prefill | null>(null); const [openGenerationId, setOpenGenerationId] = useState<string | null>(null);
  const [theme, setThemeState] = useState<'dark' | 'light' | 'system'>(() => themeFromStorage() ?? 'dark');
  const shellRef = useRef<HTMLDivElement>(null);

  const go = useCallback((s: Screen) => { setScreen(s); setMoreOpen(false); try { history.replaceState(null, '', `#/${s}`); } catch { /* ignore */ } }, []);
  const reload = useCallback(() => {
    get<Me>('/api/me').then(setMe).catch((e) => { if (e instanceof ApiError && e.status === 401) setAuthErr(true); });
    get<Settings>('/api/settings').then(setSettingsState).catch(() => {});
    get<AgentStatus>('/api/agent/status').then(setAgent).catch(() => {});
  }, []);
  useEffect(() => { reload(); const id = setInterval(() => get<AgentStatus>('/api/agent/status').then(setAgent).catch(() => {}), 60_000); return () => clearInterval(id); }, [reload]);
  useEffect(() => onWake(setWaking), []);
  useEffect(() => { const ro = new ResizeObserver(([e]) => { if (e) setBodyW(e.contentRect.width); }); ro.observe(document.body); return () => ro.disconnect(); }, []);
  useEffect(() => { // theme
    const apply = () => { const dark = theme === 'system' ? matchMedia('(prefers-color-scheme: dark)').matches : theme === 'dark'; document.documentElement.dataset.theme = dark ? 'dark' : 'light'; };
    apply(); const mq = matchMedia('(prefers-color-scheme: dark)'); mq.addEventListener('change', apply); return () => mq.removeEventListener('change', apply);
  }, [theme]);
  useEffect(() => { if (settings && !themeFromStorage()) setThemeState(settings.theme); }, [settings]);
  useEffect(() => { // iframe auto-height contract: window.parent.postMessage({type:'vibe:resize', height})
    const el = shellRef.current;
    if (!el || !embedded) return;
    let lastHeight = 0;
    const send = () => {
      const height = Math.ceil(el.getBoundingClientRect().height);
      if (!height || height === lastHeight) return;
      lastHeight = height;
      window.parent.postMessage({ type: 'vibe:resize', height }, '*');
    };
    const ro = new ResizeObserver(send);
    ro.observe(el);
    send();
    return () => ro.disconnect();
  }, [authErr]);
  const isAdmin = !!me?.is_admin; const meLoaded = me !== null;
  useEffect(() => { const h = () => { const s = parseHash(); if (s === 'analytics' && !isAdmin) return; setScreen(s); }; window.addEventListener('hashchange', h); return () => window.removeEventListener('hashchange', h); }, [isAdmin]);
  useEffect(() => { if (meLoaded && !isAdmin && screen === 'analytics') go('home'); }, [meLoaded, isAdmin, screen, go]); // admin-only section: non-admins fall back to the generator

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
  const systemNav = SYSTEM.filter((n) => !n.adminOnly || isAdmin);
  const flatNav = [NEW_PROMPT, ...WORK, ...systemNav, SETTINGS];
  const mainNav = flatNav.slice(0, 4);
  const moreNav = flatNav.slice(4);
  const collapsed = !compact && (sidebarPref ? sidebarPref === 'collapsed' : bodyW < 1024);
  const toggleSidebar = () => { const next = collapsed ? 'expanded' : 'collapsed'; setSidebarPref(next); store.set('sidebar', next); };
  const themeLabel = `${t.nav.themeLabel}: ${t.settings.theme[theme]}`; const userName = me?.name ?? t.nav.userFallback;
  const cycleTheme = () => state.setTheme(theme === 'dark' ? 'light' : theme === 'light' ? 'system' : 'dark');
  const navButton = (n: NavDef, extra = '') => <button key={n.id} className={`nav-item ${extra} ${screen === n.id ? 'on' : ''}`} onClick={() => go(n.id)} aria-current={screen === n.id ? 'page' : undefined} aria-label={collapsed ? n.label : undefined} title={n.label}><n.icon size={n.id === 'home' ? 16 : 18} aria-hidden /><span className="nav-label">{n.label}</span></button>;

  if (authErr) return <ToastProvider><div ref={shellRef} style={{ padding: 'var(--space-10)' }}><div className="empty surface"><Logo /><h3 style={{ marginTop: 'var(--space-3)' }}>{t.appName}</h3><p className="tx2">{t.auth.required}</p></div></div></ToastProvider>;

  return (
    <AppCtx.Provider value={state}><ToastProvider>
      <div className={`shell ${compact ? 'compact' : ''} ${embedded ? 'embedded' : ''}`} ref={shellRef}>
        {!compact && (
          <aside id="app-sidebar" className={`sidebar ${collapsed ? 'collapsed' : ''}`} aria-label={t.nav.mainLabel}>
            <div className="sidebar-head">
              <Logo />{!collapsed && <span className="sidebar-name">{t.appName}</span>}
              <button className="icon-btn" onClick={toggleSidebar} aria-expanded={!collapsed} aria-controls="app-sidebar" aria-label={collapsed ? t.nav.expand : t.nav.collapse} title={collapsed ? t.nav.expand : t.nav.collapse}>{collapsed ? <PanelLeftOpen size={18} aria-hidden /> : <PanelLeftClose size={18} aria-hidden />}</button>
            </div>
            {navButton(NEW_PROMPT, 'nav-new')}
            <div className="sidebar-group" role="group" aria-label={t.nav.groupWork}>
              {!collapsed && <div className="sidebar-group-label">{t.nav.groupWork}</div>}
              {WORK.map((n) => navButton(n))}
            </div>
            <div className="sidebar-group" role="group" aria-label={t.nav.groupSystem}>
              {!collapsed && <div className="sidebar-group-label">{t.nav.groupSystem}</div>}
              {systemNav.map((n) => navButton(n))}
            </div>
            <div className="sidebar-spacer" />
            <div className="sidebar-foot">
              {navButton(SETTINGS)}
              <button className="nav-item status" onClick={() => go('reports')} aria-label={agentLabel} title={agentLabel}><span className={`dot ${agentDot}`} aria-hidden /><span className="nav-label">{agentLabel}</span></button>
              <div className="sidebar-user">
                <span className="avatar" title={userName} aria-label={userName}>{initials(me?.name ?? '')}</span>
                {!collapsed && <span className="sidebar-username">{userName}</span>}
                <button className="icon-btn" aria-label={themeLabel} title={themeLabel} onClick={cycleTheme}><ThemeIcon size={18} aria-hidden /></button>
              </div>
            </div>
          </aside>
        )}
        <div className="main">
          {compact && (
            <header className="topbar">
              <Logo /><h2 style={{ fontSize: 'var(--font-size-h3)' }}>{t.appName}</h2><div className="grow" />
              <button className="icon-btn" onClick={() => go('reports')} aria-label={agentLabel} title={agentLabel}><span className={`dot ${agentDot}`} aria-hidden /></button>
              <button className="icon-btn" aria-label={themeLabel} title={themeLabel} onClick={cycleTheme}><ThemeIcon size={18} aria-hidden /></button>
              <span className="avatar" title={userName} aria-label={userName}>{initials(me?.name ?? '')}</span>
            </header>
          )}
        {compact && <nav className="bottom-tabs" aria-label={t.nav.tabsLabel}>
          {mainNav.map((n) => <button key={n.id} className={`nav-item ${screen === n.id ? 'on' : ''}`} onClick={() => go(n.id)} aria-current={screen === n.id ? 'page' : undefined} aria-label={n.label}><n.icon size={20} aria-hidden /><span>{n.id === 'optimizer' ? t.nav.optimizerShort : n.id === 'library' ? t.nav.libraryShort : n.label}</span></button>)}
          {moreNav.length > 0 && <button className="nav-item" onClick={() => setMoreOpen(true)} aria-label={t.nav.more}><MoreHorizontal size={20} aria-hidden /><span>{t.nav.more}</span></button>}
        </nav>}
          <main className="content">
            {agent?.paused_reason && <div className="banner err" role="alert"><span className="grow">{agent.paused_reason.startsWith('quota') ? t.banner.quota : t.banner.paused}</span></div>}
            {screen !== 'home' && agent?.scheduler_mode === 'lazy' && <div className="banner warn"><span className="grow">{t.banner.fallback}</span></div>}
            <Boundary key={screen}>
              {screen === 'home' && <HomeScreen />}{screen === 'generator' && <GeneratorScreen />}{screen === 'history' && <HistoryScreen />}{screen === 'templates' && <TemplatesScreen />}
              {screen === 'favorites' && <FavoritesScreen />}{screen === 'skills' && <SkillsScreen />}{screen === 'reports' && <ReportsScreen />}{screen === 'settings' && <SettingsScreen />}
              {screen === 'optimizer' && <OptimizerScreen />}{screen === 'library' && <LibraryScreen />}
              {screen === 'analytics' && (meLoaded ? <AnalyticsScreen /> : <Spinner />)}
            </Boundary>
          </main>
        </div>
        {moreOpen && <Modal title={t.nav.more} onClose={() => setMoreOpen(false)}>{moreNav.map((n) => <button key={n.id} className="nav-item" onClick={() => go(n.id)}><n.icon size={20} aria-hidden />{n.label}</button>)}</Modal>}
      </div>
      {waking && <div className="overlay" style={{ zIndex: 80 }} role="alert"><div className="surface empty" style={{ maxWidth: 420 }}><Logo /><h3 style={{ margin: 'var(--space-3) 0 var(--space-2)' }}>{t.wake.title}</h3><p className="tx2" style={{ margin: '0 0 var(--space-3)' }}>{t.wake.hint}</p><Spinner /></div></div>}
    </ToastProvider></AppCtx.Provider>
  );
}
