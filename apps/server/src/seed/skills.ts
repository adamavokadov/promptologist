import { PROTECTED_INVARIANTS, GOLDEN_SET, type SystemId } from '../../../../shared/src/index.ts';

export const SEED_DATE = '2026-11-13';
export interface SeedSkill {
  id: SystemId; display_name: string; model_lineup: string[]; sources: { url: string; title: string; checked_at: string }[]; body_md: string;
}

const src = (url: string, title: string) => ({ url, title, checked_at: SEED_DATE });
const INVARIANTS = PROTECTED_INVARIANTS.map((s) => `- ${s}`).join('\n');
const section = (principles: string, structure: string, style: string, anti: string, checklist: string, usage: string) => `## Principles
${principles}

### Protected invariants (never remove or weaken)
${INVARIANTS}

## Target Structure
${structure}

## Style & Formatting
${style}

## Antipatterns
${anti}

## Validation Checklist
${checklist}

## Usage Notes
${usage}
`;

export const SEED_SKILLS: SeedSkill[] = [
  {
    id: 'claude', display_name: 'Claude',
    model_lineup: ['Claude Opus 5.5', 'Claude Sonnet 5.5', 'Claude Haiku 5.5', 'Claude Fable 5.2', 'Claude Mythos 5.2'],
    sources: [
      src('https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices', 'Claude prompting best practices'),
      src('https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/overview', 'Prompt engineering overview'),
    ],
    body_md: section(
`- Be clear and direct: state the task, the audience and the success criteria explicitly.
- Separate instructions, context and data with XML tags (\`<task>\`, \`<context>\`, \`<constraints>\`, \`<output_format>\`).
- Use few-shot examples inside tags when the output format matters; keep them short and representative.
- Give a role in one sentence when expertise matters.
- Models are proactive: do not add pressure or anti-laziness language.
- Mention adaptive thinking and the effort parameter in usage notes only; do not advise deprecated \`budget_tokens\` or prefill.
- For multi-turn use keep history append-only and leave thinking blocks unchanged.`,
`Role -> task in tags -> context -> constraints -> output format -> quality criteria.
\`\`\`
<role>one sentence</role>
<task>what to do and why</task>
<context>facts, audience, source material</context>
<constraints>hard limits, must/must-not</constraints>
<output_format>exact shape of the answer</output_format>
<quality_criteria>how the answer is judged</quality_criteria>
\`\`\``,
`- XML tag names stay in English; the prompt prose follows the selected output language.
- Short imperative sentences. No filler, no motivational phrases.
- Put long documents at the top and the question at the end when the prompt embeds data.`,
`- Walls of undifferentiated prose without tags.
- Contradictory or duplicated instructions.
- Anti-laziness pressure, ALL-CAPS shouting, threats or tips.
- Inventing facts that the user did not provide.`,
`- Contains a \`<task>\` section (\`has:<task>\`).
- Contains an \`<output_format>\` section (\`has:<output_format>\`).
- Contains a \`<constraints>\` section (\`has:<constraints>\`).
- Placeholders use the form [specify: ...] / [укажите: ...] instead of invented facts.
- The prompt states the output language explicitly.`,
`Works for the Claude family. Suggest an effort level (low for simple, high for hard reasoning) and note that thinking is adaptive. Recommend Opus-class models for the hardest tasks and Sonnet/Haiku-class for speed.`),
  },
  {
    id: 'chatgpt', display_name: 'ChatGPT',
    model_lineup: ['GPT-6 Astra', 'GPT-6.1 Sol', 'GPT-6.1 Terra', 'GPT-6 Luna'],
    sources: [
      src('https://developers.openai.com/api/docs/guides/latest-model', 'Latest model guide'),
      src('https://developers.openai.com/api/docs/guides/prompt-engineering', 'Prompt engineering guide'),
      src('https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra', 'Rethinking skills and prompts for GPT-6 Astra'),
    ],
    body_md: section(
`- Structure developer-style instructions as Identity -> Instructions -> Examples -> Context, using Markdown headings and XML tags for data.
- Astra tends to ask clarifying questions or stop early: include an initiative block ("bias towards action", "persist until the task is complete").
- State instruction priority explicitly: the user's instructions outrank files and skills.
- Specify style explicitly and ban filler patterns ("delve", "foster", "Bottom Line:", "X, not Y" contrasts).
- Keep instructions short and precise; avoid overloading.
- Name the reasoning effort in usage notes (Astra and Sol do not support \`none\`).`,
`\`\`\`
# Identity
who the assistant is and the quality bar
# Instructions
numbered, testable rules, including the initiative / follow-through block
# Examples
optional, one or two short pairs
# Context
<data> tags with the user's material
# Output format
exact structure and length
\`\`\``,
`- Headings stay in English; prose follows the selected output language.
- Prefer numbered rules over paragraphs. One idea per rule.
- Explicit length target in paragraphs or bullets.`,
`- Long vague mission statements.
- Piling up every possible rule.
- Letting file content override the user's instructions.
- Marketing-style filler phrases.`,
`- Contains a \`# Identity\` section (\`has:# Identity\`).
- Contains a \`# Instructions\` section (\`has:# Instructions\`).
- Contains an initiative / follow-through rule (\`has-any:persist|bias towards action|до полного завершения|до конца\`).
- States the output format and length.
- No invented facts; assumptions are explicit.`,
`Recommend a reasoning effort (medium by default, high for analysis). Astra is the flagship; Sol/Terra trade depth for speed and cost; Luna is the lightweight option.`),
  },
  {
    id: 'kimi', display_name: 'Kimi',
    model_lineup: ['Kimi K2', 'Kimi K2 Thinking', 'Kimi K2.5', 'Kimi K3'],
    sources: [src('https://platform.kimi.ai/docs/guide/prompt-best-practice', 'Kimi prompt best practices')],
    body_md: section(
`- Give clear instructions and every relevant detail of the context; do not assume the model guesses.
- Set the role in a system-style opening sentence.
- Use delimiters (triple quotes, XML tags or headings) to mark data sections.
- Spell out the task as explicit steps (Step 1 / Step 2 / Step 3).
- Provide few-shot examples when the format matters.
- Specify length in paragraphs or bullet points, not words.
- Decompose complex tasks; for long documents summarise recursively.`,
`Role -> context in delimiters -> task -> numbered steps -> format and length -> constraints.
\`\`\`
You are <role>.
### Context
"""..."""
### Task
...
### Steps
Step 1: ...
Step 2: ...
### Output format and length
...
### Constraints
...
\`\`\``,
`- Delimiters are mandatory around user material.
- Steps are short, ordered and verifiable.
- Length is given as paragraphs/bullets.`,
`- Mixing instructions with data without delimiters.
- A single huge task without decomposition.
- Word-count targets.
- Omitting context the model cannot infer.`,
`- Contains explicit steps (\`has-any:Step 1|Шаг 1\`).
- Uses delimiters around context (\`has-any:###|"""|<\`).
- States format and length in paragraphs or bullets.
- Includes a constraints block.
- Assumptions are explicit, no invented facts.`,
`Thinking is the default on recent Kimi models and supports long agentic chains. Mention that very long documents should be summarised in stages.`),
  },
  {
    id: 'qwen', display_name: 'Qwen',
    model_lineup: ['Qwen3.7 Max', 'Qwen3.7 Plus', 'Qwen3.8 Flash'],
    sources: [
      src('https://www.alibabacloud.com/help/en/model-studio/prompt-engineering-guide', 'Model Studio prompt engineering guide'),
      src('https://qwen.readthedocs.io', 'Qwen documentation'),
    ],
    body_md: section(
`- Use the official framework: #Background# / #Purpose# / #Style# / #Tone# / #Audience# / #Outputs#.
- Separate sections with \`###\`.
- Output examples are the strongest protection against hallucination.
- List explicit task steps; for hard tasks ask for reasoning first, then the answer.
- Thinking and non-thinking modes exist; soft switches \`/think\` and \`/no_think\` are available.
- For structured output provide a JSON template plus constraints ("JSON only", "do not change the original").
- Fix the answer language explicitly (equal to the request language).`,
`\`\`\`
#Background#
#Purpose#
#Style#
#Tone#
#Audience#
#Outputs#
### Steps
### Output example
\`\`\``,
`- Framework markers stay exactly as written; prose follows the selected output language.
- Keep each section to a few concise lines.
- Provide at least one short output example.`,
`- Skipping #Outputs#.
- No example of the desired output.
- Leaving the answer language implicit.
- Asking for JSON without a template.`,
`- Contains \`#Background#\` (\`has:#Background#\`).
- Contains \`#Purpose#\` (\`has:#Purpose#\`).
- Contains \`#Outputs#\` (\`has:#Outputs#\`).
- Includes an output example.
- States the answer language explicitly.`,
`Recommend thinking mode for multi-step reasoning and \`/no_think\` for simple lookups. Qwen3.7/3.8 Max is the strongest tier, Plus balances cost, Flash is fastest.`),
  },
  {
    id: 'grok', display_name: 'Grok',
    model_lineup: ['Grok 4.7'],
    sources: [
      src('https://docs.x.ai/developers/model-capabilities/text/best-practices', 'xAI text best practices'),
      src('https://docs.x.ai/developers/grok-4-7', 'Grok 4.7 guide'),
    ],
    body_md: section(
`- State the task, constraints and output format directly; avoid extra scaffolding.
- Grok 4.7 has a 500K context window.
- Name the reasoning effort explicitly (low / medium / high / xhigh; default is high).
- Recommend sampling temperature 0.7 and top_p 0.95 in usage notes and do not suggest deviating.
- For multi-turn agents: return encrypted reasoning unchanged, use \`prompt_cache_key\` per conversation, keep history append-only and static content first.
- Use streaming and long timeouts for long outputs.`,
`Direct task -> context -> hard constraints -> output format -> (agent scenarios only) tool rules.
\`\`\`
Task: ...
Context: ...
Constraints: ...
Output format: ...
Tool rules: (only for agent tasks)
\`\`\``,
`- Plain labelled blocks, no decoration.
- Constraints are hard and testable.
- Static content first to benefit from caching.`,
`- Over-engineered wrappers.
- Soft, ambiguous constraints.
- Changing sampling parameters away from the recommendation.
- Rewriting history in multi-turn flows.`,
`- Contains a task statement (\`has-any:Task|Задача\`).
- Contains constraints (\`has-any:Constraints|Ограничения\`).
- Contains an output format (\`has-any:Output format|Формат\`).
- Direct, no filler.
- Assumptions are explicit, no invented facts.`,
`Recommend temperature 0.7 / top_p 0.95 and an explicit reasoning effort (high by default). Mention streaming for long answers.`),
  },
];

export function seedFrontmatter(s: SeedSkill, version: number): Record<string, unknown> {
  return {
    skill_id: s.id, version, target_system: s.display_name, model_lineup: s.model_lineup, last_verified: SEED_DATE,
    sources: s.sources, protected_invariants: [...PROTECTED_INVARIANTS],
    output_language_rule: 'The finished prompt is written in the language chosen by the user (ru/en); explanations are always in Russian.',
    golden_set: GOLDEN_SET.map((g) => ({ ...g })),
  };
}
