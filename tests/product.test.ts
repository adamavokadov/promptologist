import { afterEach, describe, expect, it } from 'vitest';
import { mkdtempSync, rmSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { openDb } from '../apps/server/src/db.ts';
import { buildApp } from '../apps/server/src/routes.ts';
import { clearIdentityCache, resetRateLimits } from '../apps/server/src/auth.ts';
import type { ChatMessage, VibeClient } from '../apps/server/src/vibe.ts';
import { buildTransformerUser } from '../apps/server/src/generation.ts';
import { extractPromptVariables, fillPromptVariables, inferPromptRoute, optionsSchema, promptChecklist } from '../shared/src/index.ts';
import { fakeVibe, freshDb } from './helpers.ts';

const PORTAL = 'ee637767-f81d-4460-8c42-dd95262fb893';
const OTHER_PORTAL = 'c7db9de1-55b8-4620-b683-1d8a0f9b67ee';
const session = (id: string, role = 'MEMBER', portal = PORTAL) => ({
  'x-vibe-user-id': id, 'x-vibe-user-role': role, 'x-vibe-portal-id': portal,
});
const ADMIN = session('1', 'ADMIN');
const EDITOR = session('20');
const READER = session('21');
const EMPLOYEE = session('22');
const BODY = 'Роль: редактор.\nКонтекст: ответ на письмо {{Имя_клиента}}.\nОграничения: не выдумывай факты.\nФормат: письмо по [Текст письма].';
const CHANGE = 'Роль: старший редактор.\nФормат: короткий ответ.';

const cleanups: (() => void | Promise<void>)[] = [];
afterEach(async () => { for (const cleanup of cleanups.splice(0).reverse()) await cleanup(); });

async function fixture(overrides?: VibeClient['chat']) {
  resetRateLimits();
  clearIdentityCache();
  const db = freshDb();
  const base = fakeVibe();
  const calls: ChatMessage[][] = [];
  const chat: VibeClient['chat'] = async (model, messages, options) => {
    calls.push(messages);
    if (overrides) return overrides(model, messages, options);
    const system = messages[0]?.content ?? '';
    const content = system.includes('prepare an interview') ? JSON.stringify({ clarifying_questions: ['Какая аудитория?', 'Какая цель?', 'Какие ресурсы?'] })
      : system.includes('Suggest one short') ? JSON.stringify({ answers: ['Новые клиенты', 'Проверить интерес', 'Две недели'] })
      : system.includes('prompt compressor') ? JSON.stringify({ compressed_prompt: 'Роль: редактор. {{Имя_клиента}}, [Текст письма].' })
      : system.startsWith('You are a prompt engineer') ? JSON.stringify({ final_prompt: BODY, changelog_explanation: ['Уточнены условия.'] })
      : '';
    if (content) return { content, totalTokens: 4, model: 'test' };
    if (messages.length === 1) return { content: 'Готовый ответ', totalTokens: 4, model: 'test' };
    return base.chat(model, messages, options);
  };
  const app = await buildApp({ db, vibe: { ...base, chat } });
  cleanups.push(() => db.raw.close(), () => app.close());
  return {
    db, app, calls,
    async call(method: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE', url: string, headers = ADMIN, payload?: Record<string, unknown>) {
      const result = await app.inject({ method, url, headers, payload });
      return { status: result.statusCode, data: result.json() };
    },
  };
}

describe('shared prompt behavior', () => {
  it('routes structured text, a concrete task, an idea and a hypothesis preset', () => {
    expect(inferPromptRoute(BODY)).toBe('magic');
    expect(inferPromptRoute('Напиши письмо клиенту о переносе встречи')).toBe('generate');
    expect(inferPromptRoute('Идея: отправлять новые подборки клиентам по пятницам')).toBe('clarify');
    expect(inferPromptRoute('Помоги проверить гипотезу: демо повысит конверсию')).toBe('generate');
    const prompt = buildTransformerUser(null, 'Гипотеза: демо поможет клиентам', optionsSchema.parse({ task_type: 'hypothesis' }));
    expect(prompt).toContain('success and stop thresholds');
  });
  it('checks text criteria and fills the two placeholder styles without evaluating links or the prototype', () => {
    expect(promptChecklist(BODY).map(({ present }) => present)).toEqual([true, true, true, true]);
    expect(promptChecklist('Напиши письмо клиенту').some(({ present }) => present)).toBe(false);
    const text = BODY + ' [Справка](https://example.org) {{constructor}}';
    expect(extractPromptVariables(text)).toEqual(['Имя_клиента', 'Текст письма', 'constructor']);
    expect(fillPromptVariables(text, { 'Имя_клиента': 'Ирина', 'Текст письма': '[Оригинал]' }))
      .toContain('Формат: письмо по [Оригинал]. [Справка](https://example.org) {{constructor}}');
  });
});

describe('versions and model actions', () => {
  it('offers draft answers without submitting the form and supports a single non-persisted execution', async () => {
    const { app, call, db, calls } = await fixture();
    const draft = await call('POST', '/api/optimizer/run', ADMIN, { workflow: 'clarify', raw_input: 'Идея: запустить рассылку' });
    const url = `/api/optimizer/items/${draft.data.id}`;
    expect((await call('POST', `${url}/suggest`, READER, {})).status).toBe(404);
    expect((await call('POST', `${url}/suggest`, ADMIN, {})).data.answers).toEqual(['Новые клиенты', 'Проверить интерес', 'Две недели']);
    expect((await call('GET', url, ADMIN)).data).toMatchObject({ status: 'draft_questions', answers: [] });
    const result = await call('POST', `${url}/answer`, ADMIN, { answers: ['Мой вариант', 'Проверить интерес', 'Две недели'] });
    expect(result.data).toMatchObject({ status: 'ok', optimized_score: null, final_prompt: BODY });

    const response = await app.inject({ method: 'POST', url: '/api/prompts/execute', headers: { ...ADMIN, accept: 'text/event-stream' }, payload: { prompt: BODY } });
    expect(response.headers['content-type']).toContain('text/event-stream');
    expect(response.payload).toMatch(/^event: working[\s\S]*event: result\ndata: /);
    expect(response.payload).toContain('Готовый ответ');
    expect(calls.at(-1)).toEqual([{ role: 'user', content: BODY }]);
    expect(db.get('SELECT COUNT(*) AS total FROM optimizations')?.total).toBe(1);
    expect((await app.inject({ method: 'POST', url: '/api/prompts/execute', payload: { prompt: BODY } })).statusCode).toBe(401);
    await call('POST', '/api/prompts/execute', ADMIN, { prompt: BODY });
    await call('POST', '/api/prompts/execute', ADMIN, { prompt: BODY });
    expect((await call('POST', '/api/prompts/execute', ADMIN, { prompt: BODY })).status).toBe(429);
  });

  it('tracks revisions, clears stale compression, and restores an old version as a new edit', async () => {
    const { call } = await fixture();
    const created = await call('POST', '/api/optimizer/run', ADMIN, { workflow: 'template', raw_input: 'Подготовь шаблон письма' });
    const url = `/api/optimizer/items/${created.data.id}`;
    expect((await call('POST', `${url}/compress`, ADMIN, {})).data.compressed_prompt).toBeTruthy();
    expect((await call('GET', `${url}/versions`, READER)).status).toBe(404);
    expect((await call('PUT', `${url}/prompt`, ADMIN, { body: CHANGE, expected_version: 1 })).data)
      .toMatchObject({ final_prompt: CHANGE, compressed_prompt: null });
    expect((await call('PUT', `${url}/prompt`, ADMIN, { body: BODY, expected_version: 1 })).status).toBe(409);
    const history = (await call('GET', `${url}/versions`, ADMIN)).data;
    expect(history.items.map((row: { version: number }) => row.version)).toEqual([2, 1]);
    expect((await call('PUT', `${url}/prompt`, ADMIN, { body: history.items[1].body, expected_version: 2 })).data.final_prompt).toBe(BODY);
    expect((await call('GET', `${url}/versions?before=3`, ADMIN)).data.items.map((row: { version: number }) => row.version)).toEqual([2, 1]);
    const template = await call('POST', '/api/templates', ADMIN, { title: 'Коммуникации', body: BODY });
    const templateUrl = `/api/templates/${template.data.id}`;
    expect((await call('PATCH', templateUrl, ADMIN, { body: CHANGE, expected_version: 1 })).status).toBe(200);
    expect((await call('GET', `${templateUrl}/versions`, ADMIN)).data.current_version).toBe(2);
  });

  it('upgrades a database at schema v2 without changing any existing private optimizer data', () => {
    const directory = mkdtempSync(join(tmpdir(), 'promptolog-v2-'));
    cleanups.push(() => rmSync(directory, { recursive: true, force: true }));
    const file = join(directory, 'legacy.db');
    const initial = openDb(file);
    initial.raw.exec('DROP TABLE prompt_versions; DROP TABLE team_prompts; DROP TABLE team_folder_members; DROP TABLE team_folders; PRAGMA user_version=2');
    initial.run('INSERT INTO optimizations (id, user_id, workflow, status, raw_input, final_prompt, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
      'legacy', '20', 'template', 'ok', 'request', BODY, '2026-11-01', '2026-11-01');
    initial.raw.close();
    const migrated = openDb(file);
    cleanups.push(() => migrated.raw.close());
    expect(migrated.raw.prepare('PRAGMA user_version').get()).toMatchObject({ user_version: 3 });
    expect(migrated.get('SELECT id, final_prompt FROM optimizations WHERE id = ?', 'legacy')).toMatchObject({ id: 'legacy', final_prompt: BODY });
    expect(migrated.get('SELECT COUNT(*) AS n FROM prompt_versions')).toMatchObject({ n: 0 });
  });
});

describe('team folders', () => {
  it('scopes discovery, read, write and revision history to the correct portal and role', async () => {
    const { call } = await fixture();
    const input = { name: 'Отдел продаж', visibility: 'restricted', members: [{ user_id: '20', role: 'editor' }, { user_id: '21', role: 'reader' }] };
    expect((await call('POST', '/api/team/folders', EDITOR, input)).status).toBe(403);
    const created = await call('POST', '/api/team/folders', ADMIN, input);
    expect(created.status).toBe(200);
    const folderPath = `/api/team/folders/${created.data.id}`;
    expect((await call('GET', '/api/team/folders', EMPLOYEE)).data.items).toEqual([]);
    expect((await call('GET', '/api/team/folders', session('1', 'ADMIN', OTHER_PORTAL))).data.items).toEqual([]);
    expect((await call('GET', '/api/team/folders', session('share:guest'))).data).toEqual({ items: [], can_manage: false });
    expect((await call('GET', `${folderPath}/settings`, EDITOR)).status).toBe(403);
    expect((await call('GET', `${folderPath}/prompts`, session('21', 'ADMIN', OTHER_PORTAL))).status).toBe(404);
    expect((await call('POST', `${folderPath}/prompts`, READER, { title: 'Тон компании', body: BODY })).status).toBe(403);
    const createdPrompt = await call('POST', `${folderPath}/prompts`, EDITOR, { title: 'Тон компании', body: BODY });
    const itemPath = `${folderPath}/prompts/${createdPrompt.data.id}`;
    expect((await call('GET', itemPath, READER)).data.body).toBe(BODY);
    expect((await call('GET', `${itemPath}/versions`, READER)).status).toBe(403);
    expect((await call('PUT', itemPath, READER, { body: CHANGE, expected_version: 1 })).status).toBe(403);
    expect((await call('PUT', itemPath, EDITOR, { body: CHANGE, expected_version: 1 })).data).toMatchObject({ version: 2, body: CHANGE });
    expect((await call('GET', `${itemPath}/versions`, EDITOR)).data.current_version).toBe(2);
    expect((await call('DELETE', itemPath, READER)).status).toBe(403);
    expect((await call('PUT', `${folderPath}/settings`, ADMIN, { ...input, visibility: 'portal', members: [] })).status).toBe(200);
    expect((await call('GET', itemPath, EMPLOYEE)).status).toBe(200);
    expect((await call('PUT', itemPath, EDITOR, { body: BODY, expected_version: 2 })).status).toBe(403);
  });
});
