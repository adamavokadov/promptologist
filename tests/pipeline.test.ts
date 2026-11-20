import { describe, it, expect, beforeEach } from 'vitest';
import { createHmac } from 'node:crypto';
import { freshDb, fakeVibe } from './helpers.ts';
import { runGeneration, regenerateResult, recordCanary, applyRetention, type GenEvent } from '../apps/server/src/generation.ts';
import { executeRun, createRun, dispatchDue, goldenTests, planQueries, rankEvidence, resumeUnfinished } from '../apps/server/src/refresh.ts';
import { getCurrentVersion } from '../apps/server/src/skills.ts';
import { getSettings } from '../apps/server/src/db.ts';
import { buildApp } from '../apps/server/src/routes.ts';
import { setSettings } from '../apps/server/src/db.ts';
import { resetRateLimits, clearIdentityCache } from '../apps/server/src/auth.ts';
import { DAY_MS } from '../apps/server/src/util.ts';
import { SYSTEM_IDS, type GenOptions } from '../shared/src/index.ts';
import { SEED_TEMPLATES } from '../apps/server/src/seed/templates.ts';

const opts = (o: Partial<GenOptions> = {}): GenOptions => ({ task_type: 'auto', detail: 'standard', assumptions_mode: 'assume', include_format: true, ...o });
const RAW = 'Разобрать договор аренды и найти рисковые пункты';
const noSleep = async () => {};

describe('generation pipeline', () => {
  it('produces valid cards for all 5 systems and persists them', async () => {
    const db = freshDb(); const events: GenEvent[] = [];
    const id = await runGeneration({ db, userId: 'u1', vibe: fakeVibe(), emit: (e) => events.push(e), req: { raw_input: RAW, systems: [...SYSTEM_IDS], language: 'ru', options: opts() } });
    expect(events.filter((e) => e.type === 'card_done')).toHaveLength(5);
    expect(events.at(-1)).toMatchObject({ type: 'done', status: 'ok' });
    const g = db.get('SELECT * FROM generations WHERE id = ?', id)!; expect(g.status).toBe('ok');
    expect(db.all('SELECT * FROM generation_results WHERE generation_id = ?', id)).toHaveLength(5);
  });
  it('a failing system does not break the others (partial)', async () => {
    const db = freshDb(); const events: GenEvent[] = [];
    await runGeneration({ db, userId: 'u1', vibe: fakeVibe({ failSystems: ['Kimi'] }), emit: (e) => events.push(e), req: { raw_input: RAW, systems: ['claude', 'kimi', 'grok'], language: 'ru', options: opts() } });
    expect(events.filter((e) => e.type === 'card_error')).toHaveLength(1);
    expect(events.at(-1)).toMatchObject({ status: 'partial' });
  });
  it('English output passes the language checks', async () => {
    const db = freshDb(); const events: GenEvent[] = [];
    await runGeneration({ db, userId: 'u1', vibe: fakeVibe({ language: 'en' }), emit: (e) => events.push(e), req: { raw_input: 'Review a lease and find risks', systems: ['claude'], language: 'en', options: opts() } });
    expect(events.at(-1)).toMatchObject({ status: 'ok' });
  });
  it('a wrong-language answer fails after one repair attempt', async () => {
    const db = freshDb(); const events: GenEvent[] = []; const calls = { chat: 0, search: 0, research: 0, notify: 0 };
    await runGeneration({ db, userId: 'u1', vibe: fakeVibe({ language: 'en', calls }), emit: (e) => events.push(e), req: { raw_input: RAW, systems: ['claude'], language: 'ru', options: opts() } });
    expect(events.at(-1)).toMatchObject({ status: 'failed' });
    expect(calls.chat).toBe(1 + 2); // intent + transform + one repair
  });
  it('questions mode stops with draft_questions and continues after answers', async () => {
    const db = freshDb(); const events: GenEvent[] = [];
    const vibe = fakeVibe({ intent: { missing_info: ['Какая юрисдикция?', 'Какая сторона?'] } });
    const id = await runGeneration({ db, userId: 'u1', vibe, emit: (e) => events.push(e), req: { raw_input: RAW, systems: ['claude'], language: 'ru', options: opts({ assumptions_mode: 'questions' }) } });
    expect(events.find((e) => e.type === 'questions')).toBeTruthy();
    expect(db.get('SELECT status FROM generations WHERE id = ?', id)!.status).toBe('draft_questions');
    const ev2: GenEvent[] = [];
    await runGeneration({ db, userId: 'u1', vibe, emit: (e) => ev2.push(e), extraAnswers: 'Ответ: РФ', req: { raw_input: RAW, systems: ['claude'], language: 'ru', options: opts({ assumptions_mode: 'questions' }), generation_id: id } });
    expect(ev2.at(-1)).toMatchObject({ status: 'ok' });
  });
  it('regeneration stores a new variant linked to the original', async () => {
    const db = freshDb(); const vibe = fakeVibe();
    const id = await runGeneration({ db, userId: 'u1', vibe, emit: () => {}, req: { raw_input: RAW, systems: ['claude'], language: 'ru', options: opts() } });
    const first = db.get('SELECT id FROM generation_results WHERE generation_id = ?', id)!;
    const r = await regenerateResult({ db, userId: 'u1', generationId: id, resultId: first.id, feedback: 'короче', vibe });
    expect(r.variant_of).toBe(first.id); expect(db.all('SELECT id FROM generation_results WHERE generation_id = ?', id)).toHaveLength(2);
  });
  it('a quota error pauses the agent via callback and yields a clear card error', async () => {
    const db = freshDb(); const events: GenEvent[] = []; let paused = '';
    await runGeneration({ db, userId: 'u1', vibe: fakeVibe({ quota: true }), onQuota: (r) => { paused = r; }, emit: (e) => events.push(e), req: { raw_input: RAW, systems: ['claude'], language: 'ru', options: opts() } });
    expect(paused).toMatch(/quota/); expect(events.find((e) => e.type === 'card_error')).toMatchObject({ error: 'Квота ИИ исчерпана' });
  });
  it('retention never deletes generations that contain favourites', async () => {
    const db = freshDb(); const vibe = fakeVibe(); const ids: string[] = [];
    for (let i = 0; i < 4; i++) { ids.push(await runGeneration({ db, userId: 'u1', vibe, emit: () => {}, req: { raw_input: `${RAW} ${i}`, systems: ['claude'], language: 'ru', options: opts() } })); await new Promise((r) => setTimeout(r, 3)); }
    db.run("UPDATE generation_results SET is_favorite = 1 WHERE generation_id = ?", ids[0]!);
    const removed = applyRetention(db, 'u1', 1);
    expect(removed).toBe(2);
    expect(db.get('SELECT id FROM generations WHERE id = ?', ids[0]!)).toBeTruthy();
  });
});

describe('canary and auto-rollback', () => {
  it('two hard failures roll the skill back to the previous version', () => {
    const db = freshDb(); const v1 = getCurrentVersion(db, 'claude');
    const v2id = 'v2-id';
    db.run("INSERT INTO skill_versions(id, skill_id, version, frontmatter, body_md, origin, created_at) VALUES(?,?,?,?,?,?,?)", v2id, 'claude', 2, '{}', v1.body_md, 'agent', new Date().toISOString());
    db.run("UPDATE skills SET current_version_id = ?, canary_remaining = 3 WHERE id = 'claude'", v2id);
    expect(recordCanary(db, 'claude', v2id, true).rolledBack).toBe(false);
    expect(recordCanary(db, 'claude', v2id, true).rolledBack).toBe(true);
    expect(getCurrentVersion(db, 'claude').id).toBe(v1.id);
    expect(db.get("SELECT status FROM skills WHERE id = 'claude'")!.status).toBe('failed');
    expect(db.get("SELECT verdict FROM reports WHERE skill_id = 'claude'")!.verdict).toBe('rolled_back');
  });
  it('successful canary generations never trigger a rollback', () => {
    const db = freshDb(); const v = getCurrentVersion(db, 'kimi');
    db.run("UPDATE skills SET canary_remaining = 3 WHERE id = 'kimi'");
    for (let i = 0; i < 3; i++) expect(recordCanary(db, 'kimi', v.id, false).rolledBack).toBe(false);
    expect(db.get("SELECT canary_remaining AS c FROM skills WHERE id = 'kimi'")!.c).toBe(0);
  });
});

function updatedAnalysis(db: ReturnType<typeof freshDb>) {
  const body = getCurrentVersion(db, 'claude').body_md.replace('## Usage Notes\n', '## Usage Notes\nPrefer adaptive thinking for hard tasks. NEWSKILL\n');
  return { changes_detected: true, significance: 'minor', model_lineup: ['Claude Opus 5.5'], proposed_frontmatter: {}, proposed_body_md: body,
    changelog: [{ change: 'Added adaptive thinking note', reason: 'guide update', source_url: 'https://platform.claude.com/docs/en/new-model-guide' }], confidence: 0.8 };
}
const deps = (db: any, vibe: any) => ({ db, vibe, sleepImpl: noSleep, searchPause: () => 0 });

describe('refresh agent', () => {
  let db: ReturnType<typeof freshDb>;
  beforeEach(() => { db = freshDb(); });

  it('no changes: report written, rescheduled 10-15 days ahead, no new version', async () => {
    const runId = createRun(db, 'claude', 'manual');
    expect(await executeRun(deps(db, fakeVibe()), runId)).toBe('no_changes');
    const s = db.get("SELECT * FROM skills WHERE id = 'claude'")!;
    const d = Date.parse(s.next_check_at) - Date.now(); expect(d).toBeGreaterThan(9.9 * DAY_MS); expect(d).toBeLessThan(15.2 * DAY_MS);
    expect(db.get("SELECT status FROM refresh_runs WHERE id = ?", runId)!.status).toBe('no_changes');
    expect(db.all("SELECT * FROM skill_versions WHERE skill_id = 'claude'")).toHaveLength(1);
    expect(db.all("SELECT * FROM reports WHERE skill_id = 'claude'")).toHaveLength(1);
  });
  it('applies a validated draft that passes golden tests and activates the canary', async () => {
    const calls = { chat: 0, search: 0, research: 0, notify: 0 };
    const vibe = fakeVibe({ analyzer: updatedAnalysis(db), judgeWinner: 'tie', calls });
    const runId = createRun(db, 'claude', 'manual');
    expect(await executeRun(deps(db, vibe), runId)).toBe('updated');
    const s = db.get("SELECT * FROM skills WHERE id = 'claude'")!;
    expect(getCurrentVersion(db, 'claude').version).toBe(2); expect(getCurrentVersion(db, 'claude').origin).toBe('agent');
    expect(s.canary_remaining).toBe(3); expect(calls.chat).toBeLessThanOrEqual(12); expect(calls.search).toBeLessThanOrEqual(6); expect(calls.research).toBeLessThanOrEqual(1);
    expect(getCurrentVersion(db, 'claude').frontmatter.protected_invariants).toHaveLength(4);
    expect(calls.notify).toBe(1);
  });
  it('golden loss rejects the draft without applying it', async () => {
    const runId = createRun(db, 'claude', 'manual');
    const vibe = fakeVibe({ analyzer: updatedAnalysis(db), judgeWinner: 'old' });
    expect(await executeRun(deps(db, vibe), runId)).toBe('rejected');
    expect(getCurrentVersion(db, 'claude').version).toBe(1);
    expect(db.get("SELECT verdict FROM reports WHERE run_id = ?", runId)!.verdict).toBe('rejected');
  });
  it('drops non-whitelisted sources and rejects when nothing is confirmed', async () => {
    const a = updatedAnalysis(db); a.changelog = [{ change: 'x', reason: 'y', source_url: 'https://evil.example.com/p' }];
    const runId = createRun(db, 'claude', 'manual');
    expect(await executeRun(deps(db, fakeVibe({ analyzer: a })), runId)).toBe('rejected');
  });
  it('rejects drafts that weaken protected invariants', async () => {
    const a = updatedAnalysis(db); a.proposed_body_md = a.proposed_body_md.replace('Never invent domain facts: assumptions must be explicit.', 'Be creative.');
    const runId = createRun(db, 'claude', 'manual');
    expect(await executeRun(deps(db, fakeVibe({ analyzer: a })), runId)).toBe('rejected');
  });
  it('degrades gracefully when search is unavailable', async () => {
    const runId = createRun(db, 'claude', 'manual');
    expect(await executeRun(deps(db, fakeVibe({ searchFails: true })), runId)).toBe('no_changes');
  });
  it('stops with budget_error when the LLM call budget is exceeded', async () => {
    const vibe = fakeVibe({ analyzer: updatedAnalysis(db), judgeWinner: 'tie' });
    const runId = createRun(db, 'claude', 'manual');
    db.run("UPDATE refresh_runs SET budget_used = ? WHERE id = ?", JSON.stringify({ search: 0, research: 0, llm: 11, tokens: 0 }), runId);
    expect(await executeRun(deps(db, vibe), runId)).toBe('budget_error');
    expect(getCurrentVersion(db, 'claude').version).toBe(1);
    expect(db.get("SELECT consecutive_failures AS c FROM skills WHERE id = 'claude'")!.c).toBe(1);
  });
  it('failure reschedules within 24-48h and a quota error pauses the agent', async () => {
    const runId = createRun(db, 'claude', 'manual');
    expect(await executeRun(deps(db, fakeVibe({ quota: true })), runId)).toBe('failed');
    const d = Date.parse(db.get("SELECT next_check_at FROM skills WHERE id = 'claude'")!.next_check_at) - Date.now();
    expect(d).toBeGreaterThan(23.9 * 3_600_000); expect(d).toBeLessThan(48.1 * 3_600_000);
    expect(getSettings(db).agent_paused_reason).toMatch(/quota/);
  });
  it('resumes an interrupted run from its checkpoint without repeating earlier steps', async () => {
    const calls = { chat: 0, search: 0, research: 0, notify: 0 };
    const runId = createRun(db, 'claude', 'manual');
    db.run("UPDATE refresh_runs SET status = 'running', step = 'analyze', payload = ? WHERE id = ?", JSON.stringify({ queries: ['q'], evidence: [] }), runId);
    const done = await resumeUnfinished(deps(db, fakeVibe({ calls })));
    expect(done).toEqual([runId]); expect(calls.search).toBe(0);
  });
  it('dispatcher runs at most one due skill per delivery and respects the master switch', async () => {
    db.run("UPDATE skills SET next_check_at = '2000-01-01T00:00:00.000Z'");
    const ran = await dispatchDue(deps(db, fakeVibe()), { trigger: 'schedule', jobRunId: 'r1' });
    expect(ran).toHaveLength(1);
    db.run("UPDATE skills SET next_check_at = '2000-01-01T00:00:00.000Z' WHERE status != 'running'");
    setSettings(db, { auto_refresh_enabled: false });
    expect(await dispatchDue(deps(db, fakeVibe()), { trigger: 'schedule' })).toHaveLength(0);
  });
  it('planQueries and rankEvidence', () => {
    const q = planQueries('grok', new Date('2026-11-13T00:00:00Z'), ['reasoning effort xhigh']);
    expect(q.length).toBeGreaterThanOrEqual(4); expect(q.length).toBeLessThanOrEqual(6); expect(q[1]).toContain('November 2026');
    const ev = rankEvidence([
      { url: 'https://x.ai/news/a', title: 'launch', content: '', publishedDate: '2026-11-10' },
      { url: 'https://docs.x.ai/guide', title: 'guide', content: '', publishedDate: '2026-11-01' },
      { url: 'https://docs.x.ai/guide', title: 'dup', content: '' },
      { url: 'https://docs.x.ai/old', title: 'old', content: '', publishedDate: '2020-01-01' },
      { url: 'https://other.com/z', title: 'foreign', content: '' }], ['docs.x.ai', 'x.ai'], Date.parse('2026-10-01'));
    expect(ev.map((e) => e.url)).toEqual(['https://docs.x.ai/guide', 'https://x.ai/news/a']);
  });
  it('golden tests: new must never lose', async () => {
    const cur = getCurrentVersion(db, 'claude');
    const win = await goldenTests(fakeVibe({ judgeWinner: 'new' }), 'm', 'j', 'claude', cur, cur.body_md + 'NEWSKILL', (a) => a);
    expect(win.every((g) => g.winner === 'new')).toBe(true);
    const lose = await goldenTests(fakeVibe({ judgeWinner: 'old' }), 'm', 'j', 'claude', cur, cur.body_md + 'NEWSKILL', (a, b) => b);
    expect(lose.every((g) => g.winner === 'old')).toBe(true);
  });
});

describe('HTTP API', () => {
  const U = { 'x-vibe-user-id': '42', 'x-vibe-user-role': 'ADMIN', 'x-vibe-authorization': 'Bearer vibe_session_test' };
  const M = { 'x-vibe-user-id': '43', 'x-vibe-user-role': 'MEMBER' };
  async function mk(vibeOpts = {}) { resetRateLimits(); clearIdentityCache(); const db = freshDb(); const vibe = fakeVibe(vibeOpts); const app = await buildApp({ db, vibe, refreshDeps: { db, vibe, sleepImpl: noSleep, searchPause: () => 0 } }); return { db, app }; }

  it('healthz is open; /api requires Gateway headers', async () => {
    const { app } = await mk();
    expect((await app.inject('/healthz')).statusCode).toBe(200);
    const r = await app.inject('/api/skills'); expect(r.statusCode).toBe(401);
    expect(JSON.parse(r.body).error.code).toBe('authorization_required');
    expect((await app.inject({ url: '/api/skills', headers: U })).statusCode).toBe(200);
  });
  it('lists 5 skills and every seed template', async () => {
    const { app } = await mk();
    expect(JSON.parse((await app.inject({ url: '/api/skills', headers: U })).body).items).toHaveLength(5);
    const t = JSON.parse((await app.inject({ url: '/api/templates', headers: U })).body).items; expect(t).toHaveLength(SEED_TEMPLATES.length); expect(t.every((x: any) => x.is_seed)).toBe(true);
  });
  it('generate streams SSE events and the result lands in history, favourites and search', async () => {
    const { app } = await mk();
    const res = await app.inject({ method: 'POST', url: '/api/generate', headers: U, payload: { raw_input: RAW, systems: ['claude', 'grok'], language: 'ru' } });
    expect(res.headers['content-type']).toContain('text/event-stream');
    expect(res.body).toContain('event: card_done'); expect(res.body).toContain('event: done');
    const list = JSON.parse((await app.inject({ url: '/api/generations', headers: U })).body); expect(list.total).toBe(1);
    const gid = list.items[0].id;
    const g = JSON.parse((await app.inject({ url: `/api/generations/${gid}`, headers: U })).body);
    expect(g.results).toHaveLength(2);
    await app.inject({ method: 'PATCH', url: `/api/results/${g.results[0].id}/favorite`, headers: U, payload: { value: true } });
    expect(JSON.parse((await app.inject({ url: '/api/favorites', headers: U })).body).items).toHaveLength(1);
    expect(JSON.parse((await app.inject({ url: '/api/generations?q=договор', headers: U })).body).total).toBe(1);
    expect(JSON.parse((await app.inject({ url: '/api/generations?favorites=1', headers: U })).body).total).toBe(1);
    // data is scoped per user
    expect(JSON.parse((await app.inject({ url: '/api/generations', headers: M })).body).total).toBe(0);
    expect((await app.inject({ url: `/api/generations/${gid}`, headers: M })).statusCode).toBe(404);
    await app.inject({ method: 'DELETE', url: `/api/generations/${gid}`, headers: U });
    expect(JSON.parse((await app.inject({ url: '/api/generations', headers: U })).body).total).toBe(0);
  });
  it('rate-limits generation to 6 per minute per user', async () => {
    const { app } = await mk(); let last = 0;
    for (let i = 0; i < 7; i++) last = (await app.inject({ method: 'POST', url: '/api/generate', headers: U, payload: { raw_input: RAW, systems: ['claude'], language: 'ru' } })).statusCode;
    expect(last).toBe(429);
  });
  it('validates input with zod errors', async () => {
    const { app } = await mk();
    const r = await app.inject({ method: 'POST', url: '/api/generate', headers: U, payload: { raw_input: 'x' } });
    expect(r.statusCode).toBe(400);
  });
  it('template lifecycle: create, use with variables, duplicate seed, protect seed, delete', async () => {
    const { app } = await mk();
    const c = JSON.parse((await app.inject({ method: 'POST', url: '/api/templates', headers: U, payload: { title: 'T', body: 'Hello {{name}} from {{city}}' } })).body);
    expect(c.variables).toEqual(['name', 'city']);
    const used = JSON.parse((await app.inject({ method: 'POST', url: `/api/templates/${c.id}/use`, headers: U, payload: { values: { name: 'Ann', city: 'Rio' } } })).body);
    expect(used.text).toBe('Hello Ann from Rio'); expect(used.missing).toEqual([]);
    expect(JSON.parse((await app.inject({ url: `/api/templates/${c.id}`, headers: U })).body).usage_count).toBe(1);
    const seed = JSON.parse((await app.inject({ url: '/api/templates', headers: U })).body).items[0];
    expect((await app.inject({ method: 'DELETE', url: `/api/templates/${seed.id}`, headers: U })).statusCode).toBe(403);
    expect((await app.inject({ method: 'PATCH', url: `/api/templates/${seed.id}`, headers: U, payload: { title: 'x' } })).statusCode).toBe(403);
    expect((await app.inject({ method: 'POST', url: `/api/templates/${seed.id}/duplicate`, headers: U })).statusCode).toBe(200);
    expect((await app.inject({ method: 'DELETE', url: `/api/templates/${c.id}`, headers: U })).statusCode).toBe(200);
    expect((await app.inject({ method: 'POST', url: '/api/templates', headers: U, payload: { title: 'Big', body: Array.from({ length: 13 }, (_, i) => `{{v${i}}}`).join(' ') } })).statusCode).toBe(400);
  });
  it('admin-only mutations: settings, rollback, refresh, pause', async () => {
    const { app } = await mk();
    expect((await app.inject({ method: 'PUT', url: '/api/settings', headers: M, payload: { theme: 'light' } })).statusCode).toBe(403);
    expect((await app.inject({ method: 'PUT', url: '/api/settings', headers: U, payload: { theme: 'light' } })).statusCode).toBe(200);
    expect((await app.inject({ method: 'PATCH', url: '/api/skills/claude', headers: M, payload: { paused: true } })).statusCode).toBe(403);
    const p = JSON.parse((await app.inject({ method: 'PATCH', url: '/api/skills/claude', headers: U, payload: { paused: true } })).body); expect(p.status).toBe('paused');
    expect((await app.inject({ method: 'POST', url: '/api/skills/claude/refresh', headers: M })).statusCode).toBe(403);
  });
  it('skill versions, diff and rollback produce a report', async () => {
    const { app, db } = await mk();
    const v1 = getCurrentVersion(db, 'claude');
    db.run("INSERT INTO skill_versions(id, skill_id, version, frontmatter, body_md, origin, created_at) VALUES('vv2','claude',2,'{}',?,'agent',?)", v1.body_md + '\nExtra line', new Date().toISOString());
    db.run("UPDATE skills SET current_version_id = 'vv2' WHERE id = 'claude'");
    const diff = JSON.parse((await app.inject({ url: '/api/skills/claude/versions/1/diff/2', headers: U })).body);
    expect(diff.parts.some((p: any) => p.added && p.value.includes('Extra line'))).toBe(true);
    const rb = await app.inject({ method: 'POST', url: '/api/skills/claude/rollback', headers: U, payload: { version_id: v1.id } });
    expect(rb.statusCode).toBe(200);
    expect(JSON.parse((await app.inject({ url: '/api/reports', headers: U })).body).items[0].verdict).toBe('rolled_back');
    expect(JSON.parse((await app.inject({ url: '/api/skills/claude/versions', headers: U })).body).items).toHaveLength(2);
  });
  it('manual refresh starts a run in the background and then enforces the cooldown', async () => {
    const { app, db } = await mk();
    const r = await app.inject({ method: 'POST', url: '/api/skills/claude/refresh', headers: U }); expect(r.statusCode).toBe(202);
    for (let i = 0; i < 100; i++) { await new Promise((x) => setTimeout(x, 50)); if (db.get("SELECT 1 AS x FROM reports WHERE skill_id = 'claude'")) break; }
    expect(db.get("SELECT verdict FROM reports WHERE skill_id = 'claude'")?.verdict).toBeTruthy();
    expect((await app.inject({ method: 'POST', url: '/api/skills/claude/refresh', headers: U })).statusCode).toBe(409);
  });
  it('job endpoint: rejects bad signatures, accepts valid ones once (dedupe) and returns 200 fast', async () => {
    const secret = 'vjs_' + 'B'.repeat(43); process.env.JOB_SECRET = secret;
    const { config } = await import('../apps/server/src/config.ts'); config.jobSecret = secret;
    const { app, db } = await mk(); db.run("UPDATE skills SET paused = 1");
    const body = JSON.stringify({ type: 'scheduled_job.run', jobId: 'j1', runId: 'run-1', scheduledFor: '2026-11-13T04:17:00.000Z', attempt: 1, late: false, trigger: 'schedule' });
    const t = Math.floor(Date.now() / 1000);
    const sig = `t=${t},v1=${createHmac('sha256', secret).update(`${t}.${body}`).digest('hex')}`;
    const h = { 'content-type': 'application/json', 'x-vibe-caller-kind': 'schedule', 'vibe-signature': sig };
    expect((await app.inject({ method: 'POST', url: '/internal/jobs/dispatcher', headers: { ...h, 'vibe-signature': sig.replace(/.$/, '0') }, payload: body })).statusCode).toBe(401);
    expect((await app.inject({ method: 'POST', url: '/internal/jobs/dispatcher', headers: { ...h, 'x-vibe-caller-kind': 'user' }, payload: body })).statusCode).toBe(401);
    expect((await app.inject({ method: 'POST', url: '/internal/jobs/dispatcher', headers: h, payload: body })).statusCode).toBe(200);
    expect((await app.inject({ method: 'POST', url: '/internal/jobs/dispatcher', headers: h, payload: body })).statusCode).toBe(200);
    expect(db.all('SELECT * FROM job_dedupe')).toHaveLength(1);
    config.jobSecret = '';
  });
  it('export and template import roundtrip; clear history keeps favourites', async () => {
    const { app } = await mk();
    await app.inject({ method: 'POST', url: '/api/generate', headers: U, payload: { raw_input: RAW, systems: ['claude'], language: 'ru' } });
    const ex = JSON.parse((await app.inject({ method: 'POST', url: '/api/export', headers: U })).body); expect(ex.generations).toHaveLength(1);
    const imp = JSON.parse((await app.inject({ method: 'POST', url: '/api/import/templates', headers: U, payload: { templates: [{ title: 'A', body: 'x {{y}}' }, { nope: 1 }] } })).body);
    expect(imp.imported).toBe(1); expect(imp.errors).toHaveLength(1);
    const gid = JSON.parse((await app.inject({ url: '/api/generations', headers: U })).body).items[0].id;
    const rid = JSON.parse((await app.inject({ url: `/api/generations/${gid}`, headers: U })).body).results[0].id;
    await app.inject({ method: 'PATCH', url: `/api/results/${rid}/favorite`, headers: U, payload: { value: true } });
    expect(JSON.parse((await app.inject({ method: 'POST', url: '/api/history/clear', headers: U })).body).removed).toBe(0);
  });
  it('agent status and models proxy', async () => {
    const { app } = await mk();
    expect(JSON.parse((await app.inject({ url: '/api/agent/status', headers: U })).body).scheduler_mode).toBeTruthy();
    expect(JSON.parse((await app.inject({ url: '/api/models', headers: U })).body).items[0].free).toBe(true);
  });
});
