#!/usr/bin/env node
// Post-deploy smoke checks. Run it ON the server (exec) or against a locally reachable instance:
//   node scripts/smoke.mjs --base http://127.0.0.1:3000 [--generate] [--jobs]
// Identity: the Gateway headers are trusted by the app, so the script sends X-Vibe-User-* itself (works only for direct/local calls).
// --generate performs one real, free AI call. --jobs checks the scheduler job through the platform API (needs VIBE_API_KEY and VIBE_SERVER_ID).
const argVal = (n, d) => { const i = process.argv.indexOf(n); return i > -1 ? process.argv[i + 1] : d; };
const has = (n) => process.argv.includes(n);
const BASE = (argVal('--base', process.env.SMOKE_BASE ?? 'http://127.0.0.1:' + (process.env.PORT ?? 3000))).replace(/\/+$/, '');
const H = { 'x-vibe-user-id': '1', 'x-vibe-user-role': 'ADMIN', 'x-vibe-user-name-encoded': 'Smoke' };
const results = []; let failed = 0;
const check = async (name, fn) => { try { const d = await fn(); results.push(`PASS  ${name}${d ? ` — ${d}` : ''}`); } catch (e) { failed++; results.push(`FAIL  ${name} — ${e.message}`); } };
const j = async (p, init = {}) => { const r = await fetch(BASE + p, { ...init, headers: { ...H, 'Content-Type': 'application/json', ...(init.headers ?? {}) } }); const t = await r.text(); let b; try { b = JSON.parse(t); } catch { b = t; } if (!r.ok) throw new Error(`${p} -> ${r.status} ${t.slice(0, 120)}`); return b; };

await check('healthz returns 200', async () => { const b = await j('/healthz'); if (!b.ok) throw new Error('not ok'); });
await check('static SPA is served', async () => { const r = await fetch(BASE + '/'); const t = await r.text(); if (!r.ok || !t.includes('<div id="root">')) throw new Error(`status ${r.status}`); });
await check('/api/skills returns 5 skills', async () => { for (let i = 0; i < 20; i++) { try { const b = await j('/api/skills'); if (b.items.length !== 5) throw new Error(`got ${b.items.length}`); return b.items.map((s) => `${s.id}@v${s.current_version}`).join(' '); } catch (e) { if (i === 19) throw e; await new Promise((r) => setTimeout(r, 1500)); } } });
const EXPECTED_SEED_TEMPLATES = 9; // keep in sync with SEED_TEMPLATES.length
await check(`${EXPECTED_SEED_TEMPLATES} seed templates present`, async () => { const b = await j('/api/templates'); const n = b.items.filter((t) => t.is_seed).length; if (n !== EXPECTED_SEED_TEMPLATES) throw new Error(`got ${n}`); });
await check('agent status readable', async () => { const b = await j('/api/agent/status'); return `scheduler=${b.scheduler_mode} secret=${b.job_secret_configured ? 'set' : 'missing'}`; });
if (has('--generate')) await check('real generation on one system', async () => {
  const r = await fetch(BASE + '/api/generate', { method: 'POST', headers: { ...H, 'Content-Type': 'application/json' }, body: JSON.stringify({ raw_input: 'План запуска подкаста на 8 недель', systems: ['claude'], language: 'ru' }) });
  const t = await r.text(); if (!t.includes('event: card_done')) throw new Error(`no card_done; tail: ${t.slice(-200)}`); return 'card_done received';
});
if (has('--jobs')) await check('scheduler job is registered', async () => {
  const key = process.env.VIBE_API_KEY, sid = process.env.VIBE_SERVER_ID; if (!key || !sid) throw new Error('VIBE_API_KEY / VIBE_SERVER_ID not set');
  const r = await fetch(`${process.env.VIBE_BASE_URL ?? 'https://vibecode.bitrix24.com/v1'}/infra/servers/${sid}/jobs`, { headers: { 'X-Api-Key': key } }); const b = await r.json();
  const job = (b?.data?.items ?? []).find((x) => x.label === 'promptolog-dispatcher'); if (!job) throw new Error('job promptolog-dispatcher not found (lazy fallback mode?)'); return `${job.cronExpr} ${job.timezone} enabled=${job.enabled}`;
});
console.log(results.join('\n')); console.log(failed ? `\n${failed} check(s) failed` : '\nall checks passed'); process.exit(failed ? 1 : 0);
