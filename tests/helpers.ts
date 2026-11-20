import { openDb, type Db } from '../apps/server/src/db.ts';
import { seedAll } from '../apps/server/src/skills.ts';
import type { VibeClient } from '../apps/server/src/vibe.ts';

export function freshDb(): Db { const db = openDb(':memory:'); seedAll(db); return db; }

export const RU_PROMPT = 'Ты — опытный аналитик. <task>Проанализируй договор аренды и выдели рисковые пункты.</task> <constraints>Не выдумывай факты, используй [укажите: стороны].</constraints> <output_format>Список пунктов с оценкой риска.</output_format> # Identity Ты аналитик. # Instructions 1. Работай до конца и persist до полного завершения. Step 1: прочитай. Шаг 1: прочитай. ### Контекст #Background# договор #Purpose# анализ #Outputs# список. Task: анализ. Constraints: без выдумок. Output format: список. Отвечай на русском языке.';
export const EN_PROMPT = 'You are an expert analyst. <task>Review the lease and flag risky clauses.</task> <constraints>Do not invent facts.</constraints> <output_format>A list of clauses with risk.</output_format> # Identity An analyst. # Instructions 1. Persist until the task is complete. Step 1: read. ### Context #Background# lease #Purpose# review #Outputs# list. Task: review. Constraints: none. Output format: list. Respond in English.';

export interface FakeOpts {
  language?: 'ru' | 'en';
  intent?: Record<string, unknown>;
  failSystems?: string[];            // transformer returns invalid JSON for these (skill display name in system prompt)
  analyzer?: Record<string, unknown> | ((n: number) => Record<string, unknown>);
  judgeWinner?: 'A' | 'B' | 'tie' | 'new' | 'old';
  quota?: boolean;
  searchFails?: boolean;
  calls?: { chat: number; search: number; research: number; notify: number };
}
export function fakeVibe(o: FakeOpts = {}): VibeClient {
  const calls = o.calls ?? { chat: 0, search: 0, research: 0, notify: 0 };
  let analyzerN = 0;
  const lang = o.language ?? 'ru';
  const vibe: any = {
    async chat(_model: string, messages: { role: string; content: string }[]) {
      calls.chat++;
      if (o.quota) { const { VibeError } = await import('../apps/server/src/vibe.ts'); throw new VibeError(402, 'ai_quota_exhausted', 'quota', 'quota'); }
      const sys = messages[0]!.content;
      if (sys.startsWith('Ты анализируешь сырой запрос')) {
        return { content: JSON.stringify({ task_type: 'analysis', domain: 'legal', key_requirements: ['risks'], missing_info: [], suggested_assumptions: [], complexity: 'low', input_language: 'ru', ...o.intent }), totalTokens: 10, model: 'm' };
      }
      if (sys.includes('Промптолог, эксперт')) {
        const name = /для (\w+)\./.exec(sys)?.[1] ?? '';
        if (o.failSystems?.includes(name)) return { content: 'not json at all', totalTokens: 5, model: 'm' };
        return { content: JSON.stringify({ prompt: (lang === 'ru' ? RU_PROMPT : EN_PROMPT) + (sys.includes('NEWSKILL') ? ' NEWSKILL' : ''), improvements: ['a', 'b', 'c'], assumptions: [], usage_notes: 'n', estimated_tokens: 100 }), totalTokens: 50, model: 'm' };
      }
      if (sys.includes('агент обновления скиллов')) {
        const a = typeof o.analyzer === 'function' ? o.analyzer(analyzerN++) : o.analyzer;
        return { content: JSON.stringify(a ?? { changes_detected: false, significance: 'none', model_lineup: [], proposed_frontmatter: {}, proposed_body_md: '', changelog: [], confidence: 0.9 }), totalTokens: 100, model: 'm' };
      }
      if (sys.includes('независимый судья')) {
        const w = o.judgeWinner ?? 'tie';
        // the position of the new skill is random, so resolve "new"/"old" by checking which prompt has the marker
        let winner: string = w;
        if (w === 'new' || w === 'old') {
          const user = messages[1]!.content; const a = /<prompt_A>([\s\S]*?)<\/prompt_A>/.exec(user)?.[1] ?? '';
          const newIsA = a.includes('NEWSKILL');
          winner = (w === 'new') === newIsA ? 'A' : 'B';
        }
        return { content: JSON.stringify({ winner, scores: { intent: 8, structure: 8, completeness: 8, language: 9 }, reason: 'r' }), totalTokens: 30, model: 'm' };
      }
      if (sys === undefined) throw new Error('unexpected');
      return { content: 'pong', totalTokens: 1, model: 'm' };
    },
    async search() {
      calls.search++;
      if (o.searchFails) { const { VibeError } = await import('../apps/server/src/vibe.ts'); throw new VibeError(500, 'SEARCH_DOWN', 'down', 'server'); }
      const today = new Date().toISOString();
      return { results: [
        { url: 'https://platform.claude.com/docs/en/new-model-guide', title: 'Introducing the new model guide', content: 'New model release with migration notes', publishedDate: today },
        { url: 'https://evil.example.com/x', title: 'Not whitelisted', content: 'ignore', publishedDate: today },
        { url: 'https://www.anthropic.com/news/launch', title: 'Launch announcement', content: 'release of new model upgrade', publishedDate: today },
      ] };
    },
    async research() { calls.research++; return { text: 'research synthesis', tokens: 200 }; },
    async meService() { return { currentUser: { bitrixUserId: '1' } }; },
    async notify() { calls.notify++; },
    async me() { return { currentUser: { bitrixUserId: '42' }, portal: 'p.bitrix24.com' }; },
    async models() { return [{ id: 'bitrix/bitrixgpt-5.5', name: 'BitrixGPT' }]; },
    async usage() { return { total_tokens: 1 }; },
    async listJobs() { return []; },
    async createJob() { return { secret: 'vjs_' + 'A'.repeat(43) }; },
    request: async () => ({}),
    searchProviders: async () => ({}),
  };
  return vibe as VibeClient;
}
