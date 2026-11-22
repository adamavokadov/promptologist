import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react';
import { Check, Copy, X, Star } from 'lucide-react';
import { marked } from 'marked';
import DOMPurify from 'dompurify';
import { SYSTEM_NAMES, type SystemId } from '../../../shared/src/index.ts';
import { t } from './strings.ru.ts';

export const SYSTEM_COLORS: Record<SystemId, string> = { claude: 'var(--color-system-claude)', chatgpt: 'var(--color-system-chatgpt)', kimi: 'var(--color-system-kimi)', qwen: 'var(--color-system-qwen)', grok: 'var(--color-system-grok)' };
export const SystemDot = ({ id }: { id: SystemId }) => <span className="dot" style={{ background: SYSTEM_COLORS[id] }} aria-hidden />;
export const SystemChip = ({ id }: { id: SystemId }) => <span className="chip static"><SystemDot id={id} />{SYSTEM_NAMES[id]}</span>;

// ---- toasts ----
interface ToastItem { id: number; text: string; kind: 'ok' | 'err' | 'info' }
const ToastCtx = createContext<(text: string, kind?: ToastItem['kind']) => void>(() => {});
export const useToast = () => useContext(ToastCtx);
export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]); const n = useRef(0);
  const push = useCallback((text: string, kind: ToastItem['kind'] = 'info') => {
    const id = ++n.current; setItems((x) => [...x, { id, text, kind }]);
    setTimeout(() => setItems((x) => x.filter((i) => i.id !== id)), 3500);
  }, []);
  return <ToastCtx.Provider value={push}>{children}<div className="toasts" role="status" aria-live="polite">{items.map((i) => <div key={i.id} className={`toast glass ${i.kind}`}>{i.text}</div>)}</div></ToastCtx.Provider>;
}

// ---- clipboard with fallback (iframes may block navigator.clipboard) ----
export async function copyText(text: string): Promise<boolean> {
  try { await navigator.clipboard.writeText(text); return true; } catch { /* fall through */ }
  try {
    const ta = document.createElement('textarea'); ta.value = text; ta.style.position = 'fixed'; ta.style.opacity = '0'; document.body.appendChild(ta); ta.select();
    const ok = document.execCommand('copy'); document.body.removeChild(ta); return ok;
  } catch { return false; }
}
export function CopyButton({ text, label = t.common.copy, primary = false }: { text: string; label?: string; primary?: boolean }) {
  const [done, setDone] = useState(false); const toast = useToast();
  return <button className={`btn sm ${primary ? 'primary' : ''}`} onClick={async () => { if (await copyText(text)) { setDone(true); toast(t.common.copied, 'ok'); setTimeout(() => setDone(false), 1500); } else toast(t.common.error, 'err'); }}>
    {done ? <Check size={15} /> : <Copy size={15} />}{label}</button>;
}
export const StarButton = ({ on, onClick }: { on: boolean; onClick: () => void }) => (
  <button className="icon-btn" aria-label={on ? t.common.unfavorite : t.common.favorite} aria-pressed={on} onClick={onClick}><Star size={18} fill={on ? 'var(--color-warning)' : 'none'} color={on ? 'var(--color-warning)' : 'currentColor'} /></button>
);

// ---- modal / drawer with focus trap and Esc ----
function useTrap(onClose: () => void) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const prev = document.activeElement as HTMLElement | null; const el = ref.current;
    const focusable = () => Array.from(el?.querySelectorAll<HTMLElement>('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])') ?? []).filter((x) => !x.hasAttribute('disabled'));
    (focusable()[0] ?? el)?.focus();
    const key = (e: KeyboardEvent) => {
      if (e.key === 'Escape') { e.stopPropagation(); onClose(); }
      if (e.key === 'Tab') { const f = focusable(); if (!f.length) return; const first = f[0]!; const last = f[f.length - 1]!;
        if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); } else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); } }
    };
    document.addEventListener('keydown', key);
    return () => { document.removeEventListener('keydown', key); prev?.focus?.(); };
  }, [onClose]);
  return ref;
}
export function Modal({ title, onClose, children, wide = false, footer }: { title: string; onClose: () => void; children: ReactNode; wide?: boolean; footer?: ReactNode }) {
  const ref = useTrap(onClose);
  return <div className="overlay" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
    <div ref={ref} className={`glass modal ${wide ? 'wide' : ''}`} role="dialog" aria-modal="true" aria-label={title} tabIndex={-1}>
      <div className="row spread" style={{ marginBottom: 14 }}><h3>{title}</h3><button className="icon-btn" aria-label={t.common.close} onClick={onClose}><X size={18} /></button></div>
      <div className="col">{children}</div>{footer && <div className="row" style={{ justifyContent: 'flex-end', marginTop: 16 }}>{footer}</div>}
    </div></div>;
}
export function Drawer({ title, onClose, children }: { title: ReactNode; onClose: () => void; children: ReactNode }) {
  const ref = useTrap(onClose);
  return <div className="overlay" style={{ justifyContent: 'flex-end', padding: 0 }} onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
    <div ref={ref} className="glass drawer" role="dialog" aria-modal="true" tabIndex={-1}>
      <div className="row spread" style={{ marginBottom: 16 }}><h2>{title}</h2><button className="icon-btn" aria-label={t.common.close} onClick={onClose}><X size={20} /></button></div>{children}
    </div></div>;
}
export function ConfirmModal({ title, text, danger = false, onConfirm, onClose }: { title: string; text: string; danger?: boolean; onConfirm: () => void; onClose: () => void }) {
  return <Modal title={title} onClose={onClose} footer={<><button className="btn" onClick={onClose}>{t.common.cancel}</button><button className={`btn ${danger ? 'danger' : 'primary'}`} onClick={() => { onConfirm(); onClose(); }}>{t.common.confirm}</button></>}><p className="tx2" style={{ margin: 0 }}>{text}</p></Modal>;
}

export const Switch = ({ on, onChange, label, disabled }: { on: boolean; onChange: (v: boolean) => void; label: string; disabled?: boolean }) =>
  <button type="button" role="switch" aria-checked={on} aria-label={label} disabled={disabled} className={`switch ${on ? 'on' : ''}`} onClick={() => onChange(!on)} />;
export function Seg<T extends string>({ value, options, onChange, label }: { value: T; options: { value: T; label: string }[]; onChange: (v: T) => void; label: string }) {
  return <div className="seg" role="group" aria-label={label}>{options.map((o) => <button key={o.value} type="button" className={o.value === value ? 'on' : ''} aria-pressed={o.value === value} onClick={() => onChange(o.value)}>{o.label}</button>)}</div>;
}
export const Empty = ({ title, hint, cta }: { title: string; hint?: string; cta?: ReactNode }) =>
  <div className="empty glass"><div className="glyph" aria-hidden>{t.empty.glyph}</div><h3 style={{ marginTop: 8 }}>{title}</h3>{hint && <p className="tx2" style={{ margin: '6px 0 14px' }}>{hint}</p>}{cta}</div>;
export const Skeletons = ({ n = 3, h = 90 }: { n?: number; h?: number }) => <div className="col">{Array.from({ length: n }, (_, i) => <div key={i} className="skeleton glass" style={{ height: h }} />)}</div>;
export const Spinner = () => <span className="spinner" aria-hidden />;

// ---- helpers ----
export function daysFrom(iso: string | null | undefined, now = Date.now()): number | null { return iso ? Math.round((Date.parse(iso) - now) / 86_400_000) : null; }
export function fmtDate(iso: string): string { return new Date(iso).toLocaleString('ru-RU', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }); }
export function renderMarkdown(md: string): string { return DOMPurify.sanitize(marked.parse(md, { async: false }) as string, { FORBID_TAGS: ['style', 'script', 'iframe'], USE_PROFILES: { html: true } }); }
export const Markdown = ({ md }: { md: string }) => <div className="md" dangerouslySetInnerHTML={{ __html: renderMarkdown(md) }} />;

/** Highlights XML tags and Markdown headings without a heavy syntax highlighter. */
export function HighlightedPrompt({ text }: { text: string }) {
  const parts = text.split(/(<\/?[a-zA-Z_][\w-]*>|^#{1,6} .*$|^#[A-Za-z]+#)/gm);
  return <>{parts.map((p, i) => (/^<\/?[a-zA-Z_][\w-]*>$/.test(p) ? <span key={i} className="hl-tag">{p}</span> : /^(#{1,6} .*|#[A-Za-z]+#)$/.test(p) ? <span key={i} className="hl-head">{p}</span> : <span key={i}>{p}</span>))}</>;
}
export function useDebounced<T>(value: T, ms = 300): T {
  const [v, setV] = useState(value);
  useEffect(() => { const id = setTimeout(() => setV(value), ms); return () => clearTimeout(id); }, [value, ms]);
  return v;
}
