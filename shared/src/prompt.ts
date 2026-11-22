import { z } from 'zod';

export const PROMPT_CRITERIA = ['role', 'context', 'constraints', 'format'] as const;
const HEADINGS: Record<(typeof PROMPT_CRITERIA)[number], RegExp> = {
  role: /^(?:role|persona|роль|персона)\s*(?:[:：-]|\s*$)/iu,
  context: /^(?:context|background|audience|контекст|исходные данные|аудитория)\s*(?:[:：-]|\s*$)/iu,
  constraints: /^(?:constraints?|requirements?|rules?|ограничения?|требования|правила)\s*(?:[:：-]|\s*$)/iu,
  format: /^(?:output(?: format)?|response(?: format)?|format|deliverables?|формат(?: (?:ответа|вывода))?|результат)\s*(?:[:：-]|\s*$)/iu,
};
const CUES = {
  role: /(?:^|\s)(?:you are|act as|assume the role of|ты —|ты[- ](?:эксперт|редактор|консультант)|выступи в роли|представь, что ты)\s/iu,
  context: /(?:^|\s)(?:target audience|intended for|our team|known facts|для команды|целевая аудитория|исходные данные|у нас есть|для клиентов)(?=[\s:,.]|$)/iu,
  constraints: /(?:^|\s)(?:no more than|at most|do not|must not|avoid|only use|не более|не длиннее|не добавляй|не используй|без вымысла|только по)(?=[\s:,.]|$)/iu,
  format: /(?:^|\s)(?:as a table|in json|in markdown|as a checklist|in bullet points|в виде таблицы|в формате json|в markdown|в виде списка|структурируй ответ)(?=[\s:,.]|$)/iu,
};
const linesOf = (text: string) => text.split('\n').map((line) =>
  line.trim().replace(/^(?:#{1,6}\s*|[-*]\s+|\d+\.\s+)/, '').replace(/\*\*/g, ''));
const TAG: Record<(typeof PROMPT_CRITERIA)[number], RegExp> = {
  role: /<(?:role|identity)>\s*[^<\s]/iu,
  context: /<(?:context|background)>\s*[^<\s]/iu,
  constraints: /<(?:constraints|requirements)>\s*[^<\s]/iu,
  format: /<(?:output_format|format|output)>\s*[^<\s]/iu,
};

export function promptChecklist(text: string) {
  const lines = linesOf(text);
  return PROMPT_CRITERIA.map((id) => ({
    id, present: lines.some((line, index) => {
      const title = HEADINGS[id].exec(line);
      if (!title) return false;
      if (line.slice(title[0].length).trim()) return true;
      const next = lines.slice(index + 1).find(Boolean);
      return !!next && !Object.values(HEADINGS).some((heading) => heading.test(next));
    }) || CUES[id].test(text) || TAG[id].test(text),
  }));
}

export const START_MODES = ['auto', 'generate', 'magic', 'clarify', 'template', 'reverse'] as const;
export type StartMode = (typeof START_MODES)[number];

export function inferPromptRoute(text: string): Exclude<StartMode, 'auto' | 'template' | 'reverse'> {
  const trimmed = text.trim();
  const structure = promptChecklist(trimmed).filter((criterion) => criterion.present).length;
  if (structure >= 2 || (structure > 0 && trimmed.length >= 240) || trimmed.length > 8000) return 'magic';
  if (isHypothesisTask(trimmed)) return 'generate';
  const idea = /^(?:идея|гипотеза|мысль|предположение|планирую|хочу|думаю|предлагаю|мы можем|а что если|может быть|idea|hypothesis|what if|i (?:want|think|plan))(?=[\s:,.?!]|$)/iu;
  const task = /(?:^|[.!?\n;:]\s*)(?:помоги|напиши|перепиши|составь|объясни|придумай|сделай|разбери|проанализируй|оцени|подготовь|создай|переведи|разработай|предложи|write|rewrite|build|create|draft|summarize|analy[sz]e|translate|explain|generate|help)(?=[\s:,.]|$)/iu;
  if (idea.test(trimmed) && !task.test(trimmed)) return 'clarify';
  if (trimmed.length < 10) return 'clarify';
  return 'generate';
}

export const isHypothesisTask = (text: string) =>
  /^(?:помоги проверить гипотезу|проверь гипотезу|validate (?:this|my) hypothesis)(?=[\s:,.!?]|$)/iu.test(text.trim());

const VARIABLE = /(?<![\[{])(?:\[([^\[\]\n\r]{2,60})\](?![(\]])|\{\{\s*([\p{L}\p{M}\p{N}_-]{1,60})\s*\}\}(?!\}))/gu;
function variableName(bracket: string | undefined, brace: string | undefined) {
  const name = brace ?? bracket?.trim();
  return name && (brace || /\p{L}/u.test(name)) ? name : undefined;
}
export function extractPromptVariables(text: string): string[] {
  const names = new Set<string>();
  for (const match of text.matchAll(VARIABLE)) {
    const name = variableName(match[1], match[2]);
    if (name) names.add(name);
  }
  return [...names];
}
export function fillPromptVariables(text: string, values: Readonly<Record<string, string>>): string {
  return text.replace(VARIABLE, (match, bracket: string | undefined, brace: string | undefined) => {
    const name = variableName(bracket, brace);
    return name && Object.hasOwn(values, name) && values[name]?.trim() ? values[name]! : match;
  });
}

export const PROMPT_BODY_MAX = 20_000;
export const EXECUTION_MAX = 60_000;
export const promptRevisionSchema = z.object({
  body: z.string().trim().min(1).max(PROMPT_BODY_MAX),
  expected_version: z.number().int().positive(),
});
export interface PromptVersion { version: number; body: string; created_at: string }
export interface PromptVersions { current_version: number; items: PromptVersion[] }
export interface PromptExecution { text: string; model: string }
export const promptIdSchema = z.object({ id: z.string().min(1).max(60) });
