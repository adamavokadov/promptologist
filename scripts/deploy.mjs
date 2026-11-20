#!/usr/bin/env node
// Builds a source archive and deploys it to Alaio Vibecode through the Deploy API (JSON mode, never ?stream=true).
// Usage: VIBE_API_KEY=... VIBE_SERVER_ID=... node scripts/deploy.mjs [--source-url <https url>] [--skip-build] [--bind-placement] [--dry-run]
// Secrets are read from the environment only. Nothing here is ever printed unmasked.
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const args = new Set(process.argv.slice(2));
const argVal = (name) => { const i = process.argv.indexOf(name); return i > -1 ? process.argv[i + 1] : undefined; };
const BASE = (process.env.VIBE_BASE_URL ?? 'https://vibecode.bitrix24.com/v1').replace(/\/+$/, '');
const KEY = process.env.VIBE_API_KEY ?? '';
const SERVER_ID = process.env.VIBE_SERVER_ID ?? '';
const APP_KEY = process.env.VIBE_APP_KEY ?? '';
const RUNTIME_PREF = process.env.DEPLOY_RUNTIME ?? 'node24';
const DISPLAY_NAME = 'Промптолог';
const DESCRIPTION = 'Генератор промптов для Claude, ChatGPT, Kimi, Qwen и Grok с самообновляемыми скиллами.';
const mask = (s) => String(s).replace(/vibe_(api|app|session)_[A-Za-z0-9_-]+/g, 'vibe_$1_***').replace(/vjs_[A-Za-z0-9_-]+/g, 'vjs_***');
const log = (...a) => console.log('[deploy]', ...a.map(mask));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const root = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');

if (!KEY || !SERVER_ID || KEY.startsWith('REPLACE') || SERVER_ID.startsWith('REPLACE')) {
  console.error('VIBE_API_KEY and VIBE_SERVER_ID must be set (see .env.example).'); process.exit(2);
}

/** JSON request with retries per docs: Retry-After for 429/503, EXEC_BUSY / WAKE_TIMEOUT / GALAXY_UPLOAD_BUSY are retried, never re-creating the server. */
async function api(method, p, { body, key = KEY, headers = {}, retries = 6 } = {}) {
  for (let attempt = 0; ; attempt++) {
    let res; let json = null;
    try {
      res = await fetch(`${BASE}${p}`, { method, headers: { 'Content-Type': 'application/json', 'X-Api-Key': key, ...headers }, body: body ? JSON.stringify(body) : undefined });
      const text = await res.text(); try { json = text ? JSON.parse(text) : null; } catch { json = { raw: text.slice(0, 300) }; }
    } catch (e) { if (attempt >= retries) throw e; await sleep(2000 * (attempt + 1)); continue; }
    const code = json?.error?.code ?? '';
    const retryable = res.status === 429 || res.status === 503 || res.status === 502 || ['EXEC_BUSY', 'WAKE_TIMEOUT', 'GALAXY_UPLOAD_BUSY'].includes(code);
    if (!res.ok && retryable && attempt < retries) {
      const ra = Number(res.headers.get('retry-after')); const wait = (Number.isFinite(ra) && ra > 0 ? ra : 5 * (attempt + 1)) * 1000;
      log(`HTTP ${res.status} ${code} — retrying in ${Math.round(wait / 1000)}s`); await sleep(wait); continue;
    }
    if (!res.ok || json?.success === false) { const err = new Error(`${method} ${p} -> ${res.status} ${code} ${json?.error?.message ?? ''}`); err.status = res.status; err.code = code; throw err; }
    return json;
  }
}

function run(cmd, a, opts = {}) { return execFileSync(cmd, a, { stdio: 'inherit', cwd: root, ...opts }); }

async function pickRuntime() {
  try {
    const r = await api('GET', '/infra/runtimes');
    const list = (r?.data?.items ?? r?.data ?? r?.items ?? []).map((x) => (typeof x === 'string' ? x : x.id ?? x.name)).filter(Boolean);
    if (list.includes(RUNTIME_PREF)) return RUNTIME_PREF;
    const nodes = list.filter((x) => /^node\d+/.test(x)).sort((a, b) => parseInt(b.slice(4)) - parseInt(a.slice(4)));
    if (nodes[0]) { log(`runtime ${RUNTIME_PREF} not available; using ${nodes[0]}`); return nodes[0]; }
  } catch (e) { log('could not read /infra/runtimes, falling back to', RUNTIME_PREF, '-', e.message); }
  return RUNTIME_PREF;
}

async function main() {
  if (!args.has('--skip-build')) { log('installing and building'); run('npm', ['ci']); run('npm', ['run', 'build']); }
  if (!fs.existsSync(path.join(root, 'dist/server.js'))) throw new Error('dist/server.js is missing; run npm run build');

  // The runtime environment. APP_PUBLIC_URL, JOB_SECRET and VIBE_APP_KEY are placeholders until you provide the real values.
  const env = {
    NODE_ENV: 'production', VIBE_API_KEY: KEY, VIBE_BASE_URL: BASE, VIBE_SERVER_ID: SERVER_ID, VIBE_APP_KEY: APP_KEY || 'REPLACE_WITH_vibe_app_KEY',
    APP_PUBLIC_URL: process.env.APP_PUBLIC_URL ?? 'REPLACE_WITH_APP_URL', ...(process.env.JOB_SECRET ? { JOB_SECRET: process.env.JOB_SECRET } : {}),
  };
  const runtime = await pickRuntime();
  const body = { runtime, install: 'cd /opt/app && npm ci --omit=dev', start: 'cd /opt/app && node dist/server.js', port: 3000, env, displayName: DISPLAY_NAME, description: DESCRIPTION };

  const srcUrl = argVal('--source-url');
  let archivePath = null;
  if (srcUrl) body.source = { url: srcUrl };
  else {
    // Archive: sources + lockfile + prebuilt dist; no node_modules, .env, .git, databases or logs.
    archivePath = path.join(os.tmpdir(), `promptolog-deploy-${Date.now()}.tar.gz`);
    run('tar', ['-czf', archivePath, '--exclude=node_modules', '--exclude=.git', '--exclude=.env', '--exclude=.env.*', '--exclude=deliverables', '--exclude=*.db', '--exclude=*.db-*', '--exclude=*.log', '--exclude=data', '.']);
    const size = fs.statSync(archivePath).size; log(`archive ${(size / 1024 / 1024).toFixed(2)} MB`);
    // UNVERIFIED CONTRACT: the exact way to hand an archive to POST /infra/servers/:id/deploy must be confirmed against
    // https://vibecode.bitrix24.com/docs/infra/deploy. The documented form for URLs is {"source":{"url":...}}; for uploads this
    // script sends base64 under source.archive. Adjust here if the docs differ, or use --source-url with a hosted tarball.
    body.source = { archive: fs.readFileSync(archivePath).toString('base64'), format: 'tar.gz' };
  }
  if (args.has('--dry-run')) { log('dry run; would deploy with', JSON.stringify({ ...body, env: Object.keys(env), source: srcUrl ? body.source : '<archive>' })); return; }

  log(`deploying to server ${SERVER_ID} (runtime ${runtime})`);
  const res = await api('POST', `/infra/servers/${encodeURIComponent(SERVER_ID)}/deploy?stream=false`, { body, headers: srcUrl ? { 'X-Skip-Source-Snapshot': 'deploy from external URL' } : {} });
  const appUrl = res?.data?.appUrl ?? res?.appUrl;
  log('deploy accepted. appUrl =', appUrl ?? '(not returned)'); for (const w of res?.data?.warnings ?? []) log('warning:', typeof w === 'string' ? w : JSON.stringify(w));
  if (archivePath) fs.rmSync(archivePath, { force: true });

  if (args.has('--bind-placement')) {
    if (!APP_KEY) { log('--bind-placement needs VIBE_APP_KEY (vibe_app_...); skipping'); return; }
    // UNVERIFIED CONTRACT: body shape of POST /v1/placements/bind — confirm at /docs/apps/placements/bind.
    const b = await api('POST', '/placements/bind', { key: APP_KEY, body: { placement: 'LEFT_MENU', title: DISPLAY_NAME } });
    log('placement bound:', JSON.stringify(b?.data ?? b).slice(0, 200));
  }
  log('next: set the real APP_PUBLIC_URL / JOB_SECRET / VIBE_APP_KEY env values and redeploy if you used placeholders (see OPERATIONS.md).');
}
main().catch((e) => { console.error('[deploy] FAILED:', mask(e.message)); process.exit(1); });
