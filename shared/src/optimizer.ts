import { z } from 'zod';

// ---------- constants ----------
export const OPT_WORKFLOWS = ['magic', 'clarify', 'template', 'reverse'] as const;
export type OptWorkflow = (typeof OPT_WORKFLOWS)[number];
export const GOAL_PRESETS = ['copywriting', 'coding', 'data', 'brainstorm', 'roleplay', 'learning'] as const;
export const FRAMEWORK_PRESETS = ['auto', 'cot', 'few_shot', 'costar', 'rtf', 'asd_ste100'] as const;
export const OPT_PRESETS = [...GOAL_PRESETS, ...FRAMEWORK_PRESETS] as const;
export type OptPreset = (typeof OPT_PRESETS)[number];
export const OUTPUT_FORMATS = ['none', 'table', 'json', 'markdown_list', 'prose', 'code', 'slides'] as const;
export const TONES = ['none', 'academic', 'persuasive', 'friendly', 'concise', 'no_yapping'] as const;
export const OPT_LIMITS = { rawMin: 3, rawMax: 12000, answerMax: 1000, promptMax: 20000, questions: 3, folderName: 60, maxFolders: 40 } as const;
export const DEFAULT_FOLDERS = [
  { key: 'work', name: 'Работа' }, { key: 'marketing', name: 'Маркетинг' }, { key: 'coding', name: 'Код' },
] as const;

/** Appended by the server, never by the model, when the language bridge is on. */
export const BRIDGE_CONSTRAINT = 'CRITICAL INSTRUCTION: Perform all internal reasoning in English, but deliver the final response strictly in natural, fluent Russian.';

// ---------- engine (provider, model, key) ----------
export const PROVIDERS = ['platform', 'anthropic', 'openai', 'google', 'alibaba', 'moonshot', 'custom'] as const;
export type Provider = (typeof PROVIDERS)[number];
export interface CatalogModel { id: string; label: string; verified: boolean; recommended?: boolean }
/** Model ids other than Anthropic's are taken from the product spec and are NOT verified against provider docs: use the custom model field if one differs. */
export const ENGINE_CATALOG: Record<Exclude<Provider, 'platform' | 'custom'>, CatalogModel[]> = {
  anthropic: [{ id: 'claude-opus-5-5', label: 'Claude Opus 5.5', verified: true, recommended: true }, { id: 'claude-sonnet-5-5', label: 'Claude Sonnet 5.5', verified: true }],
  openai: [{ id: 'chatgpt-6-omni', label: 'ChatGPT 6 Omni', verified: false }, { id: 'gpt-6-reasoning', label: 'GPT-6 Reasoning', verified: false }],
  google: [{ id: 'gemini-4-ultra', label: 'Gemini 4 Ultra', verified: false }, { id: 'gemini-4-pro', label: 'Gemini 4 Pro', verified: false }],
  alibaba: [{ id: 'qwen-4-max', label: 'Qwen 4 Max', verified: false }, { id: 'qwen-4-coder', label: 'Qwen 4 Coder', verified: false }],
  moonshot: [{ id: 'kimi-3.1-ultra', label: 'Kimi 3.1 Ultra', verified: false }],
};
export const engineConfigSchema = z.object({
  provider: z.enum(PROVIDERS).default('platform'),
  model: z.string().trim().min(1).max(120).default('bitrix/bitrixgpt-5.5'),
  base_url: z.string().trim().max(300).default(''),
  temperature: z.number().min(0).max(1.5).default(0.4),
});
export type EngineConfig = z.infer<typeof engineConfigSchema>;
export const engineUpdateSchema = engineConfigSchema.partial().extend({
  /** Plain key from the admin form. Empty string clears the stored key; omitted keeps it. */
  api_key: z.string().max(500).optional(),
});
export interface EngineView extends EngineConfig {
  has_key: boolean; key_hint: string; secret_configured: boolean;
  catalog: typeof ENGINE_CATALOG; default_base_urls: Record<string, string>;
}

// ---------- optimize requests and outputs ----------
export const optimizeRequestSchema = z.object({
  workflow: z.enum(OPT_WORKFLOWS).default('magic'),
  raw_input: z.string().trim().min(OPT_LIMITS.rawMin).max(OPT_LIMITS.rawMax),
  preset: z.enum(OPT_PRESETS).default('auto'),
  output_format: z.enum(OUTPUT_FORMATS).default('none'),
  tone: z.enum(TONES).default('none'),
  bridge: z.boolean().default(false),
});
export type OptimizeRequest = z.infer<typeof optimizeRequestSchema>;
export const answerRequestSchema = z.object({
  answers: z.array(z.string().max(OPT_LIMITS.answerMax)).max(OPT_LIMITS.questions).default([]),
  auto: z.boolean().default(false),
});

const score = z.coerce.number().transform((n) => Math.min(10, Math.max(1, Math.round(n * 10) / 10)));
const textList = z.array(z.string().trim().min(1).max(600)).max(12);
/** What the engine must return for an optimization run (parsed and validated server-side). */
export const optimizerOutputSchema = z.object({
  initial_score: score, initial_critique: z.string().trim().max(600).default(''), optimized_score: score,
  changelog_explanation: textList.min(1), final_prompt: z.string().trim().min(1).max(OPT_LIMITS.promptMax),
  framework_used: z.string().trim().max(60).default(''),
});
export type OptimizerOutput = z.infer<typeof optimizerOutputSchema>;
export const clarifierOutputSchema = z.object({ clarifying_questions: z.array(z.string().trim().min(3).max(300)).min(1).max(5) });
export const compressOutputSchema = z.object({ compressed_prompt: z.string().trim().min(1).max(OPT_LIMITS.promptMax) });

export interface OptimizationDTO {
  id: string; workflow: OptWorkflow; status: 'draft_questions' | 'ok'; raw_input: string; options: Omit<OptimizeRequest, 'raw_input' | 'workflow'>;
  clarifying_questions: string[]; answers: string[]; initial_score: number | null; initial_critique: string; optimized_score: number | null;
  changelog_explanation: string[]; final_prompt: string; framework_used: string; variables: string[]; var_values: Record<string, string>;
  compressed_prompt: string | null; tokens_before: number | null; tokens_after: number | null;
  is_favorite: boolean; folder_id: string | null; tags: string[]; provider: string; model: string; created_at: string;
}
export interface FolderDTO { id: string; name: string; is_default: boolean; count: number }

// ---------- helpers shared by server and UI ----------
/** Bracket variables as in the spec: [Insert Topic]. Links like [text](url) and nested or empty brackets are ignored. */
const BR_RE = /(?<!\[)\[([^\[\]\n]{2,60})\](?![(\]])/g;
export function extractBracketVars(text: string): string[] {
  const seen = new Set<string>();
  for (const m of text.matchAll(BR_RE)) { const v = m[1]!.trim(); if (/\p{L}/u.test(v)) seen.add(v); }
  return [...seen].slice(0, 20);
}
export function substituteBracketVars(text: string, values: Record<string, string>): string {
  return text.replace(BR_RE, (m, name: string) => { const v = values[name.trim()]; return v !== undefined && v !== '' ? v : m; });
}
/** Rough token estimate without a tokenizer: about 4 Latin characters, or 2.5 Cyrillic characters, per token. Always shown as approximate. */
export function estimateTokens(text: string): number {
  let latin = 0; let cyr = 0; let other = 0;
  for (const ch of text) {
    if (/\s/.test(ch)) continue;
    if (/[\u0400-\u04FF]/.test(ch)) cyr++; else if (/[\u0021-\u007E]/.test(ch)) latin++; else other++;
  }
  return Math.max(1, Math.ceil(latin / 4 + cyr / 2.5 + other * 0.8 + text.split(/\s+/).filter(Boolean).length * 0.1));
}
export function frameworkOf(preset: OptPreset): 'goal' | 'framework' { return (FRAMEWORK_PRESETS as readonly string[]).includes(preset) ? 'framework' : 'goal'; }
