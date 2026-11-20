import type { SystemId } from '../../../../shared/src/index.ts';
export interface SeedTemplate { title: string; description: string; language: 'ru' | 'en'; default_systems: SystemId[]; tags: string[]; body: string }
export const SEED_TEMPLATES: SeedTemplate[] = [
  { title: 'Анализ договора на риски', description: 'Разбор договора и список рисковых пунктов с рекомендациями.', language: 'ru', default_systems: ['claude', 'chatgpt'], tags: ['юридическое', 'анализ'],
    body: 'Проанализируй договор типа «{{contract_type}}» для стороны «{{party_role}}». Найди рисковые пункты, оцени серьёзность и предложи формулировки правок. Юрисдикция: {{jurisdiction}}.' },
  { title: 'Код-ревью Pull Request', description: 'Структурное ревью изменений с приоритетами замечаний.', language: 'ru', default_systems: ['claude', 'qwen', 'grok'], tags: ['код', 'ревью'],
    body: 'Проведи код-ревью pull request на языке {{language}}. Цель изменений: {{goal}}. Обрати внимание на {{focus_areas}}. Раздели замечания на блокирующие и рекомендательные.' },
  { title: 'План запуска продукта', description: 'Пошаговый план запуска с контрольными точками.', language: 'ru', default_systems: ['chatgpt', 'kimi'], tags: ['продукт', 'план'],
    body: 'Составь план запуска продукта «{{product}}» для аудитории «{{audience}}» на {{weeks}} недель. Бюджет: {{budget}}. Выдели контрольные точки и риски.' },
  { title: 'Резюме встречи с решениями', description: 'Краткое резюме, решения и задачи с ответственными.', language: 'ru', default_systems: ['claude', 'chatgpt', 'kimi'], tags: ['встречи', 'резюме'],
    body: 'Сделай резюме встречи «{{meeting_title}}». Из заметок ниже выдели принятые решения, открытые вопросы и задачи с ответственными и сроками.\n\n{{notes}}' },
  { title: 'Market research brief', description: 'A structured brief for market research on a product or niche.', language: 'en', default_systems: ['chatgpt', 'grok'], tags: ['research', 'marketing'],
    body: 'Prepare a market research brief for "{{product}}" in the {{market}} market. Target segment: {{segment}}. Cover size, competitors, trends and risks, and cite where facts must be verified.' },
  { title: 'Debug a failing test', description: 'Diagnose a failing test and propose a minimal fix.', language: 'en', default_systems: ['claude', 'qwen'], tags: ['code', 'debugging'],
    body: 'Help me debug a failing {{framework}} test. Test name: {{test_name}}. Error output:\n{{error_output}}\nExplain the likely cause and propose the smallest fix.' },
  { title: 'Social media content pack', description: 'A week of platform-specific posts with hooks and calls to action.', language: 'en', default_systems: ['chatgpt', 'kimi', 'grok'], tags: ['content', 'social'],
    body: 'Create a {{days}}-day social media content pack for {{brand}} on {{platform}}. Tone: {{tone}}. Include hooks, post text and a call to action for each day.' },
  { title: 'Learning roadmap', description: 'A staged learning plan with resources and milestones.', language: 'en', default_systems: ['claude', 'kimi', 'qwen'], tags: ['learning', 'plan'],
    body: 'Build a learning roadmap for {{topic}} for someone at {{level}} level with {{hours_per_week}} hours per week. Include milestones, practice projects and how to measure progress.' },
];
