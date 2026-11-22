import { createContext, useContext } from 'react';
import type { GenOptions, Settings, SystemId } from '../../../shared/src/index.ts';

export interface Me { user_id: string; name: string; role: string; is_admin: boolean }
export interface AgentStatus { scheduler_mode: 'job' | 'lazy'; auto_refresh_enabled: boolean; paused_reason: string | null; busy: boolean; next_check_at: string | null; job_secret_configured: boolean; timezone: string }
export interface Prefill { raw_input: string; systems?: SystemId[]; language?: 'ru' | 'en'; options?: Partial<GenOptions>; nonce: number }
export type Screen = 'generator' | 'history' | 'templates' | 'favorites' | 'skills' | 'reports' | 'settings' | 'analytics' | 'optimizer' | 'library';
export interface AppState {
  me: Me | null; settings: Settings | null; agent: AgentStatus | null; go: (s: Screen) => void; prefill: Prefill | null; setPrefill: (p: Omit<Prefill, 'nonce'>, go?: boolean) => void;
  reload: () => void; setSettings: (s: Settings) => void; openGeneration: (id: string) => void; openGenerationId: string | null; clearOpenGeneration: () => void; theme: 'dark' | 'light' | 'system'; setTheme: (t: 'dark' | 'light' | 'system') => void;
}
export const AppCtx = createContext<AppState>(null as unknown as AppState);
export const useApp = () => useContext(AppCtx);
