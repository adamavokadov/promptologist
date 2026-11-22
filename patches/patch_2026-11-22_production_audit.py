#!/usr/bin/env python3
"""Apply the Promptolog production audit fixes to the 2026-11-22 repository.

From the repository root, run:
    python3 patch_2026-11-22_production_audit.py --dry-run --diff
    python3 patch_2026-11-22_production_audit.py
    npm ci && npm run build && npm test && npm run audit:contrast

Requires Python 3.12 and the tracked package-lock.json from the repository.
The plan is validated before writing. Default backups are under .patch-backup/.
An archived copy lives in patches/. --commit commits only planned files.
"""

from __future__ import annotations

import argparse
import difflib
import json
from pathlib import Path
import runpy
import stat
import subprocess
import sys
import tempfile
from dataclasses import dataclass

PATCH_ID = '2026-11-22_production_audit'
PATCH_DATE = '2026-11-22'
PATCH_FILE = f'patch_{PATCH_ID}.py'
COMMIT_MESSAGE = 'fix: harden prompt optimization and responsive layouts'

HUNKS = {
    '.devcontainer/devcontainer.json': (
      ((
        '    "ghcr.io/devcontainers/features/python:1": { "version": "3.12" },\n'
        '    "ghcr.io/devcontainers/features/github-cli:1": {}\n'
        '  },\n'
        '  "forwardPorts": [3000, 5173],\n'
        '  "postCreateCommand": "npm ci || npm install",\n'
        '  "customizations": {\n'
        '    "vscode": {\n'
        '      "extensions": ["editorconfig.editorconfig", "bradlc.vscode-tailwindcss", "vitest.explorer"]\n'
        '    }\n'
      ), (
        '    "ghcr.io/devcontainers/features/python:1": { "version": "3.12" },\n'
        '    "ghcr.io/devcontainers/features/github-cli:1": {}\n'
        '  },\n'
        '  "forwardPorts": [3000, 5173],\n'
        '  "postCreateCommand": "npm ci",\n'
        '  "customizations": {\n'
        '    "vscode": {\n'
        '      "extensions": ["editorconfig.editorconfig", "bradlc.vscode-tailwindcss", "vitest.explorer"]\n'
        '    }\n'
      )),
    ),
    '.env.example': (
      ((
        'DATA_DIR=\n'
        'NODE_ENV=production\n'
        '# Injected by the platform. Local default 3000.\n'
        'PORT=3000\n'
        '# Local development only (ignored in production): skip Gateway identity.\n'
        'DEV_AUTH_BYPASS=0\n'
        '# Optional override of the CSP frame-ancestors list.\n'
        'FRAME_ANCESTORS=\n'
      ), (
        'DATA_DIR=\n'
        'NODE_ENV=production\n'
        '# Injected by the platform. Local default 3000.\n'
        'PORT=3000\n'
        '# Optional bind address. Use 127.0.0.1 for direct local smoke tests.\n'
        '# HOST=127.0.0.1\n'
        '# Local development only (ignored in production): skip Gateway identity.\n'
        'DEV_AUTH_BYPASS=0\n'
        '# Optional override of the CSP frame-ancestors list.\n'
        'FRAME_ANCESTORS=\n'
      )),
    ),
    '.github/workflows/ci.yml': (
      ((
        '          cache: npm\n'
        '      - run: npm ci\n'
        '      - run: npm run build\n'
        '      - run: npm test\n'
      ), (
        '          cache: npm\n'
        '      - run: npm ci\n'
        '      - run: npm run build\n'
        '      - run: npm test\n'
        '      - run: npm run audit:contrast\n'
      )),
    ),
    'agents.md': (
      ((
        'The owner works in GitHub Codespaces and deploys by himself. Agents produce source and patches only: no deployment, no real keys.\n'
        '\n'
        '## 2. Stack and layout\n'
        '\n'
        '- Node >= 22.5 (devcontainer: 24), TypeScript strict, Fastify 5, `node:sqlite`, zod 4. React 18, Vite, Tailwind 3 with a hand-written design system in `index.css`, lucide-react, marked + DOMPurify. Tests: vitest.\n'
        '- `shared/src/index.ts`: constants, zod schemas, DTO types. `apps/server/src/*`: backend. `apps/web/src/*`: `App.tsx` (shell), `ui.tsx` (primitives), `strings.ru.ts` (all UI strings), `index.css`, `screens/*`, `components/*`. `scripts/`, `tests/`, `patches/` (archived patch scripts).\n'
        '\n'
        '## 3. Commands\n'
        '\n'
      ), (
        'The owner works in GitHub Codespaces and deploys by himself. Agents produce source and patches only: no deployment, no real keys.\n'
        '\n'
        '## 2. Stack and layout\n'
        '\n'
        '- Node >= 22.12 (devcontainer: 24), TypeScript strict, Fastify 5, `node:sqlite`, zod 4. React 18, Vite, Tailwind 3 with a hand-written design system in `index.css`, lucide-react, marked + DOMPurify. Tests: vitest.\n'
        '- `shared/src/index.ts`: constants, zod schemas, DTO types. `apps/server/src/*`: backend. `apps/web/src/*`: `App.tsx` (shell), `ui.tsx` (primitives), `strings.ru.ts` (all UI strings), `index.css`, `screens/*`, `components/*`. `scripts/`, `tests/`, `patches/` (archived patch scripts).\n'
        '\n'
        '## 3. Commands\n'
        '\n'
      )),
      ((
        '9. `localStorage` is always wrapped in `try/catch` (blocked in iframes). SQL only through prepared statements. zod validates every input.\n'
        '\n'
        '## 6. Design system\n'
        '\n'
        'Before any UI task read `design.md` fully: Part 0 is the canonical Obsidian / Linear Dark system (dark default, light sibling, indigo accent, tokens in `apps/web/src/styles/tokens.css`); Part I (the «Ноябрь» brief) and Addendum A keep structure, accessibility, engineering and QA rules, and their visual values are superseded. Decisions D1–D5 are resolved (D2 superseded: dark default). Tokens and the shell are implemented; the screens still use deprecated flat aliases (`glass`, `card`, `inset-field`) until migrated. Run `npm run audit:contrast` after any token change.\n'
        '\n'
        '## 7. Patch-script standard\n'
        '\n'
        'File `patch_<YYYY-MM-DD>_<slug>.py` in the repo root. Python 3.12, stdlib only.\n'
      ), (
        '9. `localStorage` is always wrapped in `try/catch` (blocked in iframes). SQL only through prepared statements. zod validates every input.\n'
        '\n'
        '## 6. Design system\n'
        '\n'
        'Before any UI task read `design.md` fully: Part 0 is the canonical Obsidian / Linear Dark system (dark default, light sibling, indigo accent, tokens in `apps/web/src/styles/tokens.css`); Part I (the «Ноябрь» brief) and Addendum A keep structure, accessibility, engineering and QA rules, and their visual values are superseded. Decisions D1–D5 are resolved (D2 superseded: dark default). The shell and screens use the shared `surface`, `card`, and `field` classes and canonical design tokens. Run `npm run audit:contrast` after any token change.\n'
        '\n'
        '## 7. Patch-script standard\n'
        '\n'
        'File `patch_<YYYY-MM-DD>_<slug>.py` in the repo root. Python 3.12, stdlib only.\n'
      )),
    ),
    'apps/server/src/config.ts': (
      ((
        '}\n'
        '\n'
        'export const config = {\n'
        '  port: Number(process.env.PORT ?? 3000),\n'
        "  nodeEnv: process.env.NODE_ENV ?? 'development',\n"
        '  /** Service key (vibe_api_...) for AI router, search, infra, notifications and background jobs. */\n'
        "  apiKey: process.env.VIBE_API_KEY ?? '',\n"
        '  /** OAuth application key (vibe_app_...) used together with the forwarded session to resolve identity via GET /v1/me. */\n'
      ), (
        '}\n'
        '\n'
        'export const config = {\n'
        '  port: Number(process.env.PORT ?? 3000),\n'
        "  host: process.env.HOST ?? '0.0.0.0',\n"
        "  nodeEnv: process.env.NODE_ENV ?? 'development',\n"
        '  /** Service key (vibe_api_...) for AI router, search, infra, notifications and background jobs. */\n'
        "  apiKey: process.env.VIBE_API_KEY ?? '',\n"
        '  /** OAuth application key (vibe_app_...) used together with the forwarded session to resolve identity via GET /v1/me. */\n'
      )),
      ((
        "  jobSecretPrevious: process.env.JOB_SECRET_PREVIOUS ?? '',\n"
        '  /** Encrypts stored provider API keys (AES-256-GCM). Without it keys cannot be saved. */\n'
        "  engineSecret: process.env.ENGINE_SECRET ?? '',\n"
        '  /** Allow Custom Base URL on private networks and plain http (local proxies). Off by default. */\n'
        "  engineAllowPrivate: process.env.ENGINE_ALLOW_PRIVATE === '1',\n"
        '  /** Local development only: skip Gateway identity (ignored when NODE_ENV=production). */\n'
        "  devAuthBypass: process.env.DEV_AUTH_BYPASS === '1' && (process.env.NODE_ENV ?? 'development') !== 'production',\n"
        "  staticDir: process.env.STATIC_DIR ?? path.resolve(process.cwd(), 'dist/public'),\n"
        '};\n'
      ), (
        "  jobSecretPrevious: process.env.JOB_SECRET_PREVIOUS ?? '',\n"
        '  /** Encrypts stored provider API keys (AES-256-GCM). Without it keys cannot be saved. */\n'
        "  engineSecret: process.env.ENGINE_SECRET ?? '',\n"
        '  /** Allow Custom Base URL on private networks and plain http (local proxies). Off by default. */\n'
        "  engineAllowPrivate: process.env.ENGINE_ALLOW_PRIVATE === '1' && process.env.NODE_ENV !== 'production',\n"
        '  /** Local development only: skip Gateway identity (ignored when NODE_ENV=production). */\n'
        "  devAuthBypass: process.env.DEV_AUTH_BYPASS === '1' && (process.env.NODE_ENV ?? 'development') !== 'production',\n"
        "  staticDir: process.env.STATIC_DIR ?? path.resolve(process.cwd(), 'dist/public'),\n"
        '};\n'
      )),
    ),
    'apps/server/src/db.ts': (
      ((
        '  const tokens = query.toLowerCase().split(/[^\\p{L}\\p{N}]+/u).filter(Boolean).slice(0, 8);\n'
        '  if (tokens.length === 0) return [];\n'
        '  if (db.fts) {\n'
        '    const match = tokens.map((t) => `"${t.replace(/"/g, \'\')}"*`).join(\' \');\n'
        "    const rows = db.all<{ ref_key: string }>('SELECT ref_key FROM search_fts WHERE search_fts MATCH ? LIMIT 2000', match);\n"
        '    const ids = rows.filter((r) => r.ref_key.startsWith(`${refType}:`)).map((r) => r.ref_key.slice(refType.length + 1));\n'
        '    if (userId === null || ids.length === 0) return ids;\n'
        '    const owned = db.all<{ ref_id: string }>(\n'
        "      `SELECT ref_id FROM search_docs WHERE ref_type = ? AND user_id = ? AND ref_id IN (${ids.map(() => '?').join(',')})`, refType, userId, ...ids);\n"
        '    return owned.map((r) => r.ref_id);\n'
        '  }\n'
        "  const where = tokens.map(() => 'LOWER(body) LIKE ?').join(' AND ');\n"
        "  const likeParams = tokens.map((t) => `%${t.replace(/[%_]/g, '')}%`);\n"
        "  const sql = `SELECT ref_id FROM search_docs WHERE ref_type = ? ${userId === null ? '' : 'AND user_id = ?'} AND ${where} LIMIT 2000`;\n"
      ), (
        '  const tokens = query.toLowerCase().split(/[^\\p{L}\\p{N}]+/u).filter(Boolean).slice(0, 8);\n'
        '  if (tokens.length === 0) return [];\n'
        '  if (db.fts) {\n'
        '    const match = tokens.map((t) => `"${t.replace(/"/g, \'\')}"*`).join(\' \');\n'
        "    const userFilter = userId === null ? '' : ' AND d.user_id = ?';\n"
        '    const params = userId === null ? [refType, match] : [refType, match, userId];\n'
        '    return db.all<{ ref_id: string }>(\n'
        '      `SELECT d.ref_id FROM search_fts\n'
        '       JOIN search_docs d ON d.ref_type = ? AND d.ref_id = substr(search_fts.ref_key, length(d.ref_type) + 2)\n'
        "         AND search_fts.ref_key = d.ref_type || ':' || d.ref_id\n"
        '       WHERE search_fts MATCH ?${userFilter} LIMIT 2000`,\n'
        '      ...params,\n'
        '    ).map((row) => row.ref_id);\n'
        '  }\n'
        "  const where = tokens.map(() => 'LOWER(body) LIKE ?').join(' AND ');\n"
        "  const likeParams = tokens.map((t) => `%${t.replace(/[%_]/g, '')}%`);\n"
        "  const sql = `SELECT ref_id FROM search_docs WHERE ref_type = ? ${userId === null ? '' : 'AND user_id = ?'} AND ${where} LIMIT 2000`;\n"
      )),
    ),
    'apps/server/src/engine.ts': (
      ((
        "import { createCipheriv, createDecipheriv, randomBytes, scryptSync } from 'node:crypto';\n"
        "import { lookup } from 'node:dns/promises';\n"
        "import net from 'node:net';\n"
        "import { config } from './config.ts';\n"
        "import { type Db } from './db.ts';\n"
        "import { log, AppError, jsonParse } from './util.ts';\n"
        "import { VibeError, parseErrorEnvelope, type ChatMessage, type VibeClient } from './vibe.ts';\n"
        "import { engineConfigSchema, engineUpdateSchema, ENGINE_CATALOG, type EngineConfig, type EngineView, type Provider } from '../../../shared/src/index.ts';\n"
        "import type { z } from 'zod';\n"
        '\n'
        '/** Public defaults (from provider docs, overridable with Custom_Base_URL; not verified against Nov 2026 docs). */\n'
        'export const DEFAULT_BASE_URLS: Record<string, string> = {\n'
        "  anthropic: 'https://api.anthropic.com', openai: 'https://api.openai.com/v1', google: 'https://generativelanguage.googleapis.com/v1beta',\n"
        "  alibaba: 'https://dashscope-intl.aliyuncs.com/compatible-mode/v1', moonshot: 'https://api.moonshot.ai/v1',\n"
        '};\n'
        "const SETTINGS_KEY = 'engine';\n"
      ), (
        "import { createCipheriv, createDecipheriv, randomBytes, scryptSync } from 'node:crypto';\n"
        "import { config } from './config.ts';\n"
        "import { engineUrlFetch, resolveEngineUrl } from './engine-url.ts';\n"
        "import { type Db } from './db.ts';\n"
        "import { log, AppError, extractJson, jsonParse } from './util.ts';\n"
        "import { VibeError, parseErrorEnvelope, type ChatMessage, type VibeClient } from './vibe.ts';\n"
        "import { engineConfigSchema, engineUpdateSchema, ENGINE_CATALOG, supportsCustomTemperature, type EngineConfig, type EngineView, type Provider } from '../../../shared/src/index.ts';\n"
        "import type { z } from 'zod';\n"
        '\n'
        '/** Public defaults (from provider docs, overridable with Custom_Base_URL; not verified against Nov 2026 docs). */\n'
        'const DEFAULT_BASE_URLS: Record<string, string> = {\n'
        "  anthropic: 'https://api.anthropic.com', openai: 'https://api.openai.com/v1', google: 'https://generativelanguage.googleapis.com/v1beta',\n"
        "  alibaba: 'https://dashscope-intl.aliyuncs.com/compatible-mode/v1', moonshot: 'https://api.moonshot.ai/v1',\n"
        '};\n'
        "const SETTINGS_KEY = 'engine';\n"
      )),
      ((
        "  let hint = '';\n"
        "  if (blob) { try { const k = decryptSecret(blob); hint = k.length > 8 ? `…${k.slice(-4)}` : '…'; } catch { hint = ''; } }\n"
        '  return { ...cfg, has_key: !!blob, key_hint: hint, secret_configured: config.engineSecret.length >= 16, catalog: ENGINE_CATALOG, default_base_urls: DEFAULT_BASE_URLS };\n'
        '}\n'
        'export async function updateEngine(db: Db, input: z.infer<typeof engineUpdateSchema>): Promise<EngineView> {\n'
        '  const body = engineUpdateSchema.parse(input);\n'
        "  const next = engineConfigSchema.parse({ ...getEngineConfig(db), ...Object.fromEntries(Object.entries(body).filter(([k, v]) => k !== 'api_key' && v !== undefined)) });\n"
        '  if (next.base_url) await assertSafeBaseUrl(next.base_url);\n'
        "  if (next.provider === 'custom' && !next.base_url) throw new AppError(400, 'base_url_required', 'Для custom-провайдера нужен Custom Base URL');\n"
        "  const put = (k: string, v: unknown) => db.run('INSERT INTO settings(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value', k, JSON.stringify(v));\n"
        "  const del = (k: string) => db.run('DELETE FROM settings WHERE key = ?', k);\n"
        '  // Encrypt first: a missing ENGINE_SECRET must fail before anything is written.\n'
        "  const blob = body.api_key === undefined ? undefined : body.api_key === '' ? '' : encryptSecret(body.api_key.trim());\n"
        "  db.tx(() => { put(SETTINGS_KEY, next); if (blob === '') del(KEY_SETTINGS_KEY); else if (blob) put(KEY_SETTINGS_KEY, blob); });\n"
        '  return engineView(db);\n'
        '}\n'
        '\n'
        '// ---------- SSRF guard for Custom_Base_URL ----------\n'
        'export function isPrivateAddress(ip: string): boolean {\n'
        '  if (net.isIPv4(ip)) {\n'
        "    const [a, b] = ip.split('.').map(Number) as [number, number];\n"
        '    return a === 10 || a === 127 || a === 0 || (a === 169 && b === 254) || (a === 172 && b >= 16 && b <= 31) || (a === 192 && b === 168) || (a === 100 && b >= 64 && b <= 127);\n'
        '  }\n'
        '  const v = ip.toLowerCase();\n'
        "  if (v.startsWith('::ffff:')) return isPrivateAddress(v.slice(7));\n"
        "  return v === '::1' || v === '::' || v.startsWith('fc') || v.startsWith('fd') || v.startsWith('fe80');\n"
        '}\n'
        'export async function assertSafeBaseUrl(raw: string): Promise<URL> {\n'
        '  let u: URL;\n'
        "  try { u = new URL(raw); } catch { throw new AppError(400, 'bad_base_url', 'Custom Base URL: некорректный адрес'); }\n"
        '  const allowPrivate = config.engineAllowPrivate;\n'
        "  if (u.protocol !== 'https:' && !(allowPrivate && u.protocol === 'http:')) throw new AppError(400, 'bad_base_url', 'Custom Base URL должен начинаться с https://');\n"
        "  if (u.username || u.password) throw new AppError(400, 'bad_base_url', 'Custom Base URL не должен содержать логин и пароль');\n"
        '  if (allowPrivate) return u;\n'
        "  const host = u.hostname.replace(/^\\[|\\]$/g, '');\n"
        "  const addrs = net.isIP(host) ? [host] : (await lookup(host, { all: true }).catch(() => { throw new AppError(400, 'bad_base_url', 'Custom Base URL: хост не найден'); })).map((a) => a.address);\n"
        "  if (host === 'localhost' || addrs.some(isPrivateAddress)) throw new AppError(400, 'bad_base_url', 'Custom Base URL указывает на внутренний адрес: это запрещено');\n"
        '  return u;\n'
        '}\n'
        '\n'
        '// ---------- provider adapters ----------\n'
        'export interface EngineChat { content: string; tokens: number; model: string; provider: Provider }\n'
      ), (
        "  let hint = '';\n"
        "  if (blob) { try { const k = decryptSecret(blob); hint = k.length > 8 ? `…${k.slice(-4)}` : '…'; } catch { hint = ''; } }\n"
        '  return { ...cfg, has_key: !!blob, key_hint: hint, secret_configured: config.engineSecret.length >= 16, catalog: ENGINE_CATALOG, default_base_urls: DEFAULT_BASE_URLS };\n'
        '}\n'
        "const engineBase = (cfg: EngineConfig) => (cfg.base_url || DEFAULT_BASE_URLS[cfg.provider] || '').replace(/\\/+$/, '');\n"
        '\n'
        'export async function updateEngine(db: Db, input: z.infer<typeof engineUpdateSchema>): Promise<EngineView> {\n'
        '  const { api_key: key, ...fields } = input;\n'
        '  const current = getEngineConfig(db);\n'
        '  const providerChanged = fields.provider !== undefined && fields.provider !== current.provider;\n'
        "  const inherited = providerChanged ? { ...current, base_url: '' } : current;\n"
        '  const next = engineConfigSchema.parse({ ...inherited, ...fields });\n'
        "  if (next.provider === 'custom' && !next.base_url) {\n"
        "    throw new AppError(400, 'base_url_required', 'Для custom-провайдера нужен Custom Base URL');\n"
        '  }\n'
        '  if (next.base_url) await resolveEngineUrl(next.base_url);\n'
        '\n'
        '  const destinationChanged = providerChanged || engineBase(current) !== engineBase(next);\n'
        '  const blob = key ? encryptSecret(key) : undefined;\n'
        "  const put = (k: string, v: unknown) => db.run('INSERT INTO settings(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value', k, JSON.stringify(v));\n"
        '  db.tx(() => {\n'
        '    if (JSON.stringify(current) !== JSON.stringify(getEngineConfig(db))) {\n'
        "      throw new AppError(409, 'engine_settings_changed', 'Настройки движка изменились. Обновите страницу и повторите.');\n"
        '    }\n'
        '    put(SETTINGS_KEY, next);\n'
        '    if (blob) put(KEY_SETTINGS_KEY, blob);\n'
        "    else if (key === '' || destinationChanged) db.run('DELETE FROM settings WHERE key = ?', KEY_SETTINGS_KEY);\n"
        '  });\n'
        '  return engineView(db);\n'
        '}\n'
        '\n'
        '// ---------- provider adapters ----------\n'
        'export interface EngineChat { content: string; tokens: number; model: string; provider: Provider }\n'
      )),
      ((
        '}\n'
        '\n'
        '/** One chat completion through the configured engine. JSON mode is a hint only; callers always validate. */\n'
        'export async function engineChat(db: Db, deps: EngineDeps, messages: ChatMessage[], o: { json?: boolean; maxTokens?: number } = {}): Promise<EngineChat> {\n'
        '  const cfg = getEngineConfig(db); const f = deps.fetchImpl ?? fetch; const maxTokens = o.maxTokens ?? 4000;\n'
        "  if (cfg.provider === 'platform') {\n"
        '    const r = await deps.vibe.chat(cfg.model, messages, { temperature: cfg.temperature, maxTokens, json: o.json });\n'
        "    return { content: r.content, tokens: r.totalTokens, model: r.model, provider: 'platform' };\n"
        '  }\n'
        '  const blob = storedKey(db);\n'
        "  if (!blob) throw new AppError(409, 'engine_key_missing', 'Для выбранного провайдера не задан ключ API (Настройки, Движок)');\n"
        '  const key = decryptSecret(blob);\n'
        "  const base = (cfg.base_url || DEFAULT_BASE_URLS[cfg.provider] || '').replace(/\\/+$/, '');\n"
        "  if (!base) throw new AppError(400, 'base_url_required', 'Для custom-провайдера нужен Custom Base URL');\n"
        '  if (cfg.base_url) await assertSafeBaseUrl(cfg.base_url);\n'
        "  const sys = messages.filter((m) => m.role === 'system').map((m) => m.content).join('\\n\\n'); const rest = messages.filter((m) => m.role !== 'system');\n"
        '  try {\n'
        "    if (cfg.provider === 'anthropic') {\n"
        "      const j = await httpJson(f, `${base}/v1/messages`, { 'x-api-key': key, 'anthropic-version': '2023-06-01' },\n"
        '        { model: cfg.model, max_tokens: maxTokens, temperature: Math.min(1, cfg.temperature), system: sys, messages: rest.map((m) => ({ role: m.role, content: m.content })) }, key);\n'
        "      const text = (Array.isArray(j.content) ? j.content : []).filter((b: any) => b?.type === 'text').map((b: any) => b.text).join('');\n"
        "      if (!text) throw new VibeError(502, 'EMPTY_COMPLETION', 'Model returned no content', 'server');\n"
        "      return { content: text, tokens: Number(j.usage?.input_tokens ?? 0) + Number(j.usage?.output_tokens ?? 0), model: String(j.model ?? cfg.model), provider: 'anthropic' };\n"
        '    }\n'
      ), (
        '}\n'
        '\n'
        '/** One chat completion through the configured engine. JSON mode is a hint only; callers always validate. */\n'
        'export async function engineChat(db: Db, deps: EngineDeps, messages: ChatMessage[], o: { json?: boolean; maxTokens?: number } = {}): Promise<EngineChat> {\n'
        '  const cfg = getEngineConfig(db); const maxTokens = o.maxTokens ?? 4000;\n'
        "  if (cfg.provider === 'platform') {\n"
        '    const r = await deps.vibe.chat(cfg.model, messages, { temperature: cfg.temperature, maxTokens, json: o.json });\n'
        "    return { content: r.content, tokens: r.totalTokens, model: r.model, provider: 'platform' };\n"
        '  }\n'
        '  const blob = storedKey(db);\n'
        "  if (!blob) throw new AppError(409, 'engine_key_missing', 'Для выбранного провайдера не задан ключ API (Настройки, Движок)');\n"
        '  const key = decryptSecret(blob);\n'
        '  const base = engineBase(cfg);\n'
        "  if (!base) throw new AppError(400, 'base_url_required', 'Для custom-провайдера нужен Custom Base URL');\n"
        '  const custom = cfg.base_url ? await resolveEngineUrl(cfg.base_url) : undefined;\n'
        '  const f = deps.fetchImpl ?? (custom ? engineUrlFetch(custom) : fetch);\n'
        '  const sampling = supportsCustomTemperature(cfg.provider, cfg.model) ? { temperature: cfg.temperature } : {};\n'
        "  const sys = messages.filter((m) => m.role === 'system').map((m) => m.content).join('\\n\\n'); const rest = messages.filter((m) => m.role !== 'system');\n"
        '  try {\n'
        "    if (cfg.provider === 'anthropic') {\n"
        "      const j = await httpJson(f, `${base}/v1/messages`, { 'x-api-key': key, 'anthropic-version': '2023-06-01' },\n"
        '        { model: cfg.model, max_tokens: maxTokens, ...(sampling.temperature === undefined ? {} : { temperature: Math.min(1, sampling.temperature) }), system: sys, messages: rest.map((m) => ({ role: m.role, content: m.content })) }, key);\n'
        "      const text = (Array.isArray(j.content) ? j.content : []).filter((b: any) => b?.type === 'text').map((b: any) => b.text).join('');\n"
        "      if (!text) throw new VibeError(502, 'EMPTY_COMPLETION', 'Model returned no content', 'server');\n"
        "      return { content: text, tokens: Number(j.usage?.input_tokens ?? 0) + Number(j.usage?.output_tokens ?? 0), model: String(j.model ?? cfg.model), provider: 'anthropic' };\n"
        '    }\n'
      )),
      ((
        "      return { content: text, tokens: Number(j.usageMetadata?.totalTokenCount ?? 0), model: cfg.model, provider: 'google' };\n"
        '    }\n'
        '    // openai, alibaba, moonshot, custom: OpenAI-compatible chat completions\n'
        '    const j = await httpJson(f, `${base}/chat/completions`, { Authorization: `Bearer ${key}` },\n'
        "      { model: cfg.model, messages, temperature: cfg.temperature, max_tokens: maxTokens, ...(o.json && cfg.provider === 'openai' ? { response_format: { type: 'json_object' } } : {}) }, key);\n"
        '    const content = j?.choices?.[0]?.message?.content;\n'
        "    if (typeof content !== 'string') throw new VibeError(502, 'EMPTY_COMPLETION', 'Model returned no content', 'server');\n"
        '    return { content, tokens: Number(j.usage?.total_tokens ?? 0), model: String(j.model ?? cfg.model), provider: cfg.provider };\n'
        '  } catch (e) {\n'
        "    if (e instanceof VibeError) log.warn('engine call failed', { provider: cfg.provider, code: e.code, kind: e.kind });\n"
        '    throw e;\n'
        '  }\n'
        '}\n'
        '\n'
        '// ---------- structured output ----------\n'
        'export function extractJsonObject(text: string): unknown {\n'
        "  const t = text.trim().replace(/^```(?:json)?\\s*/i, '').replace(/\\s*```$/i, '');\n"
        '  try { return JSON.parse(t); } catch { /* locate the outermost object */ }\n'
        "  const s = t.indexOf('{'); const e = t.lastIndexOf('}');\n"
        '  if (s >= 0 && e > s) return JSON.parse(t.slice(s, e + 1));\n'
        "  throw new Error('No JSON object found');\n"
        '}\n'
        'export class EngineOutputError extends AppError {\n'
        "  constructor(detail: string) { super(502, 'engine_bad_output', `Модель вернула ответ в неверном формате: ${detail}`); }\n"
        '}\n'
        '/** Calls the engine, parses and validates JSON against `schema`; on failure asks once more with the validation error. */\n'
      ), (
        "      return { content: text, tokens: Number(j.usageMetadata?.totalTokenCount ?? 0), model: cfg.model, provider: 'google' };\n"
        '    }\n'
        '    // openai, alibaba, moonshot, custom: OpenAI-compatible chat completions\n'
        '    const j = await httpJson(f, `${base}/chat/completions`, { Authorization: `Bearer ${key}` },\n'
        "      { model: cfg.model, messages, ...sampling, ...(cfg.provider === 'openai' ? { max_completion_tokens: maxTokens } : { max_tokens: maxTokens }),\n"
        "        ...(o.json && cfg.provider === 'openai' ? { response_format: { type: 'json_object' } } : {}) }, key);\n"
        '    const content = j?.choices?.[0]?.message?.content;\n'
        "    if (typeof content !== 'string' || !content.trim()) throw new VibeError(502, 'EMPTY_COMPLETION', 'Model returned no content', 'server');\n"
        '    return { content, tokens: Number(j.usage?.total_tokens ?? 0), model: String(j.model ?? cfg.model), provider: cfg.provider };\n'
        '  } catch (e) {\n'
        "    if (e instanceof VibeError) log.warn('engine call failed', { provider: cfg.provider, code: e.code, kind: e.kind });\n"
        '    throw e;\n'
        '  }\n'
        '}\n'
        '\n'
        '// ---------- structured output ----------\n'
        'export class EngineOutputError extends AppError {\n'
        "  constructor(detail: string) { super(502, 'engine_bad_output', `Модель вернула ответ в неверном формате: ${detail}`); }\n"
        '}\n'
        '/** Calls the engine, parses and validates JSON against `schema`; on failure asks once more with the validation error. */\n'
      )),
      ((
        '  for (let attempt = 0; attempt < 2; attempt++) {\n'
        '    const r = await engineChat(db, deps, msgs, { json: true, maxTokens: o.maxTokens });\n'
        '    tokens += r.tokens;\n'
        '    try {\n'
        '      const parsed = schema.safeParse(extractJsonObject(r.content));\n'
        '      if (parsed.success) return { data: parsed.data, tokens, model: r.model, provider: r.provider };\n'
        "      last = parsed.error.issues.slice(0, 3).map((i) => `${i.path.join('.') || 'root'}: ${i.message}`).join('; ');\n"
        '    } catch (e) { last = (e as Error).message; }\n'
        "    msgs = [...messages, { role: 'assistant', content: r.content.slice(0, 4000) }, { role: 'user', content: `Your previous reply was invalid (${last}). Reply again with ONE valid JSON object only, matching the schema exactly. No prose, no code fences.` }];\n"
      ), (
        '  for (let attempt = 0; attempt < 2; attempt++) {\n'
        '    const r = await engineChat(db, deps, msgs, { json: true, maxTokens: o.maxTokens });\n'
        '    tokens += r.tokens;\n'
        '    try {\n'
        '      const parsed = schema.safeParse(extractJson(r.content));\n'
        '      if (parsed.success) return { data: parsed.data, tokens, model: r.model, provider: r.provider };\n'
        "      last = parsed.error.issues.slice(0, 3).map((i) => `${i.path.join('.') || 'root'}: ${i.message}`).join('; ');\n"
        '    } catch (e) { last = (e as Error).message; }\n'
        "    msgs = [...messages, { role: 'assistant', content: r.content.slice(0, 4000) }, { role: 'user', content: `Your previous reply was invalid (${last}). Reply again with ONE valid JSON object only, matching the schema exactly. No prose, no code fences.` }];\n"
      )),
    ),
    'apps/server/src/generation.ts': (
      ((
        "} from '../../../shared/src/index.ts';\n"
        "import { type Db, type Row, getSettings, indexDoc } from './db.ts';\n"
        "import { getVibe, VibeError, type VibeClient, type ChatMessage } from './vibe.ts';\n"
        "import { getCurrentVersion, runChecklist, type SkillVersion } from './skills.ts';\n"
        "import { uid, nowIso, jsonParse, log } from './util.ts';\n"
        '\n'
        "export const LANGUAGE_NAME = { ru: 'русском', en: 'английском (English)' } as const;\n"
        '\n'
        "export function buildTransformerSystem(system: SystemId, language: 'ru' | 'en', skillBody: string): string {\n"
      ), (
        "} from '../../../shared/src/index.ts';\n"
        "import { type Db, type Row, getSettings, indexDoc } from './db.ts';\n"
        "import { getVibe, VibeError, type VibeClient, type ChatMessage } from './vibe.ts';\n"
        "import { getCurrentVersion, runChecklist, type SkillVersion } from './skills.ts';\n"
        "import { uid, nowIso, jsonParse, log, extractJson, AppError } from './util.ts';\n"
        '\n'
        "export const LANGUAGE_NAME = { ru: 'русском', en: 'английском (English)' } as const;\n"
        '\n'
        "export function buildTransformerSystem(system: SystemId, language: 'ru' | 'en', skillBody: string): string {\n"
      )),
      ((
        '    `<raw_request>${rawInput}</raw_request>`,\n'
        '    `<options>detail=${o.detail}; include_format=${o.include_format}; task_type=${o.task_type}</options>`,\n'
        "    refinement ? `<refinement>${refinement}</refinement>` : '',\n"
        "  ].filter(Boolean).join('\\n');\n"
        '}\n'
        '\n'
        'export function extractJson(text: string): unknown {\n'
        "  const t = text.trim().replace(/^```(?:json)?\\s*/i, '').replace(/\\s*```$/i, '');\n"
        '  try { return JSON.parse(t); } catch { /* try to locate object */ }\n'
        "  const s = t.indexOf('{'); const e = t.lastIndexOf('}');\n"
        '  if (s >= 0 && e > s) return JSON.parse(t.slice(s, e + 1));\n'
        "  throw new Error('No JSON object found');\n"
        '}\n'
        '\n'
        'export interface TransformCtx { vibe: VibeClient; model: string }\n'
        'export interface TransformResult { output: TransformOutput; tokens: number; checklistErrors: string[] }\n'
      ), (
        '    `<raw_request>${rawInput}</raw_request>`,\n'
        '    `<options>detail=${o.detail}; include_format=${o.include_format}; task_type=${o.task_type}</options>`,\n'
        "    refinement ? `<refinement>${refinement}</refinement>` : '',\n"
        "  ].filter(Boolean).join('\\n');\n"
        '}\n'
        '\n'
        'export interface TransformCtx { vibe: VibeClient; model: string }\n'
        'export interface TransformResult { output: TransformOutput; tokens: number; checklistErrors: string[] }\n'
      )),
      ((
        '  let genId = p.req.generation_id;\n'
        '  let rawInput = p.req.raw_input;\n'
        '  if (genId) {\n'
        "    const g = db.get('SELECT * FROM generations WHERE id = ? AND user_id = ? AND deleted_at IS NULL', genId, userId);\n"
        "    if (!g) throw new Error('Generation not found');\n"
        "    rawInput = `${g.raw_input}\\n\\n${p.extraAnswers ?? ''}`.trim();\n"
        '    db.run("UPDATE generations SET raw_input = ?, status = \'running\', questions = NULL WHERE id = ?", rawInput, genId);\n'
        '  } else {\n'
        '    genId = p.newId ?? uid();\n'
      ), (
        '  let genId = p.req.generation_id;\n'
        '  let rawInput = p.req.raw_input;\n'
        '  if (genId) {\n'
        "    const g = db.get('SELECT * FROM generations WHERE id = ? AND user_id = ? AND deleted_at IS NULL', genId, userId);\n"
        "    if (!g) throw new AppError(404, 'not_found', 'Генерация не найдена');\n"
        "    if (g.status !== 'draft_questions') throw new AppError(409, 'not_awaiting_answers', 'Эта генерация уже обработана');\n"
        "    rawInput = `${g.raw_input}\\n\\n${p.extraAnswers ?? ''}`.trim();\n"
        '    db.run("UPDATE generations SET raw_input = ?, status = \'running\', questions = NULL WHERE id = ?", rawInput, genId);\n'
        '  } else {\n'
        '    genId = p.newId ?? uid();\n'
      )),
      ((
        '/** Regenerate one card with optional feedback; stores a new row linked to the old one (variant chain). */\n'
        'export async function regenerateResult(p: { db: Db; userId: string; generationId: string; resultId: string; feedback?: string; vibe?: VibeClient; onQuota?: (r: string) => void }): Promise<ResultDTO> {\n'
        '  const { db } = p; const vibe = p.vibe ?? getVibe();\n'
        "  const g = db.get('SELECT * FROM generations WHERE id = ? AND user_id = ? AND deleted_at IS NULL', p.generationId, p.userId);\n"
        "  if (!g) throw new Error('Generation not found');\n"
        "  const old = db.get('SELECT * FROM generation_results WHERE id = ? AND generation_id = ?', p.resultId, p.generationId);\n"
        "  if (!old) throw new Error('Result not found');\n"
        '  const system = old.skill_id as SystemId; const skill = getCurrentVersion(db, system);\n'
        '  const ctx: TransformCtx = { vibe, model: getSettings(db).transformer_model };\n'
      ), (
        '/** Regenerate one card with optional feedback; stores a new row linked to the old one (variant chain). */\n'
        'export async function regenerateResult(p: { db: Db; userId: string; generationId: string; resultId: string; feedback?: string; vibe?: VibeClient; onQuota?: (r: string) => void }): Promise<ResultDTO> {\n'
        '  const { db } = p; const vibe = p.vibe ?? getVibe();\n'
        "  const g = db.get('SELECT * FROM generations WHERE id = ? AND user_id = ? AND deleted_at IS NULL', p.generationId, p.userId);\n"
        "  if (!g) throw new AppError(404, 'not_found', 'Генерация не найдена');\n"
        "  const old = db.get('SELECT * FROM generation_results WHERE id = ? AND generation_id = ?', p.resultId, p.generationId);\n"
        "  if (!old) throw new Error('Result not found');\n"
        '  const system = old.skill_id as SystemId; const skill = getCurrentVersion(db, system);\n'
        '  const ctx: TransformCtx = { vibe, model: getSettings(db).transformer_model };\n'
      )),
    ),
    'apps/server/src/main.ts': (
      ((
        '  const db = openDb();\n'
        '  let ready = false;\n'
        '  const vibe = getVibe();\n'
        '  const app = await buildApp({ db, vibe, ready: () => ready });\n'
        "  await app.listen({ port: config.port, host: '0.0.0.0' });\n"
        "  log.info('listening', { port: config.port, dataDir: config.dataDir, fts: db.fts });\n"
        '  // /healthz is served before seeding finishes; /api/* answers 503 + Retry-After until ready.\n'
        '  setImmediate(async () => {\n'
        '    try {\n'
        '      seedAll(db); ready = true;\n'
        '      const deps = { db, vibe };\n'
        "      await ensureSchedulerJob(db, vibe).then((s) => log.info('scheduler', { ...s }));\n"
        '      for (const runId of pendingRuns(db)) await processJobRun(deps, { runId });\n'
        '      await resumeUnfinished(deps);\n'
        "    } catch (e) { log.error('startup tasks failed', { err: String((e as Error).message) }); ready = true; }\n"
        '  });\n'
        '  const daily = setInterval(() => { void ensureSchedulerJob(db, vibe).catch(() => {}); }, 24 * HOUR_MS);\n'
        '  daily.unref();\n'
        '  const shutdown = () => { void app.close().then(() => process.exit(0)); };\n'
      ), (
        '  const db = openDb();\n'
        '  let ready = false;\n'
        '  const vibe = getVibe();\n'
        '  const app = await buildApp({ db, vibe, ready: () => ready });\n'
        '  await app.listen({ port: config.port, host: config.host });\n'
        "  log.info('listening', { port: config.port, dataDir: config.dataDir, fts: db.fts });\n"
        '  // /healthz is served before seeding finishes; /api/* answers 503 + Retry-After until ready.\n'
        '  setImmediate(async () => {\n'
        '    try {\n'
        '      seedAll(db);\n'
        '      ready = true;\n'
        '      const deps = { db, vibe };\n'
        "      await ensureSchedulerJob(db, vibe).then((s) => log.info('scheduler', { ...s }));\n"
        '      for (const runId of pendingRuns(db)) await processJobRun(deps, { runId });\n'
        '      await resumeUnfinished(deps);\n'
        '    } catch (e) {\n'
        "      log.error('startup tasks failed', { err: String((e as Error).message) });\n"
        '      if (!ready) process.exitCode = 1;\n'
        '      if (!ready) await app.close();\n'
        '    }\n'
        '  });\n'
        '  const daily = setInterval(() => { void ensureSchedulerJob(db, vibe).catch(() => {}); }, 24 * HOUR_MS);\n'
        '  daily.unref();\n'
        '  const shutdown = () => { void app.close().then(() => process.exit(0)); };\n'
      )),
    ),
    'apps/server/src/optimizer-routes.ts': (
      ((
        "import type { FastifyInstance, FastifyRequest } from 'fastify';\n"
        "import { z } from 'zod';\n"
        "import type { Db } from './db.ts';\n"
        "import { unindexDoc } from './db.ts';\n"
        "import type { Identity } from './auth.ts';\n"
        "import { rateLimit } from './auth.ts';\n"
        "import { AppError, nowIso } from './util.ts';\n"
        "import type { VibeClient } from './vibe.ts';\n"
      ), (
        "import type { FastifyInstance, FastifyRequest } from 'fastify';\n"
        "import { z } from 'zod';\n"
        "import { unindexDoc, type Db } from './db.ts';\n"
        "import type { Identity } from './auth.ts';\n"
        "import { rateLimit } from './auth.ts';\n"
        "import { AppError, nowIso } from './util.ts';\n"
        "import type { VibeClient } from './vibe.ts';\n"
      )),
      ((
        "import { OPT_LIMITS, answerRequestSchema, engineUpdateSchema, optimizeRequestSchema, OPT_WORKFLOWS } from '../../../shared/src/index.ts';\n"
        '\n'
        'export interface OptimizerRouteDeps { db: Db; vibe: VibeClient; me: (req: FastifyRequest) => Identity; admin: (req: FastifyRequest) => Identity; fetchImpl?: typeof fetch }\n'
        '\n'
        '/** Prompt optimizer: engine settings, four workflows, compression, library with folders. All routes are under /api/optimizer. */\n'
        'export function registerOptimizerRoutes(app: FastifyInstance, d: OptimizerRouteDeps): void {\n'
        '  const { db, me, admin } = d; const deps = { vibe: d.vibe, fetchImpl: d.fetchImpl };\n'
        "  const limit = (userId: string) => { const l = rateLimit(`opt:${userId}`, 10, 60_000); if (!l.ok) throw new AppError(429, 'rate_limited', 'Слишком много запросов к оптимизатору', l.retryAfter); };\n"
      ), (
        "import { OPT_LIMITS, answerRequestSchema, engineUpdateSchema, optimizeRequestSchema, OPT_WORKFLOWS } from '../../../shared/src/index.ts';\n"
        '\n'
        'export interface OptimizerRouteDeps { db: Db; vibe: VibeClient; me: (req: FastifyRequest) => Identity; admin: (req: FastifyRequest) => Identity; fetchImpl?: typeof fetch }\n'
        '\n'
        'const paramsSchema = z.object({ id: z.string().min(1).max(60) });\n'
        '\n'
        '/** Prompt optimizer: engine settings, four workflows, compression, library with folders. All routes are under /api/optimizer. */\n'
        'export function registerOptimizerRoutes(app: FastifyInstance, d: OptimizerRouteDeps): void {\n'
        '  const { db, me, admin } = d; const deps = { vibe: d.vibe, fetchImpl: d.fetchImpl };\n'
        "  const limit = (userId: string) => { const l = rateLimit(`opt:${userId}`, 10, 60_000); if (!l.ok) throw new AppError(429, 'rate_limited', 'Слишком много запросов к оптимизатору', l.retryAfter); };\n"
      )),
      ((
        '  // ---- engine settings (read for everyone, write for admins; the key is never returned) ----\n'
        "  app.get('/api/optimizer/engine', async () => engineView(db));\n"
        "  app.put('/api/optimizer/engine', async (req) => { admin(req); return updateEngine(db, engineUpdateSchema.parse(req.body)); });\n"
        "  app.post('/api/optimizer/engine/test', async (req) => {\n"
        '    admin(req); const t0 = Date.now();\n'
        "    const r = await engineChat(db, deps, [{ role: 'user', content: 'Reply with the single word: ok' }], { maxTokens: 20 });\n"
        '    return { ok: true, latency_ms: Date.now() - t0, provider: r.provider, model: r.model };\n'
        '  });\n'
        '\n'
        '  // ---- workflows ----\n'
        "  app.post('/api/optimizer/run', async (req) => { const id = me(req); limit(id.userId); return runOptimization(db, { userId: id.userId, deps }, optimizeRequestSchema.parse(req.body)); });\n"
        "  app.post('/api/optimizer/items/:id/answer', async (req) => { const id = me(req); limit(id.userId); return answerOptimization(db, { userId: id.userId, deps }, (req.params as any).id, answerRequestSchema.parse(req.body)); });\n"
        "  app.post('/api/optimizer/items/:id/compress', async (req) => { const id = me(req); limit(id.userId); return compressOptimization(db, { userId: id.userId, deps }, (req.params as any).id); });\n"
        '\n'
        '  // ---- library ----\n'
        "  app.get('/api/optimizer/items', async (req) => {\n"
        '    const id = me(req);\n'
        '    const q = z.object({ page: z.coerce.number().int().min(1).default(1), q: z.string().max(200).optional(), folder: z.string().max(60).optional(),\n'
        "      favorites: z.enum(['0', '1']).optional(), workflow: z.enum(OPT_WORKFLOWS).optional() }).parse(req.query);\n"
        "    return listOptimizations(db, id.userId, { q: q.q, folder: q.folder, favorites: q.favorites === '1', workflow: q.workflow, page: q.page });\n"
        '  });\n'
        "  app.get('/api/optimizer/items/:id', async (req) => rowToOptimization(getOwned(db, (req.params as any).id, me(req).userId)));\n"
        "  app.patch('/api/optimizer/items/:id', async (req) => {\n"
        '    const id = me(req); const row = getOwned(db, (req.params as any).id, id.userId);\n'
        '    const body = z.object({ is_favorite: z.boolean().optional(), folder_id: z.string().max(60).nullable().optional(),\n'
        '      var_values: z.record(z.string().max(60), z.string().max(2000)).optional(), tags: z.array(z.string().trim().min(1).max(30)).max(8).optional() }).parse(req.body);\n'
        '    if (body.folder_id) ownFolder(db, body.folder_id, id.userId);\n'
        '    db.tx(() => {\n'
        "      if (body.is_favorite !== undefined) db.run('UPDATE optimizations SET is_favorite = ?, favorited_at = ? WHERE id = ?', body.is_favorite ? 1 : 0, body.is_favorite ? nowIso() : null, row.id);\n"
        "      if (body.folder_id !== undefined) db.run('UPDATE optimizations SET folder_id = ? WHERE id = ?', body.folder_id, row.id);\n"
        "      if (body.var_values) db.run('UPDATE optimizations SET var_values = ? WHERE id = ?', JSON.stringify(body.var_values), row.id);\n"
        "      if (body.tags) db.run('UPDATE optimizations SET tags = ? WHERE id = ?', JSON.stringify([...new Set(body.tags)]), row.id);\n"
        "      db.run('UPDATE optimizations SET updated_at = ? WHERE id = ?', nowIso(), row.id);\n"
        '    });\n'
        "    const next = db.get('SELECT * FROM optimizations WHERE id = ?', row.id)!;\n"
        '    if (body.tags) reindex(db, next);\n'
        '    return rowToOptimization(next);\n'
        '  });\n'
        "  app.delete('/api/optimizer/items/:id', async (req) => {\n"
        '    const id = me(req); const row = getOwned(db, (req.params as any).id, id.userId);\n'
        "    db.run('DELETE FROM optimizations WHERE id = ?', row.id); unindexDoc(db, 'opt', row.id);\n"
        '    return { ok: true };\n'
        '  });\n'
        '\n'
        '  // ---- folders ----\n'
        "  app.get('/api/optimizer/folders', async (req) => ({ items: listFolders(db, me(req).userId) }));\n"
        "  app.post('/api/optimizer/folders', async (req) => createFolder(db, me(req).userId, z.object({ name: z.string().max(OPT_LIMITS.folderName * 2) }).parse(req.body).name));\n"
        "  app.patch('/api/optimizer/folders/:id', async (req) => {\n"
        '    const id = me(req); const f = ownFolder(db, (req.params as any).id, id.userId);\n'
        "    if (f.default_key) throw new AppError(409, 'folder_protected', 'Стандартную папку нельзя переименовать');\n"
        '    const name = z.object({ name: z.string().trim().min(1).max(OPT_LIMITS.folderName) }).parse(req.body).name;\n'
        "    if (db.get('SELECT 1 FROM folders WHERE user_id = ? AND name = ? AND id <> ?', id.userId, name, f.id)) throw new AppError(409, 'folder_exists', 'Папка с таким названием уже есть');\n"
        "    db.run('UPDATE folders SET name = ? WHERE id = ?', name, f.id);\n"
        '    return listFolders(db, id.userId).find((x) => x.id === f.id);\n'
        '  });\n'
        "  app.delete('/api/optimizer/folders/:id', async (req) => {\n"
        '    const id = me(req); const f = ownFolder(db, (req.params as any).id, id.userId);\n'
        "    if (f.default_key) throw new AppError(409, 'folder_protected', 'Стандартную папку нельзя удалить');\n"
        "    db.tx(() => { db.run('UPDATE optimizations SET folder_id = NULL WHERE user_id = ? AND folder_id = ?', id.userId, f.id); db.run('DELETE FROM folders WHERE id = ?', f.id); });\n"
        '    return { ok: true };\n'
        '  });\n'
      ), (
        '  // ---- engine settings (read for everyone, write for admins; the key is never returned) ----\n'
        "  app.get('/api/optimizer/engine', async () => engineView(db));\n"
        "  app.put('/api/optimizer/engine', async (req) => { admin(req); return updateEngine(db, engineUpdateSchema.parse(req.body)); });\n"
        "  app.post('/api/optimizer/engine/test', async (req) => {\n"
        '    const identity = admin(req);\n'
        '    limit(identity.userId);\n'
        '    const t0 = Date.now();\n'
        "    const r = await engineChat(db, deps, [{ role: 'user', content: 'Reply with the single word: ok' }], { maxTokens: 1024 });\n"
        '    return { ok: true, latency_ms: Date.now() - t0, provider: r.provider, model: r.model };\n'
        '  });\n'
        '\n'
        '  // ---- workflows ----\n'
        "  app.post('/api/optimizer/run', async (req) => { const id = me(req); limit(id.userId); return runOptimization(db, { userId: id.userId, deps }, optimizeRequestSchema.parse(req.body)); });\n"
        "  app.post('/api/optimizer/items/:id/answer', async (req) => { const id = me(req); limit(id.userId); return answerOptimization(db, { userId: id.userId, deps }, paramsSchema.parse(req.params).id, answerRequestSchema.parse(req.body)); });\n"
        "  app.post('/api/optimizer/items/:id/compress', async (req) => { const id = me(req); limit(id.userId); return compressOptimization(db, { userId: id.userId, deps }, paramsSchema.parse(req.params).id); });\n"
        '\n'
        '  // ---- library ----\n'
        "  app.get('/api/optimizer/items', async (req) => {\n"
        '    const id = me(req);\n'
        '    const q = z.object({ page: z.coerce.number().int().min(1).default(1), q: z.string().max(200).optional(), folder: z.string().max(60).optional(),\n'
        "      favorites: z.enum(['0', '1']).optional(), workflow: z.enum(OPT_WORKFLOWS).optional() }).parse(req.query);\n"
        "    return listOptimizations(db, id.userId, { q: q.q, folder: q.folder, favorites: q.favorites === '1', workflow: q.workflow, page: q.page });\n"
        '  });\n'
        "  app.get('/api/optimizer/items/:id', async (req) => rowToOptimization(getOwned(db, paramsSchema.parse(req.params).id, me(req).userId)));\n"
        "  app.patch('/api/optimizer/items/:id', async (req) => {\n"
        '    const id = me(req); const row = getOwned(db, paramsSchema.parse(req.params).id, id.userId);\n'
        '    const body = z.object({ is_favorite: z.boolean().optional(), folder_id: z.string().max(60).nullable().optional(),\n'
        '      var_values: z.record(z.string().max(60), z.string().max(OPT_LIMITS.variableValue)).optional(), tags: z.array(z.string().trim().min(1).max(30)).max(8).optional() }).parse(req.body);\n'
        '    if (body.folder_id != null) ownFolder(db, body.folder_id, id.userId);\n'
        '    return db.tx(() => {\n'
        "      if (body.is_favorite !== undefined) db.run('UPDATE optimizations SET is_favorite = ?, favorited_at = ? WHERE id = ?', body.is_favorite ? 1 : 0, body.is_favorite ? nowIso() : null, row.id);\n"
        "      if (body.folder_id !== undefined) db.run('UPDATE optimizations SET folder_id = ? WHERE id = ?', body.folder_id, row.id);\n"
        "      if (body.var_values) db.run('UPDATE optimizations SET var_values = ? WHERE id = ?', JSON.stringify(body.var_values), row.id);\n"
        "      if (body.tags) db.run('UPDATE optimizations SET tags = ? WHERE id = ?', JSON.stringify([...new Set(body.tags)]), row.id);\n"
        "      db.run('UPDATE optimizations SET updated_at = ? WHERE id = ?', nowIso(), row.id);\n"
        '      const next = getOwned(db, row.id, id.userId);\n'
        '      if (body.tags) reindex(db, next);\n'
        '      return rowToOptimization(next);\n'
        '    });\n'
        '  });\n'
        "  app.delete('/api/optimizer/items/:id', async (req) => {\n"
        '    const id = me(req); const row = getOwned(db, paramsSchema.parse(req.params).id, id.userId);\n'
        '    db.tx(() => {\n'
        "      db.run('DELETE FROM optimizations WHERE id = ?', row.id);\n"
        "      unindexDoc(db, 'opt', row.id);\n"
        '    });\n'
        '    return { ok: true };\n'
        '  });\n'
        '\n'
        '  // ---- folders ----\n'
        "  app.get('/api/optimizer/folders', async (req) => ({ items: listFolders(db, me(req).userId) }));\n"
        "  app.post('/api/optimizer/folders', async (req) => createFolder(db, me(req).userId, z.object({ name: z.string().max(OPT_LIMITS.folderName * 2) }).parse(req.body).name));\n"
        "  app.patch('/api/optimizer/folders/:id', async (req) => {\n"
        '    const id = me(req); const f = ownFolder(db, paramsSchema.parse(req.params).id, id.userId);\n'
        "    if (f.default_key) throw new AppError(409, 'folder_protected', 'Стандартную папку нельзя переименовать');\n"
        '    const name = z.object({ name: z.string().trim().min(1).max(OPT_LIMITS.folderName) }).parse(req.body).name;\n'
        "    if (db.get('SELECT 1 FROM folders WHERE user_id = ? AND name = ? AND id <> ?', id.userId, name, f.id)) throw new AppError(409, 'folder_exists', 'Папка с таким названием уже есть');\n"
        "    db.run('UPDATE folders SET name = ? WHERE id = ?', name, f.id);\n"
        '    return listFolders(db, id.userId).find((x) => x.id === f.id);\n'
        '  });\n'
        "  app.delete('/api/optimizer/folders/:id', async (req) => {\n"
        '    const id = me(req); const f = ownFolder(db, paramsSchema.parse(req.params).id, id.userId);\n'
        "    if (f.default_key) throw new AppError(409, 'folder_protected', 'Стандартную папку нельзя удалить');\n"
        "    db.tx(() => { db.run('UPDATE optimizations SET folder_id = NULL WHERE user_id = ? AND folder_id = ?', id.userId, f.id); db.run('DELETE FROM folders WHERE id = ?', f.id); });\n"
        '    return { ok: true };\n'
        '  });\n'
      )),
    ),
    'apps/server/src/optimizer.ts': (
      ((
        "import type { Db } from './db.ts';\n"
        "import { indexDoc, unindexDoc, searchDocs } from './db.ts';\n"
        "import { AppError, jsonParse, nowIso, uid } from './util.ts';\n"
        "import { engineJson, getEngineConfig, type EngineDeps } from './engine.ts';\n"
        'import {\n'
        '  BRIDGE_CONSTRAINT, DEFAULT_FOLDERS, OPT_LIMITS, clarifierOutputSchema, compressOutputSchema, estimateTokens, extractBracketVars, frameworkOf,\n'
        '  optimizerOutputSchema, type FolderDTO, type OptPreset, type OptWorkflow, type OptimizationDTO, type OptimizeRequest,\n'
        "} from '../../../shared/src/index.ts';\n"
        '\n'
        'type Row = Record<string, any>;\n'
      ), (
        "import type { Db } from './db.ts';\n"
        "import { acquireLock, indexDoc, releaseLock, searchDocs, unindexDoc } from './db.ts';\n"
        "import { AppError, jsonParse, nowIso, uid } from './util.ts';\n"
        "import { engineJson, type EngineDeps } from './engine.ts';\n"
        'import {\n'
        '  BRIDGE_CONSTRAINT, DEFAULT_FOLDERS, OPT_LIMITS, clarifierOutputSchema, compressOutputSchema, estimateTokens, extractBracketVars,\n'
        '  optimizerOutputSchema, type FolderDTO, type OptPreset, type OptWorkflow, type OptimizationDTO, type OptimizeRequest,\n'
        "} from '../../../shared/src/index.ts';\n"
        '\n'
        'type Row = Record<string, any>;\n'
      )),
      ((
        '  if (!bridge) return prompt;\n'
        "  const cleaned = prompt.split('\\n').filter((l) => !/CRITICAL INSTRUCTION:\\s*Perform all internal reasoning/i.test(l)).join('\\n').trimEnd();\n"
        '  return `${cleaned}\\n\\n${BRIDGE_CONSTRAINT}`;\n'
        '}\n'
        "export function varsFor(workflow: OptWorkflow, prompt: string): string[] { return workflow === 'template' || workflow === 'reverse' ? extractBracketVars(prompt) : []; }\n"
        '\n'
        '// ---------- persistence ----------\n'
        'export function rowToOptimization(r: Row): OptimizationDTO {\n'
        "  const options = jsonParse<Record<string, any>>(r.options, {}); const prompt = String(r.final_prompt ?? '');\n"
      ), (
        '  if (!bridge) return prompt;\n'
        "  const cleaned = prompt.split('\\n').filter((l) => !/CRITICAL INSTRUCTION:\\s*Perform all internal reasoning/i.test(l)).join('\\n').trimEnd();\n"
        '  return `${cleaned}\\n\\n${BRIDGE_CONSTRAINT}`;\n'
        '}\n'
        "function varsFor(workflow: OptWorkflow, prompt: string): string[] { return workflow === 'template' || workflow === 'reverse' ? extractBracketVars(prompt) : []; }\n"
        '\n'
        '// ---------- persistence ----------\n'
        'export function rowToOptimization(r: Row): OptimizationDTO {\n'
        "  const options = jsonParse<Record<string, any>>(r.options, {}); const prompt = String(r.final_prompt ?? '');\n"
      )),
      ((
        '  const extra = db.all<{ id: string }>(`SELECT id FROM optimizations WHERE user_id = ? AND deleted_at IS NULL AND is_favorite = 0 AND folder_id IS NULL ORDER BY created_at DESC LIMIT -1 OFFSET ?`, userId, RETENTION_CAP);\n'
        "  for (const e of extra) { db.run('DELETE FROM optimizations WHERE id = ?', e.id); unindexDoc(db, 'opt', e.id); }\n"
        '}\n'
        '\n'
        'export function ensureDefaultFolders(db: Db, userId: string): void {\n'
        "  const have = new Set(db.all<{ default_key: string }>('SELECT default_key FROM folders WHERE user_id = ? AND default_key IS NOT NULL', userId).map((r) => r.default_key));\n"
        "  for (const f of DEFAULT_FOLDERS) if (!have.has(f.key)) db.run('INSERT OR IGNORE INTO folders(id, user_id, name, default_key, created_at) VALUES(?,?,?,?,?)', uid(), userId, f.name, f.key, nowIso());\n"
        '}\n'
        'export function listFolders(db: Db, userId: string): FolderDTO[] {\n'
      ), (
        '  const extra = db.all<{ id: string }>(`SELECT id FROM optimizations WHERE user_id = ? AND deleted_at IS NULL AND is_favorite = 0 AND folder_id IS NULL ORDER BY created_at DESC LIMIT -1 OFFSET ?`, userId, RETENTION_CAP);\n'
        "  for (const e of extra) { db.run('DELETE FROM optimizations WHERE id = ?', e.id); unindexDoc(db, 'opt', e.id); }\n"
        '}\n'
        '\n'
        'function ensureDefaultFolders(db: Db, userId: string): void {\n'
        "  const have = new Set(db.all<{ default_key: string }>('SELECT default_key FROM folders WHERE user_id = ? AND default_key IS NOT NULL', userId).map((r) => r.default_key));\n"
        "  for (const f of DEFAULT_FOLDERS) if (!have.has(f.key)) db.run('INSERT OR IGNORE INTO folders(id, user_id, name, default_key, created_at) VALUES(?,?,?,?,?)', uid(), userId, f.name, f.key, nowIso());\n"
        '}\n'
        'export function listFolders(db: Db, userId: string): FolderDTO[] {\n'
      )),
      ((
        '}\n'
        '\n'
        '// ---------- workflows ----------\n'
        'interface Meta { userId: string; deps: EngineDeps }\n'
        'function insertRow(db: Db, userId: string, req: OptimizeRequest, status: string, extra: Row = {}): string {\n'
        '  const id = uid(); const now = nowIso();\n'
        '  const { raw_input, workflow, ...options } = req;\n'
        '  db.run(`INSERT INTO optimizations(id, user_id, workflow, status, raw_input, options, questions, created_at, updated_at) VALUES(?,?,?,?,?,?,?,?,?)`,\n'
        '    id, userId, workflow, status, raw_input, JSON.stringify(options), JSON.stringify(extra.questions ?? []), now, now);\n'
        '  return id;\n'
        '}\n'
        'async function optimizeInto(db: Db, m: Meta, id: string, req: OptimizeRequest, answers?: { q: string; a: string }[], auto?: boolean): Promise<void> {\n'
        '  const r = await engineJson(db, m.deps, buildOptimizeMessages({ req, answers, auto }), optimizerOutputSchema, { maxTokens: 4500 });\n'
        '  const finalPrompt = applyBridge(r.data.final_prompt, req.bridge);\n'
        "  db.run(`UPDATE optimizations SET status = 'ok', answers = ?, initial_score = ?, initial_critique = ?, optimized_score = ?, changelog = ?, final_prompt = ?, framework_used = ?,\n"
        '    provider = ?, model = ?, tokens_used = ?, updated_at = ? WHERE id = ?`,\n'
        '    JSON.stringify((answers ?? []).map((x) => x.a)), r.data.initial_score, r.data.initial_critique, r.data.optimized_score, JSON.stringify(r.data.changelog_explanation),\n'
        '    finalPrompt, r.data.framework_used, r.provider, r.model, r.tokens, nowIso(), id);\n'
        "  reindex(db, db.get('SELECT * FROM optimizations WHERE id = ?', id)!);\n"
        '  applyRetention(db, m.userId);\n'
        '}\n'
        'export async function runOptimization(db: Db, m: Meta, req: OptimizeRequest): Promise<OptimizationDTO> {\n'
        "  if (req.workflow === 'clarify') {\n"
        '    const q = await engineJson(db, m.deps, buildClarifyMessages(req), clarifierOutputSchema, { maxTokens: 800 });\n'
        '    const questions = q.data.clarifying_questions.slice(0, OPT_LIMITS.questions);\n'
        "    const id = insertRow(db, m.userId, req, 'draft_questions', { questions });\n"
        "    db.run('UPDATE optimizations SET provider = ?, model = ?, tokens_used = ? WHERE id = ?', q.provider, q.model, q.tokens, id);\n"
        '    return rowToOptimization(getOwned(db, id, m.userId));\n'
        '  }\n'
        "  const id = insertRow(db, m.userId, req, 'running');\n"
        "  try { await optimizeInto(db, m, id, req); } catch (e) { db.run('DELETE FROM optimizations WHERE id = ?', id); throw e; }\n"
        '  return rowToOptimization(getOwned(db, id, m.userId));\n'
        '}\n'
        'export async function answerOptimization(db: Db, m: Meta, id: string, body: { answers: string[]; auto: boolean }): Promise<OptimizationDTO> {\n'
        '  const row = getOwned(db, id, m.userId);\n'
        "  if (row.status !== 'draft_questions') throw new AppError(409, 'not_awaiting_answers', 'Эта запись уже обработана');\n"
        '  const opts = jsonParse<Record<string, any>>(row.options, {}); const questions = jsonParse<string[]>(row.questions, []);\n'
        "  const req: OptimizeRequest = { workflow: row.workflow, raw_input: row.raw_input, preset: opts.preset ?? 'auto', output_format: opts.output_format ?? 'none', tone: opts.tone ?? 'none', bridge: !!opts.bridge };\n"
        "  const answered = questions.map((q, i) => ({ q, a: (body.answers[i] ?? '').trim() })).filter((x) => x.a);\n"
        '  const auto = body.auto || answered.length === 0;\n'
        "  await optimizeInto(db, m, id, req, questions.map((q, i) => ({ q, a: (body.answers[i] ?? '').trim() })).filter((x) => x.a), auto);\n"
        '  return rowToOptimization(getOwned(db, id, m.userId));\n'
        '}\n'
        'export async function compressOptimization(db: Db, m: Meta, id: string): Promise<OptimizationDTO & { no_gain: boolean; saved_pct: number }> {\n'
        '  const row = getOwned(db, id, m.userId);\n'
        "  if (row.status !== 'ok' || !row.final_prompt) throw new AppError(409, 'nothing_to_compress', 'Сначала сформируйте промпт');\n"
        '  const opts = jsonParse<Record<string, any>>(row.options, {}); const bridge = !!opts.bridge;\n'
        '  const original = String(row.final_prompt); const before = estimateTokens(original);\n'
        '  const r = await engineJson(db, m.deps, buildCompressMessages(original), compressOutputSchema, { maxTokens: 4500 });\n'
        '  const candidate = applyBridge(r.data.compressed_prompt, bridge);\n'
        '  const origVars = varsFor(row.workflow, original); const keepsVars = origVars.every((v) => candidate.includes(`[${v}]`));\n'
        '  const after = estimateTokens(candidate);\n'
        '  const ok = keepsVars && after < before;\n'
        "  db.run('UPDATE optimizations SET compressed_prompt = ?, tokens_before = ?, tokens_after = ?, tokens_used = tokens_used + ?, updated_at = ? WHERE id = ?',\n"
        '    ok ? candidate : null, before, ok ? after : before, r.tokens, nowIso(), id);\n'
        '  const dto = rowToOptimization(getOwned(db, id, m.userId));\n'
        '  return { ...dto, no_gain: !ok, saved_pct: ok ? Math.round(((before - after) / before) * 100) : 0 };\n'
        '}\n'
        '\n'
        '// ---------- library queries ----------\n'
        'export function listOptimizations(db: Db, userId: string, q: { q?: string; folder?: string; favorites?: boolean; workflow?: string; page: number }): { items: Row[]; total: number; page: number } {\n'
      ), (
        '}\n'
        '\n'
        '// ---------- workflows ----------\n'
        'interface Meta { userId: string; deps: EngineDeps }\n'
        "function insertRow(db: Db, userId: string, req: OptimizeRequest, status: OptimizationDTO['status'], questions: string[] = []): string {\n"
        '  const id = uid(); const now = nowIso();\n'
        '  const { raw_input, workflow, ...options } = req;\n'
        '  db.run(`INSERT INTO optimizations(id, user_id, workflow, status, raw_input, options, questions, created_at, updated_at) VALUES(?,?,?,?,?,?,?,?,?)`,\n'
        '    id, userId, workflow, status, raw_input, JSON.stringify(options), JSON.stringify(questions), now, now);\n'
        '  return id;\n'
        '}\n'
        'const ITEM_LEASE_MS = 10 * 60_000;\n'
        '\n'
        'async function withItemLease<T>(db: Db, id: string, run: () => Promise<T>): Promise<T> {\n'
        '  const name = `optimizer:${id}`;\n'
        '  const holder = uid();\n'
        '  if (!acquireLock(db, name, holder, ITEM_LEASE_MS)) {\n'
        "    throw new AppError(409, 'optimization_busy', 'Эта запись уже обрабатывается');\n"
        '  }\n'
        '  try {\n'
        '    return await run();\n'
        '  } finally {\n'
        '    releaseLock(db, name, holder);\n'
        '  }\n'
        '}\n'
        '\n'
        'const optimize = (db: Db, deps: EngineDeps, ctx: BuildCtx) =>\n'
        '  engineJson(db, deps, buildOptimizeMessages(ctx), optimizerOutputSchema, { maxTokens: 4500 });\n'
        '\n'
        'function saveOptimization(db: Db, userId: string, id: string, ctx: BuildCtx, result: Awaited<ReturnType<typeof optimize>>): OptimizationDTO {\n'
        '  const { data } = result;\n'
        "  db.run(`UPDATE optimizations SET status = 'ok', answers = ?, initial_score = ?, initial_critique = ?, optimized_score = ?, changelog = ?,\n"
        '    final_prompt = ?, framework_used = ?, provider = ?, model = ?, tokens_used = tokens_used + ?, updated_at = ? WHERE id = ?`,\n'
        '    JSON.stringify((ctx.answers ?? []).map(({ a }) => a)), data.initial_score, data.initial_critique, data.optimized_score,\n'
        '    JSON.stringify(data.changelog_explanation), applyBridge(data.final_prompt, ctx.req.bridge), data.framework_used,\n'
        '    result.provider, result.model, result.tokens, nowIso(), id);\n'
        '  const row = getOwned(db, id, userId);\n'
        '  reindex(db, row);\n'
        '  applyRetention(db, userId);\n'
        '  return rowToOptimization(row);\n'
        '}\n'
        '\n'
        'export async function runOptimization(db: Db, m: Meta, req: OptimizeRequest): Promise<OptimizationDTO> {\n'
        "  if (req.workflow === 'clarify') {\n"
        '    const q = await engineJson(db, m.deps, buildClarifyMessages(req), clarifierOutputSchema, { maxTokens: 800 });\n'
        '    const questions = q.data.clarifying_questions.slice(0, OPT_LIMITS.questions);\n'
        '    return db.tx(() => {\n'
        "      const id = insertRow(db, m.userId, req, 'draft_questions', questions);\n"
        "      db.run('UPDATE optimizations SET provider = ?, model = ?, tokens_used = ? WHERE id = ?', q.provider, q.model, q.tokens, id);\n"
        '      return rowToOptimization(getOwned(db, id, m.userId));\n'
        '    });\n'
        '  }\n'
        '  const ctx = { req };\n'
        '  const result = await optimize(db, m.deps, ctx);\n'
        '  return db.tx(() => {\n'
        "    const id = insertRow(db, m.userId, req, 'ok');\n"
        '    return saveOptimization(db, m.userId, id, ctx, result);\n'
        '  });\n'
        '}\n'
        '\n'
        'export async function answerOptimization(db: Db, m: Meta, id: string, body: { answers: string[]; auto: boolean }): Promise<OptimizationDTO> {\n'
        '  getOwned(db, id, m.userId);\n'
        '  return withItemLease(db, id, async () => {\n'
        '    const row = getOwned(db, id, m.userId);\n'
        "    if (row.status !== 'draft_questions') throw new AppError(409, 'not_awaiting_answers', 'Эта запись уже обработана');\n"
        '    const item = rowToOptimization(row);\n'
        '    const req = { ...item.options, workflow: item.workflow, raw_input: item.raw_input };\n'
        "    const answers = body.auto ? [] : item.clarifying_questions.map((q, i) => ({ q, a: (body.answers[i] ?? '').trim() }));\n"
        '    const ctx = { req, answers, auto: !answers.some(({ a }) => a) };\n'
        '    const result = await optimize(db, m.deps, ctx);\n'
        '    return db.tx(() => {\n'
        '      getOwned(db, id, m.userId);\n'
        '      return saveOptimization(db, m.userId, id, ctx, result);\n'
        '    });\n'
        '  });\n'
        '}\n'
        '\n'
        'export async function compressOptimization(db: Db, m: Meta, id: string): Promise<OptimizationDTO & { no_gain: boolean; saved_pct: number }> {\n'
        '  getOwned(db, id, m.userId);\n'
        '  return withItemLease(db, id, async () => {\n'
        '    const item = rowToOptimization(getOwned(db, id, m.userId));\n'
        "    if (item.status !== 'ok' || !item.final_prompt) {\n"
        "      throw new AppError(409, 'nothing_to_compress', 'Сначала сформируйте промпт');\n"
        '    }\n'
        '    const before = estimateTokens(item.final_prompt);\n'
        '    const best = item.compressed_prompt ? estimateTokens(item.compressed_prompt) : before;\n'
        '    const result = await engineJson(db, m.deps, buildCompressMessages(item.final_prompt), compressOutputSchema, { maxTokens: 4500 });\n'
        '    const candidate = applyBridge(result.data.compressed_prompt, item.options.bridge);\n'
        '    const after = estimateTokens(candidate);\n'
        '    const candidateVars = varsFor(item.workflow, candidate);\n'
        '    const sameVars = candidateVars.length === item.variables.length && item.variables.every((v) => candidateVars.includes(v));\n'
        '    const improved = sameVars && after < best;\n'
        '    if (improved) {\n'
        "      db.run('UPDATE optimizations SET compressed_prompt = ?, tokens_before = ?, tokens_after = ?, tokens_used = tokens_used + ?, updated_at = ? WHERE id = ?',\n"
        '        candidate, before, after, result.tokens, nowIso(), id);\n'
        '    } else {\n'
        "      db.run('UPDATE optimizations SET tokens_used = tokens_used + ? WHERE id = ?', result.tokens, id);\n"
        '    }\n'
        '    const dto = rowToOptimization(getOwned(db, id, m.userId));\n'
        '    return { ...dto, no_gain: !improved, saved_pct: improved ? Math.round((before - after) / before * 100) : 0 };\n'
        '  });\n'
        '}\n'
        '\n'
        '// ---------- library queries ----------\n'
        'export function listOptimizations(db: Db, userId: string, q: { q?: string; folder?: string; favorites?: boolean; workflow?: string; page: number }): { items: Row[]; total: number; page: number } {\n'
      )),
      ((
        '  const rows = db.all(`SELECT * FROM optimizations WHERE ${w} ORDER BY created_at DESC LIMIT 20 OFFSET ?`, ...params, (q.page - 1) * 20);\n'
        '  return { items: rows.map((r) => { const d = rowToOptimization(r); return { id: d.id, workflow: d.workflow, status: d.status, preview: d.raw_input.slice(0, 140), prompt_preview: d.final_prompt.slice(0, 200),\n'
        '    initial_score: d.initial_score, optimized_score: d.optimized_score, is_favorite: d.is_favorite, folder_id: d.folder_id, tags: d.tags, created_at: d.created_at, has_variables: d.variables.length > 0 }; }), total, page: q.page };\n'
        '}\n'
        'export { getEngineConfig, frameworkOf };\n'
      ), (
        '  const rows = db.all(`SELECT * FROM optimizations WHERE ${w} ORDER BY created_at DESC LIMIT 20 OFFSET ?`, ...params, (q.page - 1) * 20);\n'
        '  return { items: rows.map((r) => { const d = rowToOptimization(r); return { id: d.id, workflow: d.workflow, status: d.status, preview: d.raw_input.slice(0, 140), prompt_preview: d.final_prompt.slice(0, 200),\n'
        '    initial_score: d.initial_score, optimized_score: d.optimized_score, is_favorite: d.is_favorite, folder_id: d.folder_id, tags: d.tags, created_at: d.created_at, has_variables: d.variables.length > 0 }; }), total, page: q.page };\n'
        '}\n'
      )),
    ),
    'apps/server/src/refresh.ts': (
      ((
        "} from '../../../shared/src/index.ts';\n"
        "import { type Db, type Row, getSettings, setSettings, acquireLock, releaseLock } from './db.ts';\n"
        "import { VibeError, type VibeClient, type SearchResult, type ChatMessage } from './vibe.ts';\n"
        "import { getCurrentVersion, validateSkillDraft, rowToVersion, type SkillVersion } from './skills.ts';\n"
        "import { buildTransformerSystem, buildTransformerUser, extractJson } from './generation.ts';\n"
        "import { computeNextCheck, computeRetry, dueSkills, MUTEX_NAME, MUTEX_TTL_MS, HARD_CAP_PER_DISPATCH, MIN_PAUSE_BETWEEN_RUNS_MS } from './scheduler.ts';\n"
        "import { uid, nowIso, jsonParse, sleep, randBetween, DAY_MS, log } from './util.ts';\n"
        "import { config } from './config.ts';\n"
        "import { TIMEOUTS } from './vibe.ts';\n"
        '\n'
        'export const WHITELIST: Record<SystemId, string[]> = {\n'
      ), (
        "} from '../../../shared/src/index.ts';\n"
        "import { type Db, type Row, getSettings, setSettings, acquireLock, releaseLock } from './db.ts';\n"
        "import { VibeError, type VibeClient, type SearchResult, type ChatMessage } from './vibe.ts';\n"
        "import { getCurrentVersion, validateSkillDraft, rowToVersion, type SkillVersion } from './skills.ts';\n"
        "import { buildTransformerSystem, buildTransformerUser } from './generation.ts';\n"
        "import { computeNextCheck, computeRetry, dueSkills, MUTEX_NAME, MUTEX_TTL_MS, HARD_CAP_PER_DISPATCH, MIN_PAUSE_BETWEEN_RUNS_MS } from './scheduler.ts';\n"
        "import { uid, nowIso, jsonParse, sleep, randBetween, DAY_MS, log, extractJson } from './util.ts';\n"
        "import { config } from './config.ts';\n"
        "import { TIMEOUTS } from './vibe.ts';\n"
        '\n'
        'export const WHITELIST: Record<SystemId, string[]> = {\n'
      )),
    ),
    'apps/server/src/routes.ts': (
      ((
        "import { type Db, type Row, getSettings, setSettings, indexDoc, unindexDoc, searchDocs } from './db.ts';\n"
        "import { VibeError, type VibeClient } from './vibe.ts';\n"
        "import { resolveIdentity, rateLimit, type Identity } from './auth.ts';\n"
        "import { registerOptimizerRoutes } from './optimizer-routes.ts';\n"
        "import { AppError, uid, nowIso, jsonParse, log } from './util.ts';\n"
        "import { runGeneration, regenerateResult, rowToGeneration, rowToResult, extractJson, type GenEvent } from './generation.ts';\n"
        "import { getCurrentVersion, listVersions, skillToDto, rowToVersion, getVersionById } from './skills.ts';\n"
        "import { runManual, isRefreshBusy, type RefreshDeps } from './refresh.ts';\n"
        "import { acceptRun, verifyWithAnySecret, singleHeader, parseJobPayload, processJobRun, maybeLazyCheck, getJobSecrets } from './jobs.ts';\n"
        '\n'
      ), (
        "import { type Db, type Row, getSettings, setSettings, indexDoc, unindexDoc, searchDocs } from './db.ts';\n"
        "import { VibeError, type VibeClient } from './vibe.ts';\n"
        "import { resolveIdentity, rateLimit, type Identity } from './auth.ts';\n"
        "import { registerOptimizerRoutes } from './optimizer-routes.ts';\n"
        "import { AppError, uid, nowIso, jsonParse, log, extractJson } from './util.ts';\n"
        "import { runGeneration, regenerateResult, rowToGeneration, rowToResult, type GenEvent } from './generation.ts';\n"
        "import { getCurrentVersion, listVersions, skillToDto, rowToVersion, getVersionById } from './skills.ts';\n"
        "import { runManual, isRefreshBusy, type RefreshDeps } from './refresh.ts';\n"
        "import { acceptRun, verifyWithAnySecret, singleHeader, parseJobPayload, processJobRun, maybeLazyCheck, getJobSecrets } from './jobs.ts';\n"
        '\n'
      )),
      ((
        '  });\n'
        '\n'
        "  app.addHook('onSend', async (_req, reply, payload) => {\n"
        "    reply.header('X-Content-Type-Options', 'nosniff');\n"
        "    reply.header('Content-Security-Policy', `default-src 'self'; img-src 'self' data:; font-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; frame-ancestors ${FRAME_ANCESTORS}`);\n"
        "    reply.header('Referrer-Policy', 'no-referrer');\n"
        '    return payload;\n'
        '  });\n'
      ), (
        '  });\n'
        '\n'
        "  app.addHook('onSend', async (_req, reply, payload) => {\n"
        "    reply.header('X-Content-Type-Options', 'nosniff');\n"
        "    if (_req.url.startsWith('/api/')) reply.header('Cache-Control', 'no-store');\n"
        "    reply.header('Content-Security-Policy', `default-src 'self'; img-src 'self' data:; font-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; frame-ancestors ${FRAME_ANCESTORS}`);\n"
        "    reply.header('Referrer-Policy', 'no-referrer');\n"
        '    return payload;\n'
        '  });\n'
      )),
      ((
        '  const sysId = (v: unknown): SystemId => systemIdSchema.parse(v);\n'
        '  registerOptimizerRoutes(app, { db, vibe, me, admin });\n'
        '\n'
        '  // ---- SSE helper ----\n'
        '  function openSse(req: FastifyRequest, reply: FastifyReply, generationId?: string): { send: (e: GenEvent) => void; close: () => void } {\n'
        '    reply.hijack();\n'
        "    reply.raw.writeHead(200, { 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-cache, no-transform', Connection: 'keep-alive', 'X-Accel-Buffering': 'no', 'X-Content-Type-Options': 'nosniff', ...(generationId ? { 'X-Generation-Id': generationId } : {}) });\n"
        "    reply.raw.write(': open\\n\\n');\n"
        '    let closed = false;\n'
        "    const hb = setInterval(() => { if (!closed) reply.raw.write(': hb\\n\\n'); }, 10_000);\n"
        "    req.raw.on('close', () => { closed = true; clearInterval(hb); });\n"
        '    return {\n'
        '      send: (e) => { if (!closed) reply.raw.write(`event: ${e.type}\\ndata: ${JSON.stringify(e)}\\n\\n`); },\n'
        '      close: () => { clearInterval(hb); if (!closed) { closed = true; reply.raw.end(); } },\n'
        '    };\n'
      ), (
        '  const sysId = (v: unknown): SystemId => systemIdSchema.parse(v);\n'
        '  registerOptimizerRoutes(app, { db, vibe, me, admin });\n'
        '\n'
        '  // ---- SSE helper ----\n'
        '  function openSse(reply: FastifyReply, generationId?: string): { send: (e: GenEvent) => void; close: () => void } {\n'
        '    reply.hijack();\n'
        "    reply.raw.writeHead(200, { 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-cache, no-transform', Connection: 'keep-alive', 'X-Accel-Buffering': 'no', 'X-Content-Type-Options': 'nosniff', ...(generationId ? { 'X-Generation-Id': generationId } : {}) });\n"
        "    reply.raw.write(': open\\n\\n');\n"
        '    let closed = false;\n'
        "    const hb = setInterval(() => { if (!closed) reply.raw.write(': hb\\n\\n'); }, 10_000);\n"
        "    reply.raw.on('close', () => { closed = true; clearInterval(hb); });\n"
        '    return {\n'
        '      send: (e) => { if (!closed) reply.raw.write(`event: ${e.type}\\ndata: ${JSON.stringify(e)}\\n\\n`); },\n'
        '      close: () => { clearInterval(hb); if (!closed) { closed = true; reply.raw.end(); } },\n'
        '    };\n'
      )),
      ((
        '    const lim = rateLimit(`gen:${id.userId}`, 6, 60_000);\n'
        "    if (!lim.ok) throw new AppError(429, 'rate_limited', 'Не более 6 генераций в минуту', lim.retryAfter);\n"
        '    const body = generateRequestSchema.parse(req.body);\n'
        '    const newId = uid();\n'
        '    const sse = openSse(req, reply, newId);\n'
        '    try { await runGeneration({ db, userId: id.userId, req: body, newId, emit: sse.send, vibe, onQuota: pauseOnQuota }); }\n'
        "    catch (e) { sse.send({ type: 'card_error', system: body.systems[0]!, error: (e as Error).message.slice(0, 200) }); sse.send({ type: 'done', generation_id: '', status: 'failed' }); }\n"
        '    sse.close();\n'
        '  });\n'
      ), (
        '    const lim = rateLimit(`gen:${id.userId}`, 6, 60_000);\n'
        "    if (!lim.ok) throw new AppError(429, 'rate_limited', 'Не более 6 генераций в минуту', lim.retryAfter);\n"
        '    const body = generateRequestSchema.parse(req.body);\n'
        '    const newId = uid();\n'
        '    const sse = openSse(reply, newId);\n'
        '    try { await runGeneration({ db, userId: id.userId, req: body, newId, emit: sse.send, vibe, onQuota: pauseOnQuota }); }\n'
        "    catch (e) { sse.send({ type: 'card_error', system: body.systems[0]!, error: (e as Error).message.slice(0, 200) }); sse.send({ type: 'done', generation_id: '', status: 'failed' }); }\n"
        '    sse.close();\n'
        '  });\n'
      )),
      ((
        "    if (!lim.ok) throw new AppError(429, 'rate_limited', 'Не более 6 генераций в минуту', lim.retryAfter);\n"
        '    const { answers } = z.object({ answers: z.array(z.string().max(2000)).max(3) }).parse(req.body);\n'
        "    const g = db.get('SELECT * FROM generations WHERE id = ? AND user_id = ? AND deleted_at IS NULL', gid, id.userId);\n"
        "    if (!g) throw new AppError(404, 'not_found', 'Генерация не найдена');\n"
        '    const qs = jsonParse<string[]>(g.questions, []);\n'
        "    const extra = answers.map((a, i) => `Вопрос: ${qs[i] ?? ''}\\nОтвет: ${a}`).join('\\n');\n"
        '    const sse = openSse(req, reply, gid);\n'
        '    try {\n'
        '      await runGeneration({ db, userId: id.userId, extraAnswers: extra, emit: sse.send, vibe, onQuota: pauseOnQuota,\n'
        '        req: { raw_input: g.raw_input, systems: jsonParse(g.systems, []), language: g.language, options: optionsSchema.parse(jsonParse(g.options, {})), generation_id: gid } });\n'
        "    } catch { sse.send({ type: 'done', generation_id: gid, status: 'failed' }); }\n"
      ), (
        "    if (!lim.ok) throw new AppError(429, 'rate_limited', 'Не более 6 генераций в минуту', lim.retryAfter);\n"
        '    const { answers } = z.object({ answers: z.array(z.string().max(2000)).max(3) }).parse(req.body);\n'
        "    const g = db.get('SELECT * FROM generations WHERE id = ? AND user_id = ? AND deleted_at IS NULL', gid, id.userId);\n"
        "    if (!g) throw new AppError(404, 'not_found', 'Генерация не найдена');\n"
        "    if (g.status !== 'draft_questions') throw new AppError(409, 'not_awaiting_answers', 'Эта генерация уже обработана');\n"
        '    const qs = jsonParse<string[]>(g.questions, []);\n'
        "    const extra = answers.map((a, i) => `Вопрос: ${qs[i] ?? ''}\\nОтвет: ${a}`).join('\\n');\n"
        '    const sse = openSse(reply, gid);\n'
        '    try {\n'
        '      await runGeneration({ db, userId: id.userId, extraAnswers: extra, emit: sse.send, vibe, onQuota: pauseOnQuota,\n'
        '        req: { raw_input: g.raw_input, systems: jsonParse(g.systems, []), language: g.language, options: optionsSchema.parse(jsonParse(g.options, {})), generation_id: gid } });\n'
        "    } catch { sse.send({ type: 'done', generation_id: gid, status: 'failed' }); }\n"
      )),
    ),
    'apps/server/src/util.ts': (
      ((
        'export const uid = (): string => randomUUID();\n'
        'export const nowIso = (): string => new Date().toISOString();\n'
        'export const sleep = (ms: number): Promise<void> => new Promise((r) => setTimeout(r, ms));\n'
        'export const DAY_MS = 86_400_000;\n'
        'export const HOUR_MS = 3_600_000;\n'
        'export const jsonParse = <T>(s: string | null | undefined, fallback: T): T => {\n'
        "  if (s == null || s === '') return fallback;\n"
        '  try { return JSON.parse(s) as T; } catch { return fallback; }\n'
      ), (
        'export const uid = (): string => randomUUID();\n'
        'export const nowIso = (): string => new Date().toISOString();\n'
        'export const sleep = (ms: number): Promise<void> => new Promise((r) => setTimeout(r, ms));\n'
        'export const DAY_MS = 86_400_000;\n'
        'export function extractJson(text: string): unknown {\n'
        "  const t = text.trim().replace(/^```(?:json)?\\s*/i, '').replace(/\\s*```$/i, '');\n"
        '  try { return JSON.parse(t); } catch { /* try to locate object */ }\n'
        "  const s = t.indexOf('{'); const e = t.lastIndexOf('}');\n"
        '  if (s >= 0 && e > s) return JSON.parse(t.slice(s, e + 1));\n'
        "  throw new Error('No JSON object found');\n"
        '}\n'
        '\n'
        'export const HOUR_MS = 3_600_000;\n'
        'export const jsonParse = <T>(s: string | null | undefined, fallback: T): T => {\n'
        "  if (s == null || s === '') return fallback;\n"
        '  try { return JSON.parse(s) as T; } catch { return fallback; }\n'
      )),
    ),
    'apps/web/src/App.tsx': (
      ((
        "import { Component, useCallback, useEffect, useRef, useState, type ReactNode } from 'react';\n"
        "import { History, LayoutTemplate, Star, Cpu, ScrollText, Settings as Cog, Wand2, Plus, PanelLeftClose, PanelLeftOpen, BarChart3, Sparkles, Library, Sun, Moon, Monitor, MoreHorizontal } from 'lucide-react';\n"
        "import type { Settings } from '../../../shared/src/index.ts';\n"
        "import { t } from './strings.ru.ts';\n"
        "import { get, onWake, ApiError } from './api.ts';\n"
        "import { AppCtx, type AgentStatus, type Me, type Prefill, type Screen, type AppState } from './context.tsx';\n"
        "import { ToastProvider, Spinner, Modal } from './ui.tsx';\n"
      ), (
        "import { Component, useCallback, useEffect, useRef, useState, type ReactNode } from 'react';\n"
        "import { History, LayoutTemplate, Star, Cpu, ScrollText, Settings as Cog, Wand2, Plus, PanelLeftClose, PanelLeftOpen, BarChart3, Sparkles, Library, Sun, Moon, Monitor, MoreHorizontal } from 'lucide-react';\n"
        "import { settingsSchema, type Settings } from '../../../shared/src/index.ts';\n"
        "import { t } from './strings.ru.ts';\n"
        "import { get, onWake, ApiError } from './api.ts';\n"
        "import { AppCtx, type AgentStatus, type Me, type Prefill, type Screen, type AppState } from './context.tsx';\n"
        "import { ToastProvider, Spinner, Modal } from './ui.tsx';\n"
      )),
      ((
        "const ALL_SCREENS: Screen[] = ['generator', 'optimizer', 'library', 'history', 'favorites', 'templates', 'skills', 'reports', 'analytics', 'settings'];\n"
        "const parseHash = (): Screen => { const s = location.hash.replace('#/', '') as Screen; return ALL_SCREENS.includes(s) ? s : 'generator'; };\n"
        'const store = { get: (k: string) => { try { return localStorage.getItem(k); } catch { return null; } }, set: (k: string, v: string) => { try { localStorage.setItem(k, v); } catch { /* storage may be blocked in iframes */ } } };\n'
        '\n'
        'class Boundary extends Component<{ children: ReactNode }, { err: boolean }> {\n'
        '  state = { err: false };\n'
        '  static getDerivedStateFromError() { return { err: true }; }\n'
        '  render() {\n'
        '    if (!this.state.err) return this.props.children;\n'
        '    return <div className="empty glass" style={{ margin: \'var(--space-10)\' }}><h3>{t.boundary.title}</h3><button className="btn primary" style={{ marginTop: \'var(--space-4)\' }} onClick={() => this.setState({ err: false })}>{t.boundary.retry}</button></div>;\n'
        '  }\n'
        '}\n'
        '\n'
        'const Logo = () => <svg className="logo" viewBox="0 0 32 32" aria-hidden><path d="M16 2l12 7v14l-12 7L4 23V9z" fill="var(--color-accent)" /><path d="M16 9l1.8 4.6L22.5 15l-4.7 1.4L16 21l-1.8-4.6L9.5 15l4.7-1.4z" fill="var(--color-on-accent)" /></svg>;\n'
      ), (
        "const ALL_SCREENS: Screen[] = ['generator', 'optimizer', 'library', 'history', 'favorites', 'templates', 'skills', 'reports', 'analytics', 'settings'];\n"
        "const parseHash = (): Screen => { const s = location.hash.replace('#/', '') as Screen; return ALL_SCREENS.includes(s) ? s : 'generator'; };\n"
        'const store = { get: (k: string) => { try { return localStorage.getItem(k); } catch { return null; } }, set: (k: string, v: string) => { try { localStorage.setItem(k, v); } catch { /* storage may be blocked in iframes */ } } };\n'
        '\n'
        'const themeFromStorage = () => {\n'
        "  const theme = settingsSchema.shape.theme.safeParse(store.get('theme'));\n"
        '  return theme.success ? theme.data : undefined;\n'
        '};\n'
        'const embedded = window.parent !== window;\n'
        '\n'
        'class Boundary extends Component<{ children: ReactNode }, { err: boolean }> {\n'
        '  state = { err: false };\n'
        '  static getDerivedStateFromError() { return { err: true }; }\n'
        '  render() {\n'
        '    if (!this.state.err) return this.props.children;\n'
        '    return <div className="empty surface" style={{ margin: \'var(--space-10)\' }}><h3>{t.boundary.title}</h3><button className="btn primary" style={{ marginTop: \'var(--space-4)\' }} onClick={() => this.setState({ err: false })}>{t.boundary.retry}</button></div>;\n'
        '  }\n'
        '}\n'
        '\n'
        'const Logo = () => <svg className="logo" viewBox="0 0 32 32" aria-hidden><path d="M16 2l12 7v14l-12 7L4 23V9z" fill="var(--color-accent)" /><path d="M16 9l1.8 4.6L22.5 15l-4.7 1.4L16 21l-1.8-4.6L9.5 15l4.7-1.4z" fill="var(--color-on-accent)" /></svg>;\n'
      )),
      ((
        '\n'
        'export default function App() {\n'
        '  const [screen, setScreen] = useState<Screen>(parseHash);\n'
        '  const [me, setMe] = useState<Me | null>(null); const [settings, setSettingsState] = useState<Settings | null>(null); const [agent, setAgent] = useState<AgentStatus | null>(null);\n'
        "  const [authErr, setAuthErr] = useState(false); const [waking, setWaking] = useState(false); const [compact, setCompact] = useState(false); const [bodyW, setBodyW] = useState(1280); const [sidebarPref, setSidebarPref] = useState<'expanded' | 'collapsed' | null>(() => { const v = store.get('sidebar'); return v === 'expanded' || v === 'collapsed' ? v : null; }); const [moreOpen, setMoreOpen] = useState(false);\n"
        '  const [prefill, setPrefillState] = useState<Prefill | null>(null); const [openGenerationId, setOpenGenerationId] = useState<string | null>(null);\n'
        "  const [theme, setThemeState] = useState<'dark' | 'light' | 'system'>(() => (store.get('theme') as any) || 'dark');\n"
        '  const shellRef = useRef<HTMLDivElement>(null);\n'
        '\n'
        "  const go = useCallback((s: Screen) => { setScreen(s); setMoreOpen(false); try { history.replaceState(null, '', `#/${s}`); } catch { /* ignore */ } }, []);\n"
        '  const reload = useCallback(() => {\n'
      ), (
        '\n'
        'export default function App() {\n'
        '  const [screen, setScreen] = useState<Screen>(parseHash);\n'
        '  const [me, setMe] = useState<Me | null>(null); const [settings, setSettingsState] = useState<Settings | null>(null); const [agent, setAgent] = useState<AgentStatus | null>(null);\n'
        "  const [authErr, setAuthErr] = useState(false); const [waking, setWaking] = useState(false); const [bodyW, setBodyW] = useState(() => document.documentElement.clientWidth); const [sidebarPref, setSidebarPref] = useState<'expanded' | 'collapsed' | null>(() => { const v = store.get('sidebar'); return v === 'expanded' || v === 'collapsed' ? v : null; }); const [moreOpen, setMoreOpen] = useState(false);\n"
        '  const compact = bodyW < 800;\n'
        '  const [prefill, setPrefillState] = useState<Prefill | null>(null); const [openGenerationId, setOpenGenerationId] = useState<string | null>(null);\n'
        "  const [theme, setThemeState] = useState<'dark' | 'light' | 'system'>(() => themeFromStorage() ?? 'dark');\n"
        '  const shellRef = useRef<HTMLDivElement>(null);\n'
        '\n'
        "  const go = useCallback((s: Screen) => { setScreen(s); setMoreOpen(false); try { history.replaceState(null, '', `#/${s}`); } catch { /* ignore */ } }, []);\n"
        '  const reload = useCallback(() => {\n'
      )),
      ((
        "    get<AgentStatus>('/api/agent/status').then(setAgent).catch(() => {});\n"
        '  }, []);\n'
        "  useEffect(() => { reload(); const id = setInterval(() => get<AgentStatus>('/api/agent/status').then(setAgent).catch(() => {}), 60_000); return () => clearInterval(id); }, [reload]);\n"
        '  useEffect(() => onWake(setWaking), []);\n'
        '  useEffect(() => { const ro = new ResizeObserver(([e]) => { const w = e?.contentRect.width ?? 1000; setCompact(w < 800); setBodyW(w); }); ro.observe(document.body); return () => ro.disconnect(); }, []);\n'
        '  useEffect(() => { // theme\n'
        "    const apply = () => { const dark = theme === 'system' ? matchMedia('(prefers-color-scheme: dark)').matches : theme === 'dark'; document.documentElement.dataset.theme = dark ? 'dark' : 'light'; };\n"
        "    apply(); const mq = matchMedia('(prefers-color-scheme: dark)'); mq.addEventListener('change', apply); return () => mq.removeEventListener('change', apply);\n"
        '  }, [theme]);\n'
        "  useEffect(() => { if (settings && !store.get('theme')) setThemeState(settings.theme); }, [settings]);\n"
        "  useEffect(() => { // iframe auto-height contract: window.parent.postMessage({type:'vibe:resize', height})\n"
        '    const el = shellRef.current; if (!el) return;\n'
        "    const send = () => { try { window.parent?.postMessage({ type: 'vibe:resize', height: Math.ceil(Math.max(el.scrollHeight, el.offsetHeight)) + 8 }, '*'); } catch { /* ignore */ } };\n"
        '    const ro = new ResizeObserver(send); ro.observe(el); send(); return () => ro.disconnect();\n'
        '  });\n'
        '  const isAdmin = !!me?.is_admin; const meLoaded = me !== null;\n'
        "  useEffect(() => { const h = () => { const s = parseHash(); if (s === 'analytics' && !isAdmin) return; setScreen(s); }; window.addEventListener('hashchange', h); return () => window.removeEventListener('hashchange', h); }, [isAdmin]);\n"
        "  useEffect(() => { if (meLoaded && !isAdmin && screen === 'analytics') go('generator'); }, [meLoaded, isAdmin, screen, go]); // admin-only section: non-admins fall back to the generator\n"
        '\n'
      ), (
        "    get<AgentStatus>('/api/agent/status').then(setAgent).catch(() => {});\n"
        '  }, []);\n'
        "  useEffect(() => { reload(); const id = setInterval(() => get<AgentStatus>('/api/agent/status').then(setAgent).catch(() => {}), 60_000); return () => clearInterval(id); }, [reload]);\n"
        '  useEffect(() => onWake(setWaking), []);\n'
        '  useEffect(() => { const ro = new ResizeObserver(([e]) => { if (e) setBodyW(e.contentRect.width); }); ro.observe(document.body); return () => ro.disconnect(); }, []);\n'
        '  useEffect(() => { // theme\n'
        "    const apply = () => { const dark = theme === 'system' ? matchMedia('(prefers-color-scheme: dark)').matches : theme === 'dark'; document.documentElement.dataset.theme = dark ? 'dark' : 'light'; };\n"
        "    apply(); const mq = matchMedia('(prefers-color-scheme: dark)'); mq.addEventListener('change', apply); return () => mq.removeEventListener('change', apply);\n"
        '  }, [theme]);\n'
        '  useEffect(() => { if (settings && !themeFromStorage()) setThemeState(settings.theme); }, [settings]);\n'
        "  useEffect(() => { // iframe auto-height contract: window.parent.postMessage({type:'vibe:resize', height})\n"
        '    const el = shellRef.current;\n'
        '    if (!el || !embedded) return;\n'
        '    let lastHeight = 0;\n'
        '    const send = () => {\n'
        '      const height = Math.ceil(el.getBoundingClientRect().height);\n'
        '      if (!height || height === lastHeight) return;\n'
        '      lastHeight = height;\n'
        "      window.parent.postMessage({ type: 'vibe:resize', height }, '*');\n"
        '    };\n'
        '    const ro = new ResizeObserver(send);\n'
        '    ro.observe(el);\n'
        '    send();\n'
        '    return () => ro.disconnect();\n'
        '  }, [authErr]);\n'
        '  const isAdmin = !!me?.is_admin; const meLoaded = me !== null;\n'
        "  useEffect(() => { const h = () => { const s = parseHash(); if (s === 'analytics' && !isAdmin) return; setScreen(s); }; window.addEventListener('hashchange', h); return () => window.removeEventListener('hashchange', h); }, [isAdmin]);\n"
        "  useEffect(() => { if (meLoaded && !isAdmin && screen === 'analytics') go('generator'); }, [meLoaded, isAdmin, screen, go]); // admin-only section: non-admins fall back to the generator\n"
        '\n'
      )),
      ((
        "  const agentDot = !agent ? '' : agent.paused_reason ? 'warn' : !agent.auto_refresh_enabled ? '' : agent.busy ? 'run' : 'ok';\n"
        "  const ThemeIcon = theme === 'dark' ? Moon : theme === 'light' ? Sun : Monitor;\n"
        '  const systemNav = SYSTEM.filter((n) => !n.adminOnly || isAdmin);\n'
        '  const flatNav = [NEW_PROMPT, ...WORK, ...systemNav, SETTINGS];\n'
        '  const mainNav = compact ? flatNav.slice(0, 4) : flatNav; const moreNav = compact ? flatNav.slice(4) : [];\n'
        "  const collapsed = !compact && (sidebarPref ? sidebarPref === 'collapsed' : bodyW < 1024);\n"
        "  const toggleSidebar = () => { const next = collapsed ? 'expanded' : 'collapsed'; setSidebarPref(next); store.set('sidebar', next); };\n"
        '  const themeLabel = `${t.nav.themeLabel}: ${t.settings.theme[theme]}`; const userName = me?.name ?? t.nav.userFallback;\n'
        "  const cycleTheme = () => state.setTheme(theme === 'dark' ? 'light' : theme === 'light' ? 'system' : 'dark');\n"
        '  const navButton = (n: NavDef, extra = \'\') => <button key={n.id} className={`nav-item ${extra} ${screen === n.id ? \'on\' : \'\'}`} onClick={() => go(n.id)} aria-current={screen === n.id ? \'page\' : undefined} aria-label={collapsed ? n.label : undefined} title={n.label}><n.icon size={n.id === \'generator\' ? 16 : 18} aria-hidden /><span className="nav-label">{n.label}</span></button>;\n'
        '\n'
        '  if (authErr) return <ToastProvider><div style={{ padding: \'var(--space-10)\' }}><div className="empty glass"><Logo /><h3 style={{ marginTop: \'var(--space-3)\' }}>{t.appName}</h3><p className="tx2">{t.auth.required}</p></div></div></ToastProvider>;\n'
        '\n'
        '  return (\n'
        '    <AppCtx.Provider value={state}><ToastProvider>\n'
        "      <div className={`shell ${compact ? 'compact' : ''}`} ref={shellRef}>\n"
        '        {!compact && (\n'
        '          <aside id="app-sidebar" className={`sidebar ${collapsed ? \'collapsed\' : \'\'}`} aria-label={t.nav.mainLabel}>\n'
        '            <div className="sidebar-head">\n'
        '              <Logo />{!collapsed && <span className="sidebar-name">{t.appName}</span>}\n'
      ), (
        "  const agentDot = !agent ? '' : agent.paused_reason ? 'warn' : !agent.auto_refresh_enabled ? '' : agent.busy ? 'run' : 'ok';\n"
        "  const ThemeIcon = theme === 'dark' ? Moon : theme === 'light' ? Sun : Monitor;\n"
        '  const systemNav = SYSTEM.filter((n) => !n.adminOnly || isAdmin);\n'
        '  const flatNav = [NEW_PROMPT, ...WORK, ...systemNav, SETTINGS];\n'
        '  const mainNav = flatNav.slice(0, 4);\n'
        '  const moreNav = flatNav.slice(4);\n'
        "  const collapsed = !compact && (sidebarPref ? sidebarPref === 'collapsed' : bodyW < 1024);\n"
        "  const toggleSidebar = () => { const next = collapsed ? 'expanded' : 'collapsed'; setSidebarPref(next); store.set('sidebar', next); };\n"
        '  const themeLabel = `${t.nav.themeLabel}: ${t.settings.theme[theme]}`; const userName = me?.name ?? t.nav.userFallback;\n'
        "  const cycleTheme = () => state.setTheme(theme === 'dark' ? 'light' : theme === 'light' ? 'system' : 'dark');\n"
        '  const navButton = (n: NavDef, extra = \'\') => <button key={n.id} className={`nav-item ${extra} ${screen === n.id ? \'on\' : \'\'}`} onClick={() => go(n.id)} aria-current={screen === n.id ? \'page\' : undefined} aria-label={collapsed ? n.label : undefined} title={n.label}><n.icon size={n.id === \'generator\' ? 16 : 18} aria-hidden /><span className="nav-label">{n.label}</span></button>;\n'
        '\n'
        '  if (authErr) return <ToastProvider><div ref={shellRef} style={{ padding: \'var(--space-10)\' }}><div className="empty surface"><Logo /><h3 style={{ marginTop: \'var(--space-3)\' }}>{t.appName}</h3><p className="tx2">{t.auth.required}</p></div></div></ToastProvider>;\n'
        '\n'
        '  return (\n'
        '    <AppCtx.Provider value={state}><ToastProvider>\n'
        "      <div className={`shell ${compact ? 'compact' : ''} ${embedded ? 'embedded' : ''}`} ref={shellRef}>\n"
        '        {!compact && (\n'
        '          <aside id="app-sidebar" className={`sidebar ${collapsed ? \'collapsed\' : \'\'}`} aria-label={t.nav.mainLabel}>\n'
        '            <div className="sidebar-head">\n'
        '              <Logo />{!collapsed && <span className="sidebar-name">{t.appName}</span>}\n'
      )),
      ((
        '              <button className="icon-btn" aria-label={themeLabel} title={themeLabel} onClick={cycleTheme}><ThemeIcon size={18} aria-hidden /></button>\n'
        '              <span className="avatar" title={userName} aria-label={userName}>{initials(me?.name ?? \'\')}</span>\n'
        '            </header>\n'
        '          )}\n'
        '          <main className="content">\n'
        '            {agent?.paused_reason && <div className="banner err" role="alert"><span className="grow">{agent.paused_reason.startsWith(\'quota\') ? t.banner.quota : t.banner.paused}</span></div>}\n'
        '            {agent?.scheduler_mode === \'lazy\' && <div className="banner warn"><span className="grow">{t.banner.fallback}</span></div>}\n'
        '            <Boundary key={screen}>\n'
      ), (
        '              <button className="icon-btn" aria-label={themeLabel} title={themeLabel} onClick={cycleTheme}><ThemeIcon size={18} aria-hidden /></button>\n'
        '              <span className="avatar" title={userName} aria-label={userName}>{initials(me?.name ?? \'\')}</span>\n'
        '            </header>\n'
        '          )}\n'
        '        {compact && <nav className="bottom-tabs" aria-label={t.nav.tabsLabel}>\n'
        "          {mainNav.map((n) => <button key={n.id} className={`nav-item ${screen === n.id ? 'on' : ''}`} onClick={() => go(n.id)} aria-current={screen === n.id ? 'page' : undefined} aria-label={n.label}><n.icon size={20} aria-hidden /><span>{n.id === 'optimizer' ? t.nav.optimizerShort : n.id === 'library' ? t.nav.libraryShort : n.label}</span></button>)}\n"
        '          {moreNav.length > 0 && <button className="nav-item" onClick={() => setMoreOpen(true)} aria-label={t.nav.more}><MoreHorizontal size={20} aria-hidden /><span>{t.nav.more}</span></button>}\n'
        '        </nav>}\n'
        '          <main className="content">\n'
        '            {agent?.paused_reason && <div className="banner err" role="alert"><span className="grow">{agent.paused_reason.startsWith(\'quota\') ? t.banner.quota : t.banner.paused}</span></div>}\n'
        '            {agent?.scheduler_mode === \'lazy\' && <div className="banner warn"><span className="grow">{t.banner.fallback}</span></div>}\n'
        '            <Boundary key={screen}>\n'
      )),
      ((
        "              {screen === 'analytics' && (meLoaded ? <AnalyticsScreen /> : <Spinner />)}\n"
        '            </Boundary>\n'
        '          </main>\n'
        '        </div>\n'
        '        <nav className="bottom-tabs" aria-label={t.nav.tabsLabel}>\n'
        "          {mainNav.map((n) => <button key={n.id} className={`nav-item ${screen === n.id ? 'on' : ''}`} onClick={() => go(n.id)} aria-current={screen === n.id ? 'page' : undefined} aria-label={n.label}><n.icon size={20} aria-hidden /><span>{n.label}</span></button>)}\n"
        '          {moreNav.length > 0 && <button className="nav-item" onClick={() => setMoreOpen(true)} aria-label={t.nav.more}><MoreHorizontal size={20} aria-hidden /><span>{t.nav.more}</span></button>}\n'
        '        </nav>\n'
        '        {moreOpen && <Modal title={t.nav.more} onClose={() => setMoreOpen(false)}>{moreNav.map((n) => <button key={n.id} className="nav-item" onClick={() => go(n.id)}><n.icon size={20} aria-hidden />{n.label}</button>)}</Modal>}\n'
        '      </div>\n'
        '      {waking && <div className="overlay" style={{ zIndex: 80 }} role="alert"><div className="glass dense empty" style={{ maxWidth: 420 }}><Logo /><h3 style={{ margin: \'var(--space-3) 0 var(--space-2)\' }}>{t.wake.title}</h3><p className="tx2" style={{ margin: \'0 0 var(--space-3)\' }}>{t.wake.hint}</p><Spinner /></div></div>}\n'
        '    </ToastProvider></AppCtx.Provider>\n'
        '  );\n'
        '}\n'
      ), (
        "              {screen === 'analytics' && (meLoaded ? <AnalyticsScreen /> : <Spinner />)}\n"
        '            </Boundary>\n'
        '          </main>\n'
        '        </div>\n'
        '        {moreOpen && <Modal title={t.nav.more} onClose={() => setMoreOpen(false)}>{moreNav.map((n) => <button key={n.id} className="nav-item" onClick={() => go(n.id)}><n.icon size={20} aria-hidden />{n.label}</button>)}</Modal>}\n'
        '      </div>\n'
        '      {waking && <div className="overlay" style={{ zIndex: 80 }} role="alert"><div className="surface empty" style={{ maxWidth: 420 }}><Logo /><h3 style={{ margin: \'var(--space-3) 0 var(--space-2)\' }}>{t.wake.title}</h3><p className="tx2" style={{ margin: \'0 0 var(--space-3)\' }}>{t.wake.hint}</p><Spinner /></div></div>}\n'
        '    </ToastProvider></AppCtx.Provider>\n'
        '  );\n'
        '}\n'
      )),
    ),
    'apps/web/src/api.ts': (
      ((
        "import type { GenerateRequest, GenerationDTO, ResultDTO, SystemId } from '../../../shared/src/index.ts';\n"
        "import { t } from './strings.ru.ts';\n"
        '\n'
        'export class ApiError extends Error {\n'
        '  constructor(public status: number, public code: string, message: string, public retryAfter?: number) { super(message); }\n'
      ), (
        "import type { GenerationDTO, ResultDTO, SystemId } from '../../../shared/src/index.ts';\n"
        "import { t } from './strings.ru.ts';\n"
        '\n'
        'export class ApiError extends Error {\n'
        '  constructor(public status: number, public code: string, message: string, public retryAfter?: number) { super(message); }\n'
      )),
      ((
        'const setWake = (delta: number) => { const before = wakeCount > 0; wakeCount = Math.max(0, wakeCount + delta); const after = wakeCount > 0; if (before !== after) wakeListeners.forEach((l) => l(after)); };\n'
        'const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));\n'
        'const WAKE_BUDGET_MS = 5 * 60_000;\n'
        '\n'
        'export async function request<T>(path: string, init: { method?: string; body?: unknown } = {}): Promise<T> {\n'
        '  const started = Date.now(); let waking = false; let attempt = 0;\n'
        '  try {\n'
        '    for (;;) {\n'
        '      const slow = setTimeout(() => { if (!waking) { waking = true; setWake(1); } }, 3000);\n'
        '      try {\n'
        "        const res = await fetch(path, { method: init.method ?? (init.body !== undefined ? 'POST' : 'GET'), headers: init.body !== undefined ? { 'Content-Type': 'application/json' } : undefined, body: init.body !== undefined ? JSON.stringify(init.body) : undefined });\n"
        '        clearTimeout(slow);\n'
        '        if (res.status === 503 && Date.now() - started < WAKE_BUDGET_MS) {\n'
        '          if (!waking) { waking = true; setWake(1); }\n'
        "          const ra = Number(res.headers.get('retry-after')); await sleep((Number.isFinite(ra) && ra > 0 ? Math.min(ra, 20) : Math.min(2 + attempt, 10)) * 1000); attempt++; continue;\n"
        '        }\n'
        '        const text = await res.text(); let json: any = null;\n'
        '        try { json = text ? JSON.parse(text) : null; } catch { json = null; }\n'
        "        if (!res.ok) throw new ApiError(res.status, json?.error?.code ?? `http_${res.status}`, json?.error?.message ?? t.common.error, Number(res.headers.get('retry-after')) || undefined);\n"
        '        return json as T;\n'
        '      } catch (e) {\n'
        '        clearTimeout(slow);\n'
        '        if (e instanceof ApiError) throw e;\n'
        "        const isGet = (init.method ?? 'GET') === 'GET';\n"
        '        if (isGet && Date.now() - started < WAKE_BUDGET_MS) { if (!waking) { waking = true; setWake(1); } await sleep(Math.min(2 + attempt, 10) * 1000); attempt++; continue; }\n'
        "        throw new ApiError(0, 'network', t.common.error);\n"
        '      }\n'
        '    }\n'
      ), (
        'const setWake = (delta: number) => { const before = wakeCount > 0; wakeCount = Math.max(0, wakeCount + delta); const after = wakeCount > 0; if (before !== after) wakeListeners.forEach((l) => l(after)); };\n'
        'const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));\n'
        'const WAKE_BUDGET_MS = 5 * 60_000;\n'
        '\n'
        'async function request<T>(path: string, init: { method?: string; body?: unknown } = {}): Promise<T> {\n'
        "  const method = init.method ?? 'GET';\n"
        '  const started = Date.now(); let waking = false; let attempt = 0;\n'
        '  try {\n'
        '    for (;;) {\n'
        "      const slow = setTimeout(() => { if (method === 'GET' && !waking) { waking = true; setWake(1); } }, 3000);\n"
        '      try {\n'
        "        const res = await fetch(path, { method, headers: init.body !== undefined ? { 'Content-Type': 'application/json' } : undefined, body: init.body !== undefined ? JSON.stringify(init.body) : undefined });\n"
        '        clearTimeout(slow);\n'
        '        const text = await res.text(); let json: any = null;\n'
        '        try { json = text ? JSON.parse(text) : null; } catch { json = null; }\n'
        "        const retryable = method === 'GET' || json?.error?.code === 'starting';\n"
        '        if (res.status === 503 && retryable && Date.now() - started < WAKE_BUDGET_MS) {\n'
        '          if (!waking) { waking = true; setWake(1); }\n'
        "          const ra = Number(res.headers.get('retry-after')); await sleep((Number.isFinite(ra) && ra > 0 ? Math.min(ra, 20) : Math.min(2 + attempt, 10)) * 1000); attempt++; continue;\n"
        '        }\n'
        "        if (!res.ok) throw new ApiError(res.status, json?.error?.code ?? `http_${res.status}`, json?.error?.message ?? t.common.error, Number(res.headers.get('retry-after')) || undefined);\n"
        '        return json as T;\n'
        '      } catch (e) {\n'
        '        clearTimeout(slow);\n'
        '        if (e instanceof ApiError) throw e;\n'
        "        const isGet = method === 'GET';\n"
        '        if (isGet && Date.now() - started < WAKE_BUDGET_MS) { if (!waking) { waking = true; setWake(1); } await sleep(Math.min(2 + attempt, 10) * 1000); attempt++; continue; }\n'
        "        throw new ApiError(0, 'network', t.common.error);\n"
        '      }\n'
        '    }\n'
      )),
      ((
        '  } catch { /* stream broke: fall back to polling below */ }\n'
        '  clearTimeout(watchdog);\n'
        "  if (!finished) { if (genId) await poll(); else h.onError?.(new ApiError(0, 'stream', t.common.error)); }\n"
        '}\n'
        'export type { GenerateRequest };\n'
      ), (
        '  } catch { /* stream broke: fall back to polling below */ }\n'
        '  clearTimeout(watchdog);\n'
        "  if (!finished) { if (genId) await poll(); else h.onError?.(new ApiError(0, 'stream', t.common.error)); }\n"
        '}\n'
      )),
    ),
    'apps/web/src/components/EngineSettings.tsx': (
      ((
        "import { useEffect, useState } from 'react';\n"
        "import { PROVIDERS, type EngineView, type Provider } from '../../../../shared/src/index.ts';\n"
        "import { t } from '../strings.ru.ts';\n"
        "import { get, post, put, ApiError } from '../api.ts';\n"
        "import { Spinner, useToast } from '../ui.tsx';\n"
        '\n'
        "const CUSTOM = '__custom__';\n"
        'export function EngineSettings({ admin }: { admin: boolean }) {\n'
        '  const toast = useToast();\n'
        '  const [view, setView] = useState<EngineView | null>(null);\n'
        "  const [provider, setProvider] = useState<Provider>('platform'); const [model, setModel] = useState(''); const [custom, setCustom] = useState(false);\n"
        "  const [baseUrl, setBaseUrl] = useState(''); const [temp, setTemp] = useState(0.4); const [key, setKey] = useState(''); const [clearKey, setClearKey] = useState(false);\n"
        '  const [busy, setBusy] = useState(false);\n'
        "  const apply = (v: EngineView) => { setView(v); setProvider(v.provider); setModel(v.model); setBaseUrl(v.base_url); setTemp(v.temperature); setKey(''); setClearKey(false);\n"
        "    const list = v.provider === 'platform' || v.provider === 'custom' ? [] : v.catalog[v.provider]; setCustom(!list.some((m) => m.id === v.model)); };\n"
        "  useEffect(() => { get<EngineView>('/api/optimizer/engine').then(apply).catch(() => {}); }, []);\n"
        '  if (!view) return null;\n'
        "  const list = provider === 'platform' || provider === 'custom' ? [] : view.catalog[provider];\n"
        "  const needsKey = provider !== 'platform';\n"
        "  const fail = (e: unknown) => toast((e as ApiError).message ?? t.common.error, 'err');\n"
        "  const changeProvider = (p: Provider) => { setProvider(p); const first = p === 'platform' || p === 'custom' ? null : view.catalog[p][0]; setCustom(!first); setModel(first?.id ?? (p === 'platform' ? 'bitrix/bitrixgpt-5.5' : '')); };\n"
        '  const save = async () => {\n'
        '    setBusy(true);\n'
        "    try { apply(await put<EngineView>('/api/optimizer/engine', { provider, model, base_url: baseUrl, temperature: temp, ...(clearKey ? { api_key: '' } : key ? { api_key: key } : {}) })); toast(t.settings.saved, 'ok'); }\n"
        '    catch (e) { fail(e); } finally { setBusy(false); }\n'
        '  };\n'
        "  const test = async () => { setBusy(true); try { const r = await post<{ latency_ms: number; model: string }>('/api/optimizer/engine/test'); toast(`${t.engine.testOk}: ${r.model}, ${r.latency_ms} ${t.engine.ms}`, 'ok'); } catch (e) { fail(e); } finally { setBusy(false); } };\n"
        '  const unverified = !custom && list.find((m) => m.id === model)?.verified === false;\n'
        '  return (\n'
        '    <section className="glass card col" aria-label={t.engine.title}>\n'
        '      <h3>{t.engine.title}</h3>\n'
        '      {!admin && <div className="banner warn">{t.engine.adminOnly}</div>}\n'
        '      {needsKey && !view.secret_configured && <div className="banner err" role="alert">{t.engine.secretMissing}</div>}\n'
        '      <div className="row wrap" style={{ gap: \'var(--space-4)\', alignItems: \'flex-start\' }}>\n'
        '        <div><label className="label" htmlFor="eng-provider">{t.engine.provider}</label>\n'
        '          <select id="eng-provider" className="inset-field" disabled={!admin} value={provider} onChange={(e) => changeProvider(e.target.value as Provider)}>{PROVIDERS.map((p) => <option key={p} value={p}>{t.engine.providers[p]}</option>)}</select></div>\n'
        '        <div><label className="label" htmlFor="eng-model">{t.engine.model}</label>\n'
        '          {list.length > 0 && <select id="eng-model" className="inset-field" disabled={!admin} value={custom ? CUSTOM : model} onChange={(e) => { if (e.target.value === CUSTOM) { setCustom(true); } else { setCustom(false); setModel(e.target.value); } }}>\n'
        "            {list.map((m) => <option key={m.id} value={m.id}>{m.label}{m.recommended ? ' ★' : ''}{m.verified ? '' : ' *'}</option>)}<option value={CUSTOM}>{t.engine.customModel}</option></select>}\n"
        '          {(custom || list.length === 0) && <input id={list.length ? \'eng-model-custom\' : \'eng-model\'} aria-label={t.engine.customModel} className="inset-field" style={{ marginTop: list.length ? \'var(--space-2)\' : 0 }} disabled={!admin} value={model} onChange={(e) => setModel(e.target.value)} placeholder={t.engine.customModel} />}\n'
        '          {unverified && <div className="small tx3" style={{ marginTop: \'var(--space-1)\' }}>* {t.engine.unverified}</div>}</div>\n'
        '      </div>\n'
        '      {needsKey && <div><label className="label" htmlFor="eng-base">{t.engine.baseUrl}</label><input id="eng-base" className="inset-field" disabled={!admin} value={baseUrl} placeholder={view.default_base_urls[provider] ?? \'https://\'} onChange={(e) => setBaseUrl(e.target.value)} /><div className="small tx3">{t.engine.baseUrlHint}</div></div>}\n'
        '      <div><label className="label" htmlFor="eng-temp">{t.engine.temperature}: <span className="mono">{temp.toFixed(1)}</span></label><input id="eng-temp" type="range" min={0} max={1.5} step={0.1} disabled={!admin} value={temp} onChange={(e) => setTemp(Number(e.target.value))} /></div>\n'
        '      {needsKey && <div><label className="label" htmlFor="eng-key">{t.engine.apiKey}{view.has_key && !clearKey ? ` · ${t.engine.apiKeyKept} (${view.key_hint})` : \'\'}</label>\n'
        '        <input id="eng-key" className="inset-field" type="password" autoComplete="off" disabled={!admin || clearKey} value={key} placeholder={t.engine.apiKeyNew} onChange={(e) => setKey(e.target.value)} />\n'
        '        {view.has_key && admin && <label className="row small" style={{ marginTop: \'var(--space-2)\' }}><input type="checkbox" checked={clearKey} onChange={(e) => setClearKey(e.target.checked)} />{t.engine.apiKeyClear}</label>}\n'
        '        <div className="small tx3">{t.engine.note}</div></div>}\n'
        '      <div className="row wrap"><button className="btn primary" disabled={!admin || busy || !model.trim()} onClick={save}>{busy ? <Spinner /> : null}{t.engine.save}</button><button className="btn" disabled={!admin || busy} onClick={test}>{t.engine.test}</button></div>\n'
        '    </section>\n'
        '  );\n'
        '}\n'
      ), (
        "import { useEffect, useState } from 'react';\n"
        "import { DEFAULT_ENGINE_MODEL, PROVIDERS, supportsCustomTemperature, type EngineView, type Provider } from '../../../../shared/src/index.ts';\n"
        "import { t } from '../strings.ru.ts';\n"
        "import { get, post, put, ApiError } from '../api.ts';\n"
        "import { Spinner, useToast } from '../ui.tsx';\n"
        '\n'
        "const CUSTOM = '__custom__';\n"
        'export function EngineSettings({ admin }: { admin: boolean }) {\n'
        '  const toast = useToast();\n'
        '  const [view, setView] = useState<EngineView | null>(null);\n'
        '  const [loadError, setLoadError] = useState(false);\n'
        "  const [provider, setProvider] = useState<Provider>('platform'); const [model, setModel] = useState(''); const [custom, setCustom] = useState(false);\n"
        "  const [baseUrl, setBaseUrl] = useState(''); const [temp, setTemp] = useState(0.4); const [key, setKey] = useState(''); const [clearKey, setClearKey] = useState(false);\n"
        '  const [busy, setBusy] = useState(false);\n'
        "  const apply = (v: EngineView) => { setView(v); setProvider(v.provider); setModel(v.model); setBaseUrl(v.base_url); setTemp(v.temperature); setKey(''); setClearKey(false);\n"
        "    const list = v.provider === 'platform' || v.provider === 'custom' ? [] : v.catalog[v.provider]; setCustom(!list.some((m) => m.id === v.model)); };\n"
        "  useEffect(() => { get<EngineView>('/api/optimizer/engine').then(apply).catch(() => setLoadError(true)); }, []);\n"
        '  if (loadError) return <div className="banner err" role="alert">{t.engine.loadError}</div>;\n'
        '  if (!view) return <Spinner />;\n'
        "  const list = provider === 'platform' || provider === 'custom' ? [] : view.catalog[provider];\n"
        "  const needsKey = provider !== 'platform';\n"
        "  const destinationChanged = provider !== view.provider || baseUrl.trim().replace(/\\/+$/, '') !== view.base_url.replace(/\\/+$/, '');\n"
        '  const keepStoredKey = view.has_key && !destinationChanged;\n'
        "  const fail = (e: unknown) => toast((e as ApiError).message ?? t.common.error, 'err');\n"
        '  const changeProvider = (p: Provider) => {\n'
        '    setProvider(p);\n'
        "    setBaseUrl('');\n"
        "    setKey('');\n"
        '    setClearKey(false);\n'
        "    const first = p === 'platform' || p === 'custom' ? undefined : (view.catalog[p].find((m) => m.recommended) ?? view.catalog[p][0]);\n"
        '    setCustom(!first);\n'
        "    setModel(first?.id ?? (p === 'platform' ? DEFAULT_ENGINE_MODEL : ''));\n"
        '  };\n'
        '  const save = async () => {\n'
        '    setBusy(true);\n'
        "    try { apply(await put<EngineView>('/api/optimizer/engine', { provider, model, base_url: baseUrl, temperature: temp, ...(clearKey ? { api_key: '' } : key ? { api_key: key } : {}) })); toast(t.settings.saved, 'ok'); }\n"
        '    catch (e) { fail(e); } finally { setBusy(false); }\n'
        '  };\n'
        "  const test = async () => { setBusy(true); try { const r = await post<{ latency_ms: number; model: string }>('/api/optimizer/engine/test'); toast(`${t.engine.testOk}: ${r.model}, ${r.latency_ms} ${t.engine.ms}`, 'ok'); } catch (e) { fail(e); } finally { setBusy(false); } };\n"
        '  return (\n'
        '    <section className="surface card col" aria-label={t.engine.title}>\n'
        '      <h3>{t.engine.title}</h3>\n'
        '      {!admin && <div className="banner warn">{t.engine.adminOnly}</div>}\n'
        '      {needsKey && !view.secret_configured && <div className="banner err" role="alert">{t.engine.secretMissing}</div>}\n'
        '      <div className="form-grid">\n'
        '        <div><label className="label" htmlFor="eng-provider">{t.engine.provider}</label>\n'
        '          <select id="eng-provider" className="field" disabled={!admin || busy} value={provider} onChange={(e) => changeProvider(e.target.value as Provider)}>{PROVIDERS.map((p) => <option key={p} value={p}>{t.engine.providers[p]}</option>)}</select></div>\n'
        '        <div><label className="label" htmlFor="eng-model">{t.engine.model}</label>\n'
        '          {list.length > 0 && <select id="eng-model" className="field" disabled={!admin || busy} value={custom ? CUSTOM : model} onChange={(e) => { if (e.target.value === CUSTOM) { setCustom(true); } else { setCustom(false); setModel(e.target.value); } }}>\n'
        '            {list.map((m) => <option key={m.id} value={m.id}>{m.label}</option>)}<option value={CUSTOM}>{t.engine.customModel}</option></select>}\n'
        '          {(custom || list.length === 0) && <input id={list.length ? \'eng-model-custom\' : \'eng-model\'} aria-label={t.engine.customModel} className="field" style={{ marginTop: list.length ? \'var(--space-2)\' : 0 }} disabled={!admin || busy} value={model} onChange={(e) => setModel(e.target.value)} placeholder={t.engine.customModel} />}\n'
        '        </div>\n'
        '      </div>\n'
        '      {needsKey && <div><label className="label" htmlFor="eng-base">{t.engine.baseUrl}</label><input id="eng-base" className="field" disabled={!admin || busy} value={baseUrl} placeholder={view.default_base_urls[provider] ?? \'https://\'} onChange={(e) => { setBaseUrl(e.target.value); setClearKey(false); }} /><div className="small tx3">{t.engine.baseUrlHint}</div></div>}\n'
        '      {supportsCustomTemperature(provider, model) && <div><label className="label" htmlFor="eng-temp">{t.engine.temperature}: <span className="mono">{temp.toFixed(1)}</span></label><input id="eng-temp" type="range" min={0} max={1.5} step={0.1} disabled={!admin || busy} value={temp} onChange={(e) => setTemp(Number(e.target.value))} /></div>}\n'
        '      {needsKey && <div><label className="label" htmlFor="eng-key">{t.engine.apiKey}{keepStoredKey && !clearKey ? ` · ${t.engine.apiKeyKept} (${view.key_hint})` : \'\'}</label>\n'
        '        <input id="eng-key" className="field" type="password" autoComplete="off" disabled={!admin || clearKey || busy} value={key} placeholder={t.engine.apiKeyNew} onChange={(e) => setKey(e.target.value)} />\n'
        '        {keepStoredKey && admin && <label className="row small" style={{ marginTop: \'var(--space-2)\' }}><input type="checkbox" checked={clearKey} onChange={(e) => setClearKey(e.target.checked)} />{t.engine.apiKeyClear}</label>}\n'
        '        <div className="small tx3">{view.has_key && destinationChanged ? t.engine.keyDestinationChanged : t.engine.note}</div></div>}\n'
        '      <div className="row wrap"><button className="btn primary" disabled={!admin || busy || !model.trim()} onClick={save}>{busy ? <Spinner /> : null}{t.engine.save}</button><button className="btn" disabled={!admin || busy} onClick={test}>{t.engine.test}</button></div>\n'
        '    </section>\n'
        '  );\n'
        '}\n'
      )),
    ),
    'apps/web/src/components/OptimizationView.tsx': (
      ((
        "import { useEffect, useMemo, useState } from 'react';\n"
        "import { Minimize2 } from 'lucide-react';\n"
        "import { estimateTokens, substituteBracketVars, type FolderDTO, type OptimizationDTO } from '../../../../shared/src/index.ts';\n"
        "import { t } from '../strings.ru.ts';\n"
        "import { patch, post, ApiError } from '../api.ts';\n"
        "import { CopyButton, Spinner, StarButton, useToast } from '../ui.tsx';\n"
        '\n'
        'type Compressed = OptimizationDTO & { no_gain?: boolean; saved_pct?: number };\n'
        '\n'
        'const ScoreBar = ({ label, value }: { label: string; value: number | null }) => (\n'
        '  <div style={{ flex: 1, minWidth: 160 }}>\n'
        '    <div className="row spread small"><span className="tx2">{label}</span><strong className="mono">{value === null ? \'—\' : value.toFixed(1)}/10</strong></div>\n'
        '    <div role="img" aria-label={`${label}: ${value ?? 0} / 10`} style={{ height: \'var(--space-2)\', borderRadius: \'var(--radius-full)\', background: \'var(--color-surface-secondary)\', border: \'1px solid var(--color-border)\', marginTop: \'var(--space-1)\' }}>\n'
        "      <div style={{ width: `${Math.round(((value ?? 0) / 10) * 100)}%`, height: '100%', borderRadius: 'var(--radius-full)', background: 'var(--color-accent)' }} />\n"
        '    </div>\n'
      ), (
        "import { useMemo, useState } from 'react';\n"
        "import { Minimize2 } from 'lucide-react';\n"
        "import { estimateTokens, OPT_LIMITS, substituteBracketVars, type FolderDTO, type OptimizationDTO } from '../../../../shared/src/index.ts';\n"
        "import { t } from '../strings.ru.ts';\n"
        "import { patch, post, ApiError } from '../api.ts';\n"
        "import { CopyButton, Spinner, StarButton, useToast } from '../ui.tsx';\n"
        '\n'
        'type Compressed = OptimizationDTO & { no_gain?: boolean; saved_pct?: number };\n'
        '\n'
        'const ScoreBar = ({ label, value }: { label: string; value: number | null }) => (\n'
        '  <div className="score-field">\n'
        '    <div className="row spread small"><span className="tx2">{label}</span><strong className="mono">{value === null ? \'—\' : value.toFixed(1)}/10</strong></div>\n'
        '    <div role="img" aria-label={`${label}: ${value ?? 0} / 10`} style={{ height: \'var(--space-2)\', borderRadius: \'var(--radius-full)\', background: \'var(--color-surface-secondary)\', border: \'1px solid var(--color-border)\', marginTop: \'var(--space-1)\' }}>\n'
        "      <div style={{ width: `${Math.round(((value ?? 0) / 10) * 100)}%`, height: '100%', borderRadius: 'var(--radius-full)', background: 'var(--color-accent)' }} />\n"
        '    </div>\n'
      )),
      ((
        '  const toast = useToast();\n'
        '  const [values, setValues] = useState<Record<string, string>>(item.var_values);\n'
        "  const [busy, setBusy] = useState(false); const [view, setView] = useState<'full' | 'compressed'>(item.compressed_prompt ? 'compressed' : 'full');\n"
        "  const [note, setNote] = useState<string>(''); const [tags, setTags] = useState(item.tags.join(', '));\n"
        "  useEffect(() => { setValues(item.var_values); setView(item.compressed_prompt ? 'compressed' : 'full'); setTags(item.tags.join(', ')); setNote(''); }, [item.id]); // eslint-disable-line react-hooks/exhaustive-deps\n"
        "  const base = view === 'compressed' && item.compressed_prompt ? item.compressed_prompt : item.final_prompt;\n"
        '  const master = useMemo(() => substituteBracketVars(base, values), [base, values]);\n'
        "  const fail = (e: unknown) => toast((e as ApiError).message ?? t.common.error, 'err');\n"
        '  const save = async (body: Record<string, unknown>) => { try { onChange(await patch<OptimizationDTO>(`/api/optimizer/items/${item.id}`, body)); } catch (e) { fail(e); } };\n'
      ), (
        '  const toast = useToast();\n'
        '  const [values, setValues] = useState<Record<string, string>>(item.var_values);\n'
        "  const [busy, setBusy] = useState(false); const [view, setView] = useState<'full' | 'compressed'>(item.compressed_prompt ? 'compressed' : 'full');\n"
        "  const [note, setNote] = useState<string>(''); const [tags, setTags] = useState(item.tags.join(', '));\n"
        "  const base = view === 'compressed' && item.compressed_prompt ? item.compressed_prompt : item.final_prompt;\n"
        '  const master = useMemo(() => substituteBracketVars(base, values), [base, values]);\n'
        "  const fail = (e: unknown) => toast((e as ApiError).message ?? t.common.error, 'err');\n"
        '  const save = async (body: Record<string, unknown>) => { try { onChange(await patch<OptimizationDTO>(`/api/optimizer/items/${item.id}`, body)); } catch (e) { fail(e); } };\n'
      )),
      ((
        '    } catch (e) { fail(e); } finally { setBusy(false); }\n'
        '  };\n'
        '  return (\n'
        '    <div className="col">\n'
        '      <div className="glass card col" aria-label={t.opt.optimized}>\n'
        '        <div className="row wrap" style={{ gap: \'var(--space-6)\' }}><ScoreBar label={t.opt.initial} value={item.initial_score} /><ScoreBar label={t.opt.optimized} value={item.optimized_score} /></div>\n'
        '        {item.initial_critique && <p className="small tx2" style={{ margin: 0 }}>{item.initial_critique}</p>}\n'
        '        <p className="small tx3" style={{ margin: 0 }}>{t.opt.scoreNote}{item.framework_used ? ` · ${t.opt.framework}: ${item.framework_used}` : \'\'}</p>\n'
        '      </div>\n'
        '      <div className="glass card col">\n'
        '        <div className="row spread wrap">\n'
        '          <h3>{t.opt.finalPrompt}</h3>\n'
        '          <div className="row wrap">\n'
        '            {item.compressed_prompt && <div className="seg" role="group" aria-label={t.opt.finalPrompt}>\n'
      ), (
        '    } catch (e) { fail(e); } finally { setBusy(false); }\n'
        '  };\n'
        '  return (\n'
        '    <div className="col">\n'
        '      <div className="surface card col" aria-label={t.opt.optimized}>\n'
        '        <div className="form-grid"><ScoreBar label={t.opt.initial} value={item.initial_score} /><ScoreBar label={t.opt.optimized} value={item.optimized_score} /></div>\n'
        '        {item.initial_critique && <p className="small tx2" style={{ margin: 0 }}>{item.initial_critique}</p>}\n'
        '        <p className="small tx3" style={{ margin: 0 }}>{t.opt.scoreNote}{item.framework_used ? ` · ${t.opt.framework}: ${item.framework_used}` : \'\'}</p>\n'
        '      </div>\n'
        '      <div className="surface card col">\n'
        '        <div className="row spread wrap">\n'
        '          <h3>{t.opt.finalPrompt}</h3>\n'
        '          <div className="row wrap">\n'
        '            {item.compressed_prompt && <div className="seg" role="group" aria-label={t.opt.finalPrompt}>\n'
      )),
      ((
        '          {note && <span className="small tx2" role="status">{note}</span>}\n'
        '        </div>\n'
        '      </div>\n'
        '      {item.variables.length > 0 && (\n'
        '        <div className="glass card col">\n'
        '          <h3>{t.opt.variables}</h3><p className="small tx2" style={{ margin: 0 }}>{t.opt.variablesHint}</p>\n'
        '          <div className="grid-cards">\n'
        '            {item.variables.map((v) => <div key={v}><label className="label" htmlFor={`var-${v}`}>{v}</label>\n'
        '              <input id={`var-${v}`} className="inset-field" value={values[v] ?? \'\'} onChange={(e) => setValues({ ...values, [v]: e.target.value })} onBlur={() => { if (JSON.stringify(values) !== JSON.stringify(item.var_values)) void save({ var_values: values }); }} /></div>)}\n'
        '          </div>\n'
        '        </div>\n'
        '      )}\n'
        '      {item.changelog_explanation.length > 0 && (\n'
        '        <div className="glass card col"><h3>{t.opt.changelog}</h3><ul style={{ margin: 0, paddingLeft: \'var(--space-5)\' }}>{item.changelog_explanation.map((c, i) => <li key={i} className="small" style={{ marginBottom: \'var(--space-1)\' }}>{c}</li>)}</ul></div>\n'
        '      )}\n'
        '      <div className="glass card row wrap">\n'
        '        <div><label className="label" htmlFor={`folder-${item.id}`}>{t.opt.folder}</label>\n'
        '          <select id={`folder-${item.id}`} className="inset-field" style={{ minWidth: 200 }} value={item.folder_id ?? \'\'} onChange={(e) => save({ folder_id: e.target.value || null })}>\n'
        '            <option value="">{t.opt.noFolder}</option>{folders.map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}</select></div>\n'
        '        <div className="grow"><label className="label" htmlFor={`tags-${item.id}`}>{t.opt.tags}</label>\n'
        '          <input id={`tags-${item.id}`} className="inset-field" value={tags} onChange={(e) => setTags(e.target.value)} onBlur={() => { const list = tags.split(\',\').map((x) => x.trim()).filter(Boolean).slice(0, 8); if (list.join(\'|\') !== item.tags.join(\'|\')) void save({ tags: list }); }} /></div>\n'
        '        <span className="small tx3">{t.opt.engine}: <span className="mono">{item.model || \'—\'}</span></span>\n'
        '      </div>\n'
        '    </div>\n'
        '  );\n'
      ), (
        '          {note && <span className="small tx2" role="status">{note}</span>}\n'
        '        </div>\n'
        '      </div>\n'
        '      {item.variables.length > 0 && (\n'
        '        <div className="surface card col">\n'
        '          <h3>{t.opt.variables}</h3><p className="small tx2" style={{ margin: 0 }}>{t.opt.variablesHint}</p>\n'
        '          <div className="grid-cards">\n'
        '            {item.variables.map((v) => <div key={v}><label className="label" htmlFor={`var-${v}`}>{v}</label>\n'
        '              <input id={`var-${v}`} className="field" maxLength={OPT_LIMITS.variableValue} value={values[v] ?? \'\'} onChange={(e) => setValues({ ...values, [v]: e.target.value })} onBlur={() => { if (JSON.stringify(values) !== JSON.stringify(item.var_values)) void save({ var_values: values }); }} /></div>)}\n'
        '          </div>\n'
        '        </div>\n'
        '      )}\n'
        '      {item.changelog_explanation.length > 0 && (\n'
        '        <div className="surface card col"><h3>{t.opt.changelog}</h3><ul style={{ margin: 0, paddingLeft: \'var(--space-5)\' }}>{item.changelog_explanation.map((c, i) => <li key={i} className="small" style={{ marginBottom: \'var(--space-1)\' }}>{c}</li>)}</ul></div>\n'
        '      )}\n'
        '      <div className="surface card form-grid">\n'
        '        <div><label className="label" htmlFor={`folder-${item.id}`}>{t.opt.folder}</label>\n'
        '          <select id={`folder-${item.id}`} className="field" value={item.folder_id ?? \'\'} onChange={(e) => save({ folder_id: e.target.value || null })}>\n'
        '            <option value="">{t.opt.noFolder}</option>{folders.map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}</select></div>\n'
        '        <div className="grow"><label className="label" htmlFor={`tags-${item.id}`}>{t.opt.tags}</label>\n'
        '          <input id={`tags-${item.id}`} className="field" value={tags} onChange={(e) => setTags(e.target.value)} onBlur={() => { const list = tags.split(\',\').map((x) => x.trim()).filter(Boolean).slice(0, 8); if (JSON.stringify(list) !== JSON.stringify(item.tags)) void save({ tags: list }); }} /></div>\n'
        '        <span className="small tx3">{t.opt.engine}: <span className="mono">{item.model || \'—\'}</span></span>\n'
        '      </div>\n'
        '    </div>\n'
        '  );\n'
      )),
    ),
    'apps/web/src/components/ResultCard.tsx': (
      ((
        '}) {\n'
        "  const [idx, setIdx] = useState(Math.max(0, variants.length - 1)); const [expanded, setExpanded] = useState(false); const [fb, setFb] = useState(''); const [fbOpen, setFbOpen] = useState(false);\n"
        '  useEffect(() => { setIdx(Math.max(0, variants.length - 1)); }, [variants.length]);\n'
        '  const r = variants[Math.min(idx, variants.length - 1)];\n'
        '  if (loading && !r) return <div className="glass card col" aria-busy><div className="row"><SystemDot id={system} /><h3>{SYSTEM_NAMES[system]}</h3><Spinner /></div><div className="skeleton" style={{ height: 220 }} /></div>;\n'
        '  if (!r) return null;\n'
        "  const failed = r.status === 'failed';\n"
        '  return (\n'
        '    <article className="glass card col" aria-label={SYSTEM_NAMES[system]}>\n'
        '      <div className="row wrap spread">\n'
        '        <div className="row"><SystemDot id={system} /><h3>{SYSTEM_NAMES[system]}</h3>{!failed && <span className="badge info">{t.gen.skillBadge} v{r.skill_version}</span>}{!failed && <span className="badge">{(r.latency_ms / 1000).toFixed(1)} c</span>}</div>\n'
        '        {variants.length > 1 && <div className="row" aria-label={t.gen.variant}><button className="icon-btn" aria-label={t.common.prev} disabled={idx === 0} onClick={() => setIdx(idx - 1)}><ChevronLeft size={18} /></button><span className="small tx2">{t.gen.variant} {idx + 1}/{variants.length}</span><button className="icon-btn" aria-label={t.common.next} disabled={idx >= variants.length - 1} onClick={() => setIdx(idx + 1)}><ChevronRight size={18} /></button></div>}\n'
        '      </div>\n'
      ), (
        '}) {\n'
        "  const [idx, setIdx] = useState(Math.max(0, variants.length - 1)); const [expanded, setExpanded] = useState(false); const [fb, setFb] = useState(''); const [fbOpen, setFbOpen] = useState(false);\n"
        '  useEffect(() => { setIdx(Math.max(0, variants.length - 1)); }, [variants.length]);\n'
        '  const r = variants[Math.min(idx, variants.length - 1)];\n'
        '  if (loading && !r) return <div className="surface card col" aria-busy><div className="row"><SystemDot id={system} /><h3>{SYSTEM_NAMES[system]}</h3><Spinner /></div><div className="skeleton" style={{ height: 220 }} /></div>;\n'
        '  if (!r) return null;\n'
        "  const failed = r.status === 'failed';\n"
        '  return (\n'
        '    <article className="surface card col" aria-label={SYSTEM_NAMES[system]}>\n'
        '      <div className="row wrap spread">\n'
        '        <div className="row"><SystemDot id={system} /><h3>{SYSTEM_NAMES[system]}</h3>{!failed && <span className="badge info">{t.gen.skillBadge} v{r.skill_version}</span>}{!failed && <span className="badge">{(r.latency_ms / 1000).toFixed(1)} c</span>}</div>\n'
        '        {variants.length > 1 && <div className="row" aria-label={t.gen.variant}><button className="icon-btn" aria-label={t.common.prev} disabled={idx === 0} onClick={() => setIdx(idx - 1)}><ChevronLeft size={18} /></button><span className="small tx2">{t.gen.variant} {idx + 1}/{variants.length}</span><button className="icon-btn" aria-label={t.common.next} disabled={idx >= variants.length - 1} onClick={() => setIdx(idx + 1)}><ChevronRight size={18} /></button></div>}\n'
        '      </div>\n'
      )),
      ((
        '          <CopyButton text={r.prompt_text} primary /><StarButton on={r.is_favorite} onClick={() => onFavorite(r, !r.is_favorite)} />\n'
        '          <button className="btn sm" onClick={() => onTemplate(r)}><FilePlus2 size={15} />{t.common.toTemplate}</button>\n'
        '          <button className="btn sm" disabled={busy} onClick={() => setFbOpen(!fbOpen)} aria-expanded={fbOpen}>{busy ? <Spinner /> : <RefreshCw size={15} />}{t.gen.regenerate}</button>\n'
        '        </div>\n'
        '        {fbOpen && <div className="row"><input className="inset-field" value={fb} maxLength={500} placeholder={t.gen.feedbackPlaceholder} onChange={(e) => setFb(e.target.value)} onKeyDown={(e) => { if (e.key === \'Enter\') { onRegenerate(r, fb); setFbOpen(false); setFb(\'\'); } }} aria-label={t.gen.feedbackPlaceholder} /><button className="btn primary sm" onClick={() => { onRegenerate(r, fb); setFbOpen(false); setFb(\'\'); }}>{t.gen.applyFeedback}</button></div>}\n'
        '        <details><summary><ChevronDown size={14} style={{ verticalAlign: -2 }} /> {t.gen.improved}</summary>\n'
        '          <ul className="tx2" style={{ margin: \'0 0 10px\', paddingLeft: 20 }}>{r.improvements.map((x, i) => <li key={i}>{x}</li>)}</ul>\n'
        '          {r.assumptions.length > 0 && <><span className="label">{t.gen.assumptionsTitle}</span><div className="row wrap" style={{ marginBottom: 10 }}>{r.assumptions.map((a, i) => <span key={i} className="chip static" style={{ whiteSpace: \'normal\' }}>{a}</span>)}</div></>}\n'
        '          {r.usage_notes && <><span className="label">{t.gen.usageNotes}</span><p className="tx2" style={{ margin: 0 }}>{r.usage_notes}</p></>}\n'
        '        </details>\n'
        '      </>)}\n'
        '      {error && !failed && <p className="small" style={{ color: \'var(--err)\' }}>{error}</p>}\n'
        '    </article>\n'
        '  );\n'
        '}\n'
      ), (
        '          <CopyButton text={r.prompt_text} primary /><StarButton on={r.is_favorite} onClick={() => onFavorite(r, !r.is_favorite)} />\n'
        '          <button className="btn sm" onClick={() => onTemplate(r)}><FilePlus2 size={15} />{t.common.toTemplate}</button>\n'
        '          <button className="btn sm" disabled={busy} onClick={() => setFbOpen(!fbOpen)} aria-expanded={fbOpen}>{busy ? <Spinner /> : <RefreshCw size={15} />}{t.gen.regenerate}</button>\n'
        '        </div>\n'
        '        {fbOpen && <div className="row"><input className="field" value={fb} maxLength={500} placeholder={t.gen.feedbackPlaceholder} onChange={(e) => setFb(e.target.value)} onKeyDown={(e) => { if (e.key === \'Enter\') { onRegenerate(r, fb); setFbOpen(false); setFb(\'\'); } }} aria-label={t.gen.feedbackPlaceholder} /><button className="btn primary sm" onClick={() => { onRegenerate(r, fb); setFbOpen(false); setFb(\'\'); }}>{t.gen.applyFeedback}</button></div>}\n'
        '        <details><summary><ChevronDown size={14} style={{ verticalAlign: -2 }} /> {t.gen.improved}</summary>\n'
        '          <ul className="tx2" style={{ margin: \'0 0 10px\', paddingLeft: 20 }}>{r.improvements.map((x, i) => <li key={i}>{x}</li>)}</ul>\n'
        '          {r.assumptions.length > 0 && <><span className="label">{t.gen.assumptionsTitle}</span><div className="row wrap" style={{ marginBottom: 10 }}>{r.assumptions.map((a, i) => <span key={i} className="chip static" style={{ whiteSpace: \'normal\' }}>{a}</span>)}</div></>}\n'
        '          {r.usage_notes && <><span className="label">{t.gen.usageNotes}</span><p className="tx2" style={{ margin: 0 }}>{r.usage_notes}</p></>}\n'
        '        </details>\n'
        '      </>)}\n'
        '      {error && !failed && <p className="small" style={{ color: \'var(--color-danger)\' }}>{error}</p>}\n'
        '    </article>\n'
        '  );\n'
        '}\n'
      )),
    ),
    'apps/web/src/components/TemplateSaveModal.tsx': (
      ((
        "    try { await post('/api/templates', { title, description, body, language, default_systems: systems, tags: tags.split(',').map((x) => x.trim()).filter(Boolean).slice(0, 8) }); toast(t.templates.saved, 'ok'); onSaved?.(); onClose(); }\n"
        "    catch (e) { toast((e as ApiError).message, 'err'); } finally { setBusy(false); }\n"
        '  };\n'
        '  return <Modal title={t.gen.saveTemplate} onClose={onClose} wide footer={<><button className="btn" onClick={onClose}>{t.common.cancel}</button><button className="btn primary" disabled={busy || !title.trim() || !body.trim()} onClick={save}>{busy && <Spinner />}{t.common.save}</button></>}>\n'
        '    <div><label className="label" htmlFor="ts-title">{t.templates.titleField}</label><input id="ts-title" className="inset-field" value={title} maxLength={120} onChange={(e) => setTitle(e.target.value)} /></div>\n'
        '    <div><label className="label" htmlFor="ts-desc">{t.templates.descField}</label><input id="ts-desc" className="inset-field" value={description} maxLength={400} onChange={(e) => setDescription(e.target.value)} /></div>\n'
        '    <div><label className="label" htmlFor="ts-tags">{t.templates.tagsField}</label><input id="ts-tags" className="inset-field" value={tags} onChange={(e) => setTags(e.target.value)} /></div>\n'
        '    <div><div className="row spread"><label className="label" htmlFor="ts-body">{t.templates.bodyField}</label><button className="btn sm" onClick={generalize} disabled={gen}>{gen ? <Spinner /> : <Sparkles size={14} />}{gen ? t.templates.generalizing : t.templates.generalize}</button></div>\n'
        '      <textarea id="ts-body" className="inset-field mono" rows={10} value={body} onChange={(e) => setBody(e.target.value)} style={{ fontSize: 13 }} /></div>\n'
        '  </Modal>;\n'
        '}\n'
      ), (
        "    try { await post('/api/templates', { title, description, body, language, default_systems: systems, tags: tags.split(',').map((x) => x.trim()).filter(Boolean).slice(0, 8) }); toast(t.templates.saved, 'ok'); onSaved?.(); onClose(); }\n"
        "    catch (e) { toast((e as ApiError).message, 'err'); } finally { setBusy(false); }\n"
        '  };\n'
        '  return <Modal title={t.gen.saveTemplate} onClose={onClose} wide footer={<><button className="btn" onClick={onClose}>{t.common.cancel}</button><button className="btn primary" disabled={busy || !title.trim() || !body.trim()} onClick={save}>{busy && <Spinner />}{t.common.save}</button></>}>\n'
        '    <div><label className="label" htmlFor="ts-title">{t.templates.titleField}</label><input id="ts-title" className="field" value={title} maxLength={120} onChange={(e) => setTitle(e.target.value)} /></div>\n'
        '    <div><label className="label" htmlFor="ts-desc">{t.templates.descField}</label><input id="ts-desc" className="field" value={description} maxLength={400} onChange={(e) => setDescription(e.target.value)} /></div>\n'
        '    <div><label className="label" htmlFor="ts-tags">{t.templates.tagsField}</label><input id="ts-tags" className="field" value={tags} onChange={(e) => setTags(e.target.value)} /></div>\n'
        '    <div><div className="row spread"><label className="label" htmlFor="ts-body">{t.templates.bodyField}</label><button className="btn sm" onClick={generalize} disabled={gen}>{gen ? <Spinner /> : <Sparkles size={14} />}{gen ? t.templates.generalizing : t.templates.generalize}</button></div>\n'
        '      <textarea id="ts-body" className="field mono" rows={10} value={body} onChange={(e) => setBody(e.target.value)} style={{ fontSize: 13 }} /></div>\n'
        '  </Modal>;\n'
        '}\n'
      )),
    ),
    'apps/web/src/index.css': (
      ((
        '@tailwind utilities;\n'
        '\n'
        '/* Obsidian base. Tokens live in styles/tokens.css; nothing here may use a literal color, shadow or gradient. */\n'
        'html, body, #root { min-height: 100%; }\n'
        "body { margin: 0; background: var(--color-canvas); color: var(--color-text-primary); font-family: 'Manrope', system-ui, sans-serif; font-size: var(--font-size-body); line-height: 1.5; letter-spacing: normal; -webkit-font-smoothing: antialiased; }\n"
        'h1, h2, h3 { letter-spacing: normal; font-weight: 600; margin: 0; }\n'
        'h1 { font-size: var(--font-size-h1); line-height: 1.2; } h2 { font-size: var(--font-size-h2); line-height: 1.3; } h3 { font-size: var(--font-size-h3); line-height: 1.3; }\n'
        ".small { font-size: var(--font-size-secondary); } .tx2 { color: var(--color-text-secondary); } .tx3 { color: var(--color-text-muted); } .mono { font-family: 'JetBrains Mono', ui-monospace, monospace; }\n"
        '\n'
        '/* one shared focus ring for every focusable element */\n'
        '.lucide { stroke-width: 1.75; }\n'
        ':where(a, button, input, select, textarea, summary, [tabindex]):focus-visible { outline: 2px solid var(--color-focus); outline-offset: 2px; }\n'
        '\n'
        '/* Deprecated surface classes, remove when screens are migrated to the open canvas:\n'
        '   .glass, .glass.dense, .glass-sm, .card, .inset-field. Kept as flat re-skins so every screen stays coherent. */\n'
        '.glass { background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-xl); }\n'
        '.glass.dense { background: var(--color-surface); }\n'
        '.glass-sm { border-radius: var(--radius-md); }\n'
        '.inset-field { background: var(--color-surface-secondary); border: 1px solid var(--color-control-border); border-radius: var(--radius-md); color: var(--color-text-primary); padding: var(--space-2) var(--space-3); min-height: var(--control-height); width: 100%; font: inherit; }\n'
        '.inset-field::placeholder { color: var(--color-text-muted); }\n'
        '.inset-field:disabled { color: var(--color-text-muted); border-color: var(--color-border-strong); cursor: not-allowed; }\n'
        'textarea.inset-field { resize: none; line-height: 1.55; padding: var(--space-3); }\n'
        'select.inset-field option { background: var(--color-surface); color: var(--color-text-primary); }\n'
        '\n'
        '/* buttons */\n'
        '.btn { display: inline-flex; align-items: center; justify-content: center; gap: var(--space-2); min-height: var(--control-height); border-radius: var(--radius-md); padding: 0 var(--space-4); font-weight: 500; font-size: var(--font-size-control); line-height: 1.3; border: 1px solid var(--color-border-strong); background: var(--color-surface); color: var(--color-text-primary); cursor: pointer; transition: background var(--duration-fast) var(--ease-standard), border-color var(--duration-fast) var(--ease-standard); font-family: inherit; }\n'
        '.btn:hover:not(:disabled) { background: var(--color-surface-secondary); }\n'
      ), (
        '@tailwind utilities;\n'
        '\n'
        '/* Obsidian base. Tokens live in styles/tokens.css; nothing here may use a literal color, shadow or gradient. */\n'
        'html, body, #root { min-height: 100%; }\n'
        "body { margin: 0; overflow-wrap: anywhere; background: var(--color-canvas); color: var(--color-text-primary); font-family: 'Manrope', system-ui, sans-serif; font-size: var(--font-size-body); line-height: 1.5; letter-spacing: normal; -webkit-font-smoothing: antialiased; }\n"
        'h1, h2, h3 { letter-spacing: normal; font-weight: 600; margin: 0; }\n'
        'h1 { font-size: var(--font-size-h1); line-height: 1.2; } h2 { font-size: var(--font-size-h2); line-height: 1.3; } h3 { font-size: var(--font-size-h3); line-height: 1.3; }\n'
        ".small { font-size: var(--font-size-secondary); } .tx2 { color: var(--color-text-secondary); } .tx3 { color: var(--color-text-muted); } .mono { font-family: 'JetBrains Mono', ui-monospace, monospace; }\n"
        '\n'
        '/* one shared focus ring for every focusable element */\n'
        '.lucide { stroke-width: 1.75; }\n'
        ':where(a, button, input, select, textarea, summary, [tabindex]):focus-visible { outline: 2px solid var(--color-focus); outline-offset: 2px; }\n'
        '\n'
        '/* Shared surfaces and fields */\n'
        '.surface { background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-xl); }\n'
        '.field { background: var(--color-surface-secondary); border: 1px solid var(--color-control-border); border-radius: var(--radius-md); color: var(--color-text-primary); padding: var(--space-2) var(--space-3); min-height: var(--control-height); width: 100%; font: inherit; }\n'
        '.field::placeholder { color: var(--color-text-muted); }\n'
        '.field:disabled { color: var(--color-text-muted); border-color: var(--color-border-strong); cursor: not-allowed; }\n'
        'textarea.field { resize: none; line-height: 1.55; padding: var(--space-3); }\n'
        'select.field option { background: var(--color-surface); color: var(--color-text-primary); }\n'
        '\n'
        '/* buttons */\n'
        '.btn { display: inline-flex; align-items: center; justify-content: center; gap: var(--space-2); min-height: var(--control-height); border-radius: var(--radius-md); padding: 0 var(--space-4); font-weight: 500; font-size: var(--font-size-control); line-height: 1.3; border: 1px solid var(--color-border-strong); background: var(--color-surface); color: var(--color-text-primary); cursor: pointer; transition: background var(--duration-fast) var(--ease-standard), border-color var(--duration-fast) var(--ease-standard); font-family: inherit; }\n'
        '.btn:hover:not(:disabled) { background: var(--color-surface-secondary); }\n'
      )),
      ((
        '.sidebar.collapsed .sidebar-user { flex-direction: column; }\n'
        '.sidebar-username { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: var(--font-size-secondary); color: var(--color-text-secondary); }\n'
        '.nav-item { display: flex; align-items: center; gap: var(--space-3); min-height: var(--control-height); padding: 0 var(--space-3); border-radius: var(--radius-md); border: 1px solid transparent; background: transparent; color: var(--color-text-secondary); font-weight: 500; cursor: pointer; white-space: nowrap; font-family: inherit; font-size: var(--font-size-control); text-align: left; width: 100%; }\n'
        '.nav-item:hover { background: var(--color-surface-secondary); color: var(--color-text-primary); }\n'
        ".nav-item.on, .nav-item[aria-current='page'] { background: var(--color-surface-secondary); color: var(--color-text-primary); font-weight: 600; }\n"
        '.nav-item.status { font-size: var(--font-size-secondary); }\n'
        '.nav-new { border-color: transparent; background: var(--color-accent-soft); color: var(--color-text-primary); font-weight: 600; }\n'
        '.nav-new:hover { background: var(--color-accent-soft); border-color: var(--color-accent); }\n'
        ".nav-new.on, .nav-new[aria-current='page'] { background: var(--color-accent-soft); border-color: var(--color-accent); }\n"
      ), (
        '.sidebar.collapsed .sidebar-user { flex-direction: column; }\n'
        '.sidebar-username { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: var(--font-size-secondary); color: var(--color-text-secondary); }\n'
        '.nav-item { display: flex; align-items: center; gap: var(--space-3); min-height: var(--control-height); padding: 0 var(--space-3); border-radius: var(--radius-md); border: 1px solid transparent; background: transparent; color: var(--color-text-secondary); font-weight: 500; cursor: pointer; white-space: nowrap; font-family: inherit; font-size: var(--font-size-control); text-align: left; width: 100%; }\n'
        '.nav-item:hover { background: var(--color-surface-secondary); color: var(--color-text-primary); }\n'
        '.nav-item.on, .nav-item[aria-current] { background: var(--color-surface-secondary); color: var(--color-text-primary); font-weight: 600; }\n'
        '.nav-item.status { font-size: var(--font-size-secondary); }\n'
        '.nav-new { border-color: transparent; background: var(--color-accent-soft); color: var(--color-text-primary); font-weight: 600; }\n'
        '.nav-new:hover { background: var(--color-accent-soft); border-color: var(--color-accent); }\n'
        ".nav-new.on, .nav-new[aria-current='page'] { background: var(--color-accent-soft); border-color: var(--color-accent); }\n"
      )),
      ((
        '.bottom-tabs { position: fixed; left: 0; right: 0; bottom: 0; z-index: 6; display: none; padding: var(--space-2) var(--space-2) calc(var(--space-2) + env(safe-area-inset-bottom, 0px)); justify-content: space-around; background: var(--color-surface); border-top: 1px solid var(--color-border); }\n'
        '.bottom-tabs .nav-item { flex-direction: column; justify-content: center; gap: 2px; width: auto; min-height: 44px; padding: var(--space-1) var(--space-2); font-size: var(--font-size-meta); }\n'
        '.compact .sidebar { display: none; } .compact .bottom-tabs { display: flex; }\n'
        '.compact .main { padding: 0 var(--space-4) calc(var(--space-16) + env(safe-area-inset-bottom, 0px)); }\n'
        '.grid-cards { display: grid; gap: var(--space-4); grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); }\n'
        '.card { padding: var(--space-5); }\n'
        '.card.hover:hover { border-color: var(--color-border-strong); }\n'
        '.stagger > * { animation: rise var(--duration-fast) var(--ease-standard) both; }\n'
        '@keyframes rise { from { opacity: 0; transform: translateY(var(--space-2)); } }\n'
      ), (
        '.bottom-tabs { position: fixed; left: 0; right: 0; bottom: 0; z-index: 6; display: none; padding: var(--space-2) var(--space-2) calc(var(--space-2) + env(safe-area-inset-bottom, 0px)); justify-content: space-around; background: var(--color-surface); border-top: 1px solid var(--color-border); }\n'
        '.bottom-tabs .nav-item { flex-direction: column; justify-content: center; gap: 2px; width: auto; min-height: 44px; padding: var(--space-1) var(--space-2); font-size: var(--font-size-meta); }\n'
        '.compact .sidebar { display: none; } .compact .bottom-tabs { display: flex; }\n'
        '.compact .main { padding: 0 var(--space-4) calc(var(--space-16) + env(safe-area-inset-bottom, 0px)); }\n'
        '.grid-cards { display: grid; gap: var(--space-4); grid-template-columns: repeat(auto-fill, minmax(min(100%, var(--card-min-width)), 1fr)); }\n'
        '.card { padding: var(--space-5); }\n'
        '.card.hover:hover { border-color: var(--color-border-strong); }\n'
        '.stagger > * { animation: rise var(--duration-fast) var(--ease-standard) both; }\n'
        '@keyframes rise { from { opacity: 0; transform: translateY(var(--space-2)); } }\n'
      )),
      ((
        '@keyframes skeleton-pulse { 50% { opacity: .5; } }\n'
        '.spinner { width: 16px; height: 16px; border-radius: 50%; border: 2px solid currentColor; border-right-color: transparent; animation: spin .8s linear infinite; display: inline-block; }\n'
        '@keyframes spin { to { transform: rotate(360deg); } }\n'
        '.overlay { position: fixed; inset: 0; z-index: 50; background: var(--color-scrim); display: flex; align-items: center; justify-content: center; padding: var(--space-5); }\n'
        '.modal { width: min(560px, 100%); max-height: 90vh; overflow: auto; padding: var(--space-6); background: var(--color-elevated); box-shadow: var(--shadow-2); }\n'
        '.modal.wide { width: min(860px, 100%); }\n'
        '.drawer { position: fixed; top: 0; right: 0; bottom: 0; z-index: 51; width: min(780px, 100%); overflow: auto; padding: var(--space-6); border-radius: var(--radius-xl) 0 0 var(--radius-xl); background: var(--color-elevated); box-shadow: var(--shadow-2); animation: slide var(--duration-fast) var(--ease-standard); }\n'
        '@keyframes slide { from { transform: translateX(var(--space-8)); opacity: 0; } }\n'
        '.toasts { position: fixed; top: var(--space-4); right: var(--space-4); z-index: 60; display: flex; flex-direction: column; gap: var(--space-2); }\n'
        '.toast { padding: var(--space-3) var(--space-4); border-radius: var(--radius-lg); font-weight: 500; font-size: var(--font-size-control); max-width: 360px; animation: rise var(--duration-fast) var(--ease-standard); background: var(--color-elevated); box-shadow: var(--shadow-1); }\n'
        '.toast.err { border-color: var(--color-danger-border); } .toast.ok { border-color: var(--color-success-border); }\n'
        '.banner { padding: var(--space-3) var(--space-4); border-radius: var(--radius-md); font-size: var(--font-size-control); display: flex; align-items: center; gap: var(--space-3); border: 1px solid var(--color-border); background: var(--color-surface); margin-bottom: var(--space-4); }\n'
        '.banner.warn { background: var(--color-warning-bg); border-color: var(--color-warning-border); } .banner.err { background: var(--color-danger-bg); border-color: var(--color-danger-border); }\n'
        '.empty { text-align: center; padding: var(--space-16) var(--space-5); } .empty .glyph { font-size: 38px; color: var(--color-accent-text); }\n'
      ), (
        '@keyframes skeleton-pulse { 50% { opacity: .5; } }\n'
        '.spinner { width: 16px; height: 16px; border-radius: 50%; border: 2px solid currentColor; border-right-color: transparent; animation: spin .8s linear infinite; display: inline-block; }\n'
        '@keyframes spin { to { transform: rotate(360deg); } }\n'
        '.overlay { position: fixed; inset: 0; z-index: 50; background: var(--color-scrim); display: flex; align-items: center; justify-content: center; padding: var(--space-5); }\n'
        '.modal {\n'
        '  position: fixed;\n'
        '  inset: 0;\n'
        '  margin: auto;\n'
        '  width: min(var(--dialog-width), calc(100% - var(--space-8)));\n'
        '  max-height: min(90dvh, var(--dialog-height));\n'
        '  overflow: auto;\n'
        '  padding: var(--space-6);\n'
        '  color: var(--color-text-primary);\n'
        '  background: var(--color-elevated);\n'
        '  box-shadow: var(--shadow-2);\n'
        '}\n'
        'dialog::backdrop { background: var(--color-scrim); }\n'
        '.dialog-head { align-items: flex-start; margin-bottom: var(--space-4); }\n'
        '.dialog-footer { justify-content: flex-end; margin-top: var(--space-4); }\n'
        '.modal.wide { width: min(var(--dialog-wide-width), calc(100% - var(--space-8))); }\n'
        '.drawer { position: fixed; inset: 0 0 0 auto; margin: 0; max-width: 100%; max-height: 100%; width: min(var(--drawer-width), 100%); color: var(--color-text-primary); overflow: auto; padding: var(--space-6); border-radius: var(--radius-xl) 0 0 var(--radius-xl); background: var(--color-elevated); box-shadow: var(--shadow-2); animation: slide var(--duration-fast) var(--ease-standard); }\n'
        '@keyframes slide { from { transform: translateX(var(--space-8)); opacity: 0; } }\n'
        '.toasts { position: fixed; top: var(--space-4); right: var(--space-4); z-index: 60; display: flex; flex-direction: column; gap: var(--space-2); }\n'
        '.toast { padding: var(--space-3) var(--space-4); border-radius: var(--radius-lg); font-weight: 500; font-size: var(--font-size-control); max-width: min(var(--toast-width), calc(100vw - var(--space-8))); animation: rise var(--duration-fast) var(--ease-standard); background: var(--color-elevated); box-shadow: var(--shadow-1); }\n'
        '.toast.err { border-color: var(--color-danger-border); } .toast.ok { border-color: var(--color-success-border); }\n'
        '.banner { padding: var(--space-3) var(--space-4); border-radius: var(--radius-md); font-size: var(--font-size-control); display: flex; align-items: center; gap: var(--space-3); border: 1px solid var(--color-border); background: var(--color-surface); margin-bottom: var(--space-4); }\n'
        '.banner.warn { background: var(--color-warning-bg); border-color: var(--color-warning-border); } .banner.err { background: var(--color-danger-bg); border-color: var(--color-danger-border); }\n'
        '.empty { text-align: center; padding: var(--space-16) var(--space-5); } .empty .glyph { font-size: 38px; color: var(--color-accent-text); }\n'
      )),
      ((
        '.divider { height: 1px; background: var(--color-border); border: 0; margin: var(--space-1) 0; }\n'
        '.label { font-size: var(--font-size-meta); font-weight: 600; color: var(--color-text-muted); margin-bottom: var(--space-2); display: block; }\n'
        'details > summary { cursor: pointer; font-weight: 600; color: var(--color-text-secondary); list-style: none; } details > summary::-webkit-details-marker { display: none; } details[open] > summary { margin-bottom: var(--space-2); color: var(--color-text-primary); }\n'
        '@media (prefers-reduced-motion: reduce) { .stagger > *, .toast, .drawer { animation: none; } .chip, .btn, .icon-btn, .tab, .switch, .switch::after, .sidebar { transition: none; } .skeleton, .dot.run, .spinner { animation: none; } }\n'
      ), (
        '.divider { height: 1px; background: var(--color-border); border: 0; margin: var(--space-1) 0; }\n'
        '.label { font-size: var(--font-size-meta); font-weight: 600; color: var(--color-text-muted); margin-bottom: var(--space-2); display: block; }\n'
        'details > summary { cursor: pointer; font-weight: 600; color: var(--color-text-secondary); list-style: none; } details > summary::-webkit-details-marker { display: none; } details[open] > summary { margin-bottom: var(--space-2); color: var(--color-text-primary); }\n'
        '@media (prefers-reduced-motion: reduce) { .stagger > *, .toast, .drawer { animation: none; } .chip, .btn, .icon-btn, .tab, .switch, .switch::after, .sidebar { transition: none; } .skeleton, .dot.run, .spinner { animation: none; } }\n'
        '\n'
        '/* Components and long, user-supplied content must stay inside their tracks. */\n'
        '.row > *, .col > *, .grid-cards > *, .form-grid > *, .library-layout > * { min-inline-size: 0; }\n'
        '.btn, .chip, .tab, .seg, .field { max-inline-size: 100%; }\n'
        '.btn > svg, .chip > svg, .nav-item > svg, .icon-btn, .spinner, .switch { flex-shrink: 0; }\n'
        '.seg { flex-wrap: wrap; }\n'
        '.seg button { min-inline-size: 0; }\n'
        '.prompt-box { overflow-wrap: anywhere; word-break: normal; }\n'
        '.workflow-picker { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: var(--space-2); }\n'
        '.workflow-picker button { justify-content: center; text-align: center; }\n'
        '.form-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, var(--form-column-min)), 1fr)); gap: var(--space-4); align-items: start; }\n'
        '.score-field strong { white-space: nowrap; }\n'
        '.library-layout { display: grid; grid-template-columns: minmax(0, var(--library-sidebar-width)) minmax(0, 1fr); gap: var(--space-6); align-items: start; }\n'
        '.library-folders { gap: var(--space-1); }\n'
        '.library-folder-name { white-space: normal; }\n'
        '.md { display: flow-root; }\n'
        '.md table { display: block; max-inline-size: 100%; overflow-x: auto; }\n'
        '.md img { max-inline-size: 100%; height: auto; }\n'
        '.bottom-tabs { align-items: stretch; }\n'
        '.bottom-tabs .nav-item { flex: 1 1 0; min-width: 0; text-align: center; white-space: normal; }\n'
        '.embedded.shell { min-height: 0; }\n'
        '.embedded .sidebar { height: auto; }\n'
        '.embedded .bottom-tabs { position: static; margin-block-end: var(--space-4); }\n'
        '.embedded.compact .main { padding-bottom: var(--space-6); }\n'
        '@media (max-width: 799px) {\n'
        '  .library-layout { grid-template-columns: minmax(0, 1fr); }\n'
        '  .compact .bottom-tabs .nav-item { padding-inline: var(--space-1); }\n'
        '  .compact .modal, .compact .drawer { padding: var(--space-4); }\n'
        '  .workflow-picker { grid-template-columns: repeat(2, minmax(0, 1fr)); }\n'
        '  .shortcut { display: none; }\n'
        '}\n'
        '@media (max-width: 360px) {\n'
        '  .compact .bottom-tabs .nav-item { overflow-wrap: anywhere; }\n'
        '  .card { padding: var(--space-4); }\n'
        '}\n'
      )),
    ),
    'apps/web/src/screens/Favorites.tsx': (
      ((
        "  const unstar = async (r: Fav) => { try { await patch(`/api/results/${r.id}/favorite`, { value: false }); setItems((x) => x?.filter((i) => i.id !== r.id) ?? null); } catch (e) { toast((e as ApiError).message, 'err'); } };\n"
        '  return (\n'
        '    <div className="col" style={{ gap: 16 }}>\n'
        '      <h1>{t.favorites.title}</h1>\n'
        '      <div className="glass card row wrap" style={{ gap: 12 }}>\n'
        '        <input className="inset-field" style={{ flex: \'2 1 240px\' }} value={q} placeholder={t.common.search} aria-label={t.common.search} onChange={(e) => setQ(e.target.value)} />\n'
        '        <select className="inset-field" style={{ flex: \'1 1 150px\' }} value={system} aria-label={t.gen.systems} onChange={(e) => setSystem(e.target.value as SystemId | \'\')}><option value="">{t.common.all}</option>{Object.entries(SYSTEM_NAMES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>\n'
        '      </div>\n'
        '      {!items ? <Skeletons /> : items.length === 0 ? <Empty title={t.favorites.empty} hint={t.favorites.emptyHint} /> : (\n'
        '        <div className="grid-cards stagger">{items.map((r) => (\n'
        '          <article key={r.id} className="glass card hover col">\n'
        '            <div className="row spread"><SystemChip id={r.skill_id} /><span className="small tx3">{fmtDate(r.created_at)}</span></div>\n'
        '            <div className="prompt-box" style={{ maxHeight: 88, overflow: \'hidden\' }}>{r.prompt_text.slice(0, 260)}</div>\n'
        '            <p className="small tx3" style={{ margin: 0 }}>{r.raw_preview}</p>\n'
        '            <div className="row wrap"><CopyButton text={r.prompt_text} primary />\n'
      ), (
        "  const unstar = async (r: Fav) => { try { await patch(`/api/results/${r.id}/favorite`, { value: false }); setItems((x) => x?.filter((i) => i.id !== r.id) ?? null); } catch (e) { toast((e as ApiError).message, 'err'); } };\n"
        '  return (\n'
        '    <div className="col" style={{ gap: 16 }}>\n'
        '      <h1>{t.favorites.title}</h1>\n'
        '      <div className="surface card row wrap" style={{ gap: 12 }}>\n'
        '        <input className="field" style={{ flex: \'2 1 240px\' }} value={q} placeholder={t.common.search} aria-label={t.common.search} onChange={(e) => setQ(e.target.value)} />\n'
        '        <select className="field" style={{ flex: \'1 1 150px\' }} value={system} aria-label={t.gen.systems} onChange={(e) => setSystem(e.target.value as SystemId | \'\')}><option value="">{t.common.all}</option>{Object.entries(SYSTEM_NAMES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>\n'
        '      </div>\n'
        '      {!items ? <Skeletons /> : items.length === 0 ? <Empty title={t.favorites.empty} hint={t.favorites.emptyHint} /> : (\n'
        '        <div className="grid-cards stagger">{items.map((r) => (\n'
        '          <article key={r.id} className="surface card hover col">\n'
        '            <div className="row spread"><SystemChip id={r.skill_id} /><span className="small tx3">{fmtDate(r.created_at)}</span></div>\n'
        '            <div className="prompt-box" style={{ maxHeight: 88, overflow: \'hidden\' }}>{r.prompt_text.slice(0, 260)}</div>\n'
        '            <p className="small tx3" style={{ margin: 0 }}>{r.raw_preview}</p>\n'
        '            <div className="row wrap"><CopyButton text={r.prompt_text} primary />\n'
      )),
    ),
    'apps/web/src/screens/Generator.tsx': (
      ((
        "import { t } from '../strings.ru.ts';\n"
        "import { streamGenerate, post, patch, ApiError } from '../api.ts';\n"
        "import { useApp } from '../context.tsx';\n"
        "import { Seg, Switch, Spinner, SystemDot, useToast } from '../ui.tsx';\n"
        "import { ResultCard, groupBySystem } from '../components/ResultCard.tsx';\n"
        "import { TemplateSaveModal } from '../components/TemplateSaveModal.tsx';\n"
        '\n'
        "type CardState = { status: 'loading' | 'ok' | 'error'; variants: ResultDTO[]; error?: string };\n"
        '\n'
      ), (
        "import { t } from '../strings.ru.ts';\n"
        "import { streamGenerate, post, patch, ApiError } from '../api.ts';\n"
        "import { useApp } from '../context.tsx';\n"
        "import { Seg, Switch, Spinner, SystemDot, useToast } from '../ui.tsx';\n"
        "import { ResultCard } from '../components/ResultCard.tsx';\n"
        "import { TemplateSaveModal } from '../components/TemplateSaveModal.tsx';\n"
        '\n'
        "type CardState = { status: 'loading' | 'ok' | 'error'; variants: ResultDTO[]; error?: string };\n"
        '\n'
      )),
      ((
        '  const cmpSet = cmp.length === 2 ? cmp : done.slice(0, 2);\n'
        '\n'
        '  return (\n'
        '    <div className="col" style={{ gap: 18 }}>\n'
        '      <section className="glass card col" aria-labelledby="gen-title" style={{ padding: 24 }}>\n'
        '        <h1 id="gen-title">{t.gen.title}</h1>\n'
        '        <div><textarea ref={ta} className="inset-field" value={raw} maxLength={LIMITS.rawInputMax} placeholder={t.gen.placeholder} onChange={(e) => setRaw(e.target.value)} aria-label={t.gen.title} />\n'
        '          <div className="row spread small tx3" style={{ marginTop: 6 }}><span>{raw.length > 0 && raw.trim().length < LIMITS.rawInputMin ? t.gen.tooShort : \'\'}</span><span>{raw.length} / {LIMITS.rawInputMax} {t.gen.counter}</span></div></div>\n'
        '        <div className="row wrap" role="group" aria-label={t.gen.systems}>\n'
        '          {SYSTEM_IDS.map((id) => <button key={id} type="button" className={`chip ${systems.includes(id) ? \'on\' : \'\'}`} aria-pressed={systems.includes(id)} onClick={() => toggle(id)}><SystemDot id={id} />{SYSTEM_NAMES[id]}</button>)}\n'
        '          <button type="button" className={`chip ${allOn ? \'on\' : \'\'}`} onClick={() => setSystems([...SYSTEM_IDS])}>{t.gen.allSystems}</button>\n'
        '          <div className="grow" /><Seg label={t.gen.language} value={language} onChange={setLanguage} options={[{ value: \'ru\', label: \'RU\' }, { value: \'en\', label: \'EN\' }]} />\n'
        '        </div>\n'
        '        <div><button className="btn ghost sm" onClick={() => setAdvOpen(!advOpen)} aria-expanded={advOpen}><ChevronDown size={15} style={{ transform: advOpen ? \'rotate(180deg)\' : undefined }} />{t.gen.advanced}</button>\n'
        '          {advOpen && <div className="row wrap" style={{ marginTop: 12, gap: 18, alignItems: \'flex-end\' }}>\n'
        '            <div><label className="label" htmlFor="g-type">{t.gen.taskType}</label><select id="g-type" className="inset-field" value={opts.task_type} onChange={(e) => setOpts({ ...opts, task_type: e.target.value as GenOptions[\'task_type\'] })}>{Object.entries(t.gen.taskTypes).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></div>\n'
        '            <div><span className="label">{t.gen.detail}</span><Seg label={t.gen.detail} value={opts.detail} onChange={(v) => setOpts({ ...opts, detail: v })} options={Object.entries(t.gen.details).map(([value, label]) => ({ value: value as GenOptions[\'detail\'], label }))} /></div>\n'
        '            <div><span className="label">{t.gen.assumptions}</span><Seg label={t.gen.assumptions} value={opts.assumptions_mode} onChange={(v) => setOpts({ ...opts, assumptions_mode: v })} options={Object.entries(t.gen.modes).map(([value, label]) => ({ value: value as GenOptions[\'assumptions_mode\'], label }))} /></div>\n'
        '            <div className="row"><Switch on={opts.include_format} onChange={(v) => setOpts({ ...opts, include_format: v })} label={t.gen.includeFormat} /><span>{t.gen.includeFormat}</span></div>\n'
        '          </div>}</div>\n'
        '        <div className="row wrap"><button className="btn primary" disabled={!valid || running} onClick={submit}>{running ? <Spinner /> : <Wand2 size={17} />}{running ? stage : t.gen.submit}</button><span className="small tx3">{t.gen.hint}</span>{polling && <span className="small tx2">{t.gen.fallbackPoll}</span>}</div>\n'
        '      </section>\n'
        '\n'
        '      {questions && <section className="glass card col" aria-label={t.gen.questionsTitle}><h3>{t.gen.questionsTitle}</h3>\n'
        '        {questions.map((q, i) => <div key={i}><label className="label" htmlFor={`q${i}`}>{q}</label><input id={`q${i}`} className="inset-field" value={answers[i] ?? \'\'} placeholder={t.gen.answerPlaceholder} onChange={(e) => setAnswers(answers.map((a, j) => (j === i ? e.target.value : a)))} /></div>)}\n'
        '        <button className="btn primary" style={{ alignSelf: \'flex-start\' }} onClick={answer}>{t.gen.questionsContinue}</button></section>}\n'
        '\n'
        '      {order.length > 0 && <section className="col" aria-live="polite">\n'
        '        <div className="row wrap" role="tablist">\n'
      ), (
        '  const cmpSet = cmp.length === 2 ? cmp : done.slice(0, 2);\n'
        '\n'
        '  return (\n'
        '    <div className="col" style={{ gap: 18 }}>\n'
        '      <section className="surface card col" aria-labelledby="gen-title" style={{ padding: 24 }}>\n'
        '        <h1 id="gen-title">{t.gen.title}</h1>\n'
        '        <div><textarea ref={ta} className="field" value={raw} maxLength={LIMITS.rawInputMax} placeholder={t.gen.placeholder} onChange={(e) => setRaw(e.target.value)} aria-label={t.gen.title} />\n'
        '          <div className="row spread small tx3" style={{ marginTop: 6 }}><span>{raw.length > 0 && raw.trim().length < LIMITS.rawInputMin ? t.gen.tooShort : \'\'}</span><span>{raw.length} / {LIMITS.rawInputMax} {t.gen.counter}</span></div></div>\n'
        '        <div className="row wrap" role="group" aria-label={t.gen.systems}>\n'
        '          {SYSTEM_IDS.map((id) => <button key={id} type="button" className={`chip ${systems.includes(id) ? \'on\' : \'\'}`} aria-pressed={systems.includes(id)} onClick={() => toggle(id)}><SystemDot id={id} />{SYSTEM_NAMES[id]}</button>)}\n'
        '          <button type="button" className={`chip ${allOn ? \'on\' : \'\'}`} onClick={() => setSystems([...SYSTEM_IDS])}>{t.gen.allSystems}</button>\n'
        '          <div className="grow" /><Seg label={t.gen.language} value={language} onChange={setLanguage} options={[{ value: \'ru\', label: \'RU\' }, { value: \'en\', label: \'EN\' }]} />\n'
        '        </div>\n'
        '        <div><button className="btn ghost sm" onClick={() => setAdvOpen(!advOpen)} aria-expanded={advOpen}><ChevronDown size={15} style={{ transform: advOpen ? \'rotate(180deg)\' : undefined }} />{t.gen.advanced}</button>\n'
        '          {advOpen && <div className="row wrap" style={{ marginTop: 12, gap: 18, alignItems: \'flex-end\' }}>\n'
        '            <div><label className="label" htmlFor="g-type">{t.gen.taskType}</label><select id="g-type" className="field" value={opts.task_type} onChange={(e) => setOpts({ ...opts, task_type: e.target.value as GenOptions[\'task_type\'] })}>{Object.entries(t.gen.taskTypes).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></div>\n'
        '            <div><span className="label">{t.gen.detail}</span><Seg label={t.gen.detail} value={opts.detail} onChange={(v) => setOpts({ ...opts, detail: v })} options={Object.entries(t.gen.details).map(([value, label]) => ({ value: value as GenOptions[\'detail\'], label }))} /></div>\n'
        '            <div><span className="label">{t.gen.assumptions}</span><Seg label={t.gen.assumptions} value={opts.assumptions_mode} onChange={(v) => setOpts({ ...opts, assumptions_mode: v })} options={Object.entries(t.gen.modes).map(([value, label]) => ({ value: value as GenOptions[\'assumptions_mode\'], label }))} /></div>\n'
        '            <div className="row"><Switch on={opts.include_format} onChange={(v) => setOpts({ ...opts, include_format: v })} label={t.gen.includeFormat} /><span>{t.gen.includeFormat}</span></div>\n'
        '          </div>}</div>\n'
        '        <div className="row wrap"><button className="btn primary" disabled={!valid || running} onClick={submit}>{running ? <Spinner /> : <Wand2 size={17} />}{running ? stage : t.gen.submit}</button><span className="small tx3">{t.gen.hint}</span>{polling && <span className="small tx2">{t.gen.fallbackPoll}</span>}</div>\n'
        '      </section>\n'
        '\n'
        '      {questions && <section className="surface card col" aria-label={t.gen.questionsTitle}><h3>{t.gen.questionsTitle}</h3>\n'
        '        {questions.map((q, i) => <div key={i}><label className="label" htmlFor={`q${i}`}>{q}</label><input id={`q${i}`} className="field" value={answers[i] ?? \'\'} placeholder={t.gen.answerPlaceholder} onChange={(e) => setAnswers(answers.map((a, j) => (j === i ? e.target.value : a)))} /></div>)}\n'
        '        <button className="btn primary" style={{ alignSelf: \'flex-start\' }} onClick={answer}>{t.gen.questionsContinue}</button></section>}\n'
        '\n'
        '      {order.length > 0 && <section className="col" aria-live="polite">\n'
        '        <div className="row wrap" role="tablist">\n'
      )),
    ),
    'apps/web/src/screens/History.tsx': (
      ((
        '  const pages = data ? Math.max(1, Math.ceil(data.total / 20)) : 1;\n'
        '  return (\n'
        '    <div className="col" style={{ gap: 16 }}>\n'
        '      <h1>{t.history.title}</h1>\n'
        '      <div className="glass card row wrap" style={{ gap: 12 }}>\n'
        '        <input className="inset-field" style={{ flex: \'2 1 220px\' }} value={q} placeholder={t.history.searchPlaceholder} aria-label={t.common.search} onChange={(e) => setQ(e.target.value)} />\n'
        '        <select className="inset-field" style={{ flex: \'1 1 130px\' }} value={system} aria-label={t.gen.systems} onChange={(e) => setSystem(e.target.value as SystemId | \'\')}><option value="">{t.common.all}</option>{Object.entries(SYSTEM_NAMES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>\n'
        '        <select className="inset-field" style={{ flex: \'1 1 100px\' }} value={language} aria-label={t.history.language} onChange={(e) => setLanguage(e.target.value)}><option value="">{t.history.language}: {t.common.all}</option><option value="ru">RU</option><option value="en">EN</option></select>\n'
        '        <input className="inset-field" style={{ flex: \'1 1 140px\' }} type="date" value={from} aria-label={t.history.from} onChange={(e) => setFrom(e.target.value)} />\n'
        '        <input className="inset-field" style={{ flex: \'1 1 140px\' }} type="date" value={to} aria-label={t.history.to} onChange={(e) => setTo(e.target.value)} />\n'
        '        <label className="row small"><input type="checkbox" checked={fav} onChange={(e) => setFav(e.target.checked)} />{t.history.onlyFav}</label>\n'
        '      </div>\n'
        '      {!data ? <Skeletons /> : data.items.length === 0 ? <Empty title={t.history.empty} hint={t.history.emptyHint} cta={<button className="btn primary" onClick={() => app.go(\'generator\')}>{t.history.cta}</button>} /> : (\n'
        '        <div className="col stagger">{data.items.map((g) => (\n'
        '          <button key={g.id} className="glass card hover row wrap" style={{ textAlign: \'left\', color: \'inherit\', cursor: \'pointer\', font: \'inherit\' }} onClick={() => setOpenId(g.id)}>\n'
        '            <div className="col grow" style={{ gap: 8 }}><span className="small tx3">{fmtDate(g.created_at)}</span><span>{g.preview}</span><div className="row wrap">{g.systems.map((s) => <SystemChip key={s} id={s} />)}</div></div>\n'
        '            <span className="badge">{g.language.toUpperCase()}</span><span className="badge ok">{g.cards} {t.history.cards}</span>{g.has_favorite && <span className="badge warn">★</span>}\n'
        '          </button>))}\n'
        '          {pages > 1 && <div className="row" style={{ justifyContent: \'center\' }}><button className="btn sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>{t.common.prev}</button><span className="small tx2">{t.common.page} {page} / {pages}</span><button className="btn sm" disabled={page >= pages} onClick={() => setPage(page + 1)}>{t.common.next}</button></div>}\n'
      ), (
        '  const pages = data ? Math.max(1, Math.ceil(data.total / 20)) : 1;\n'
        '  return (\n'
        '    <div className="col" style={{ gap: 16 }}>\n'
        '      <h1>{t.history.title}</h1>\n'
        '      <div className="surface card row wrap" style={{ gap: 12 }}>\n'
        '        <input className="field" style={{ flex: \'2 1 220px\' }} value={q} placeholder={t.history.searchPlaceholder} aria-label={t.common.search} onChange={(e) => setQ(e.target.value)} />\n'
        '        <select className="field" style={{ flex: \'1 1 130px\' }} value={system} aria-label={t.gen.systems} onChange={(e) => setSystem(e.target.value as SystemId | \'\')}><option value="">{t.common.all}</option>{Object.entries(SYSTEM_NAMES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>\n'
        '        <select className="field" style={{ flex: \'1 1 100px\' }} value={language} aria-label={t.history.language} onChange={(e) => setLanguage(e.target.value)}><option value="">{t.history.language}: {t.common.all}</option><option value="ru">RU</option><option value="en">EN</option></select>\n'
        '        <input className="field" style={{ flex: \'1 1 140px\' }} type="date" value={from} aria-label={t.history.from} onChange={(e) => setFrom(e.target.value)} />\n'
        '        <input className="field" style={{ flex: \'1 1 140px\' }} type="date" value={to} aria-label={t.history.to} onChange={(e) => setTo(e.target.value)} />\n'
        '        <label className="row small"><input type="checkbox" checked={fav} onChange={(e) => setFav(e.target.checked)} />{t.history.onlyFav}</label>\n'
        '      </div>\n'
        '      {!data ? <Skeletons /> : data.items.length === 0 ? <Empty title={t.history.empty} hint={t.history.emptyHint} cta={<button className="btn primary" onClick={() => app.go(\'generator\')}>{t.history.cta}</button>} /> : (\n'
        '        <div className="col stagger">{data.items.map((g) => (\n'
        '          <button key={g.id} className="surface card hover row wrap" style={{ textAlign: \'left\', color: \'inherit\', cursor: \'pointer\', font: \'inherit\' }} onClick={() => setOpenId(g.id)}>\n'
        '            <div className="col grow" style={{ gap: 8 }}><span className="small tx3">{fmtDate(g.created_at)}</span><span>{g.preview}</span><div className="row wrap">{g.systems.map((s) => <SystemChip key={s} id={s} />)}</div></div>\n'
        '            <span className="badge">{g.language.toUpperCase()}</span><span className="badge ok">{g.cards} {t.history.cards}</span>{g.has_favorite && <span className="badge warn">★</span>}\n'
        '          </button>))}\n'
        '          {pages > 1 && <div className="row" style={{ justifyContent: \'center\' }}><button className="btn sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>{t.common.prev}</button><span className="small tx2">{t.common.page} {page} / {pages}</span><button className="btn sm" disabled={page >= pages} onClick={() => setPage(page + 1)}>{t.common.next}</button></div>}\n'
      )),
      ((
        '  const groups = g ? [...groupBySystem(g.results)] : [];\n'
        '  return (\n'
        '    <Drawer title={t.history.title} onClose={onClose}>\n'
        '      {!g ? <Skeletons n={2} h={160} /> : <div className="col">\n'
        '        <div className="glass dense card col"><span className="small tx3">{fmtDate(g.created_at)} · {g.language.toUpperCase()}</span><p style={{ margin: 0, whiteSpace: \'pre-wrap\' }}>{g.raw_input}</p>\n'
        '          <div className="row wrap"><button className="btn sm primary" onClick={() => { app.setPrefill({ raw_input: g.raw_input, systems: groups.map(([s]) => s), language: g.language, options: g.options }); onClose(); }}><RotateCcw size={15} />{t.common.reuse}</button>\n'
        '            <button className="btn sm danger" onClick={() => setConfirm(true)}><Trash2 size={15} />{t.common.delete}</button></div></div>\n'
        '        {groups.map(([s, vs]) => <ResultCard key={s} system={s} variants={vs} busy={busy === s} onFavorite={favorite} onRegenerate={regenerate} onTemplate={setTpl} />)}\n'
        '      </div>}\n'
      ), (
        '  const groups = g ? [...groupBySystem(g.results)] : [];\n'
        '  return (\n'
        '    <Drawer title={t.history.title} onClose={onClose}>\n'
        '      {!g ? <Skeletons n={2} h={160} /> : <div className="col">\n'
        '        <div className="surface card col"><span className="small tx3">{fmtDate(g.created_at)} · {g.language.toUpperCase()}</span><p style={{ margin: 0, whiteSpace: \'pre-wrap\' }}>{g.raw_input}</p>\n'
        '          <div className="row wrap"><button className="btn sm primary" onClick={() => { app.setPrefill({ raw_input: g.raw_input, systems: groups.map(([s]) => s), language: g.language, options: g.options }); onClose(); }}><RotateCcw size={15} />{t.common.reuse}</button>\n'
        '            <button className="btn sm danger" onClick={() => setConfirm(true)}><Trash2 size={15} />{t.common.delete}</button></div></div>\n'
        '        {groups.map(([s, vs]) => <ResultCard key={s} system={s} variants={vs} busy={busy === s} onFavorite={favorite} onRegenerate={regenerate} onTemplate={setTpl} />)}\n'
        '      </div>}\n'
      )),
    ),
    'apps/web/src/screens/Library.tsx': (
      ((
        "import { useCallback, useEffect, useState } from 'react';\n"
        "import { FolderPlus, Pencil, Trash2 } from 'lucide-react';\n"
        "import { OPT_WORKFLOWS, type FolderDTO, type OptWorkflow, type OptimizationDTO } from '../../../../shared/src/index.ts';\n"
        "import { t } from '../strings.ru.ts';\n"
        "import { del, get, patch, post, ApiError } from '../api.ts';\n"
        "import { useApp } from '../context.tsx';\n"
        "import { OptimizationView } from '../components/OptimizationView.tsx';\n"
      ), (
        "import { useCallback, useEffect, useRef, useState } from 'react';\n"
        "import { FolderPlus, Pencil, Trash2 } from 'lucide-react';\n"
        "import { OPT_LIMITS, OPT_WORKFLOWS, type FolderDTO, type OptWorkflow, type OptimizationDTO } from '../../../../shared/src/index.ts';\n"
        "import { t } from '../strings.ru.ts';\n"
        "import { del, get, patch, post, ApiError } from '../api.ts';\n"
        "import { useApp } from '../context.tsx';\n"
        "import { OptimizationView } from '../components/OptimizationView.tsx';\n"
      )),
      ((
        "  const [folders, setFolders] = useState<FolderDTO[]>([]); const [folder, setFolder] = useState<string>('all'); const [wf, setWf] = useState<OptWorkflow | ''>('');\n"
        "  const [q, setQ] = useState(''); const dq = useDebounced(q); const [page, setPage] = useState(1);\n"
        '  const [rows, setRows] = useState<Row[] | null>(null); const [total, setTotal] = useState(0);\n'
        "  const [open, setOpen] = useState<OptimizationDTO | null>(null); const [confirm, setConfirm] = useState<'item' | 'folder' | null>(null);\n"
        "  const [name, setName] = useState(''); const [adding, setAdding] = useState(false);\n"
        "  const fail = (e: unknown) => toast((e as ApiError).message ?? t.common.error, 'err');\n"
        "  const loadFolders = useCallback(() => get<{ items: FolderDTO[] }>('/api/optimizer/folders').then((d) => setFolders(d.items)).catch(() => {}), []);\n"
        '  const load = useCallback(() => {\n'
        "    const p = new URLSearchParams({ page: String(page) }); if (dq) p.set('q', dq); if (wf) p.set('workflow', wf);\n"
        "    if (folder === 'fav') p.set('favorites', '1'); else if (folder === 'none') p.set('folder', 'none'); else if (folder !== 'all') p.set('folder', folder);\n"
        '    return get<{ items: Row[]; total: number }>(`/api/optimizer/items?${p}`).then((d) => { setRows(d.items); setTotal(d.total); }).catch((e) => { fail(e); setRows([]); });\n'
        '  }, [page, dq, wf, folder]); // eslint-disable-line react-hooks/exhaustive-deps\n'
        '  useEffect(() => { void loadFolders(); }, [loadFolders]);\n'
        '  useEffect(() => { setPage(1); }, [dq, wf, folder]);\n'
        '  useEffect(() => { void load(); }, [load]);\n'
        '  const current = folders.find((f) => f.id === folder);\n'
        '  const openItem = async (id: string) => { try { setOpen(await get<OptimizationDTO>(`/api/optimizer/items/${id}`)); } catch (e) { fail(e); } };\n'
        '  const star = async (r: Row) => { try { await patch(`/api/optimizer/items/${r.id}`, { is_favorite: !r.is_favorite }); void load(); } catch (e) { fail(e); } };\n'
        "  const addFolder = async () => { try { const f = await post<FolderDTO>('/api/optimizer/folders', { name }); setName(''); setAdding(false); await loadFolders(); setFolder(f.id); } catch (e) { fail(e); } };\n"
        '  const rename = async () => { if (!current) return; const n = window.prompt(t.library.folderName, current.name); if (!n || n === current.name) return; try { await patch(`/api/optimizer/folders/${current.id}`, { name: n }); void loadFolders(); } catch (e) { fail(e); } };\n'
        '  const FolderBtn = ({ id, label, count }: { id: string; label: string; count?: number }) => <button className={`nav-item ${folder === id ? \'on\' : \'\'}`} aria-current={folder === id ? \'true\' : undefined} onClick={() => setFolder(id)}><span className="nav-label grow">{label}</span>{count !== undefined && <span className="small tx3">{count}</span>}</button>;\n'
        '  void app;\n'
        '  return (\n'
        '    <div className="col" style={{ gap: \'var(--space-6)\' }}>\n'
        '      <h1>{t.library.title}</h1>\n'
        '      <div className="row wrap" style={{ alignItems: \'flex-start\', gap: \'var(--space-6)\' }}>\n'
        '        <nav className="col" style={{ width: 220, gap: \'var(--space-1)\' }} aria-label={t.library.folders}>\n'
        '          <FolderBtn id="all" label={t.library.all} /><FolderBtn id="fav" label={t.library.favorites} /><FolderBtn id="none" label={t.library.unfiled} />\n'
        '          <div className="divider" />\n'
        '          {folders.map((f) => <FolderBtn key={f.id} id={f.id} label={f.name} count={f.count} />)}\n'
        '          {adding ? <div className="col" style={{ gap: \'var(--space-2)\' }}><input className="inset-field" autoFocus aria-label={t.library.folderName} placeholder={t.library.folderName} maxLength={60} value={name} onChange={(e) => setName(e.target.value)} onKeyDown={(e) => { if (e.key === \'Enter\' && name.trim()) void addFolder(); if (e.key === \'Escape\') setAdding(false); }} />\n'
        '            <div className="row"><button className="btn sm primary" disabled={!name.trim()} onClick={addFolder}>{t.common.save}</button><button className="btn sm" onClick={() => setAdding(false)}>{t.common.cancel}</button></div></div>\n'
        '            : <button className="btn sm ghost" onClick={() => setAdding(true)}><FolderPlus size={14} aria-hidden />{t.library.newFolder}</button>}\n'
        '          {current && !current.is_default && <div className="row"><button className="btn sm ghost" onClick={rename}><Pencil size={14} aria-hidden />{t.library.rename}</button><button className="btn sm ghost danger" onClick={() => setConfirm(\'folder\')}><Trash2 size={14} aria-hidden />{t.common.delete}</button></div>}\n'
        '        </nav>\n'
        '        <div className="col grow" style={{ minWidth: 280 }}>\n'
        '          <div className="row wrap">\n'
        '            <input className="inset-field grow" type="search" aria-label={t.library.search} placeholder={t.library.search} value={q} onChange={(e) => setQ(e.target.value)} />\n'
        '            <select className="inset-field" style={{ width: \'auto\' }} aria-label={t.library.workflowFilter} value={wf} onChange={(e) => setWf(e.target.value as OptWorkflow | \'\')}><option value="">{t.library.allWorkflows}</option>{OPT_WORKFLOWS.map((w) => <option key={w} value={w}>{t.opt.workflows[w]}</option>)}</select>\n'
        '          </div>\n'
        '          {rows === null ? <Skeletons /> : rows.length === 0 ? <Empty title={t.library.empty} hint={t.library.emptyHint} cta={<button className="btn primary" onClick={() => app.go(\'optimizer\')}>{t.library.cta}</button>} /> : (\n'
        '            <div className="col stagger">\n'
        '              {rows.map((r) => (\n'
        '                <div key={r.id} className="glass card col" style={{ gap: \'var(--space-2)\' }}>\n'
        '                  <div className="row spread wrap">\n'
        '                    <div className="row wrap"><span className="badge">{t.opt.workflows[r.workflow]}</span>{r.has_variables && <span className="badge info">{t.library.template}</span>}\n'
        '                      {r.optimized_score !== null && <span className="badge ok">{r.initial_score?.toFixed(1)} → {r.optimized_score.toFixed(1)}</span>}<span className="small tx3">{fmtDate(r.created_at)}</span></div>\n'
        '                    <div className="row"><StarButton on={r.is_favorite} onClick={() => star(r)} /><button className="btn sm" onClick={() => openItem(r.id)}>{t.library.open}</button></div>\n'
      ), (
        "  const [folders, setFolders] = useState<FolderDTO[]>([]); const [folder, setFolder] = useState<string>('all'); const [wf, setWf] = useState<OptWorkflow | ''>('');\n"
        "  const [q, setQ] = useState(''); const dq = useDebounced(q); const [page, setPage] = useState(1);\n"
        '  const [rows, setRows] = useState<Row[] | null>(null); const [total, setTotal] = useState(0);\n'
        "  const [open, setOpen] = useState<OptimizationDTO | null>(null); const [confirm, setConfirm] = useState<'item' | 'folder' | null>(null);\n"
        "  const [name, setName] = useState('');\n"
        "  const [editMode, setEditMode] = useState<'create' | 'rename' | null>(null);\n"
        '  const [folderBusy, setFolderBusy] = useState(false);\n'
        '  const [revision, setRevision] = useState(0);\n'
        '  const requestId = useRef(0);\n'
        '  const itemRequestId = useRef(0);\n'
        "  const fail = useCallback((e: unknown) => toast((e as ApiError).message ?? t.common.error, 'err'), [toast]);\n"
        "  const loadFolders = useCallback(() => get<{ items: FolderDTO[] }>('/api/optimizer/folders').then((d) => setFolders(d.items)).catch(() => {}), []);\n"
        '  const load = useCallback(async () => {\n'
        '    const latest = ++requestId.current;\n'
        '    const params = new URLSearchParams({ page: String(page) });\n'
        "    if (dq) params.set('q', dq);\n"
        "    if (wf) params.set('workflow', wf);\n"
        "    if (folder === 'fav') params.set('favorites', '1');\n"
        "    else if (folder !== 'all') params.set('folder', folder);\n"
        '    try {\n'
        '      const data = await get<{ items: Row[]; total: number }>(`/api/optimizer/items?${params}`);\n'
        '      if (latest !== requestId.current) return;\n'
        '      const lastPage = Math.max(1, Math.ceil(data.total / 20));\n'
        '      if (page > lastPage) { setPage(lastPage); return; }\n'
        '      setRows(data.items);\n'
        '      setTotal(data.total);\n'
        '    } catch (error) {\n'
        '      if (latest !== requestId.current) return;\n'
        '      fail(error);\n'
        '      setRows([]);\n'
        '      setTotal(0);\n'
        '    }\n'
        '  }, [page, dq, wf, folder, fail]);\n'
        '  useEffect(() => { void loadFolders(); }, [loadFolders]);\n'
        '  useEffect(() => {\n'
        '    void load();\n'
        '    return () => { requestId.current += 1; };\n'
        '  }, [load, revision]);\n'
        '  const refreshItems = () => setRevision((value) => value + 1);\n'
        '  const selectFolder = (id: string) => {\n'
        '    setEditMode(null);\n'
        '    setPage(1);\n'
        '    setFolder(id);\n'
        '  };\n'
        '  const current = folders.find((f) => f.id === folder);\n'
        '  const openItem = async (id: string) => {\n'
        '    const latest = ++itemRequestId.current;\n'
        '    try {\n'
        '      const item = await get<OptimizationDTO>(`/api/optimizer/items/${id}`);\n'
        '      if (latest === itemRequestId.current) setOpen(item);\n'
        '    } catch (error) { if (latest === itemRequestId.current) fail(error); }\n'
        '  };\n'
        '  const star = async (r: Row) => { try { await patch(`/api/optimizer/items/${r.id}`, { is_favorite: !r.is_favorite }); refreshItems(); } catch (e) { fail(e); } };\n'
        '  const saveFolder = async () => {\n'
        '    setFolderBusy(true);\n'
        '    try {\n'
        "      if (editMode === 'rename' && current) {\n"
        '        await patch(`/api/optimizer/folders/${current.id}`, { name });\n'
        "      } else if (editMode === 'create') {\n"
        "        const created = await post<FolderDTO>('/api/optimizer/folders', { name });\n"
        '        selectFolder(created.id);\n'
        '      }\n'
        '      setEditMode(null);\n'
        '      await loadFolders();\n'
        '    } catch (error) { fail(error); }\n'
        '    finally { setFolderBusy(false); }\n'
        '  };\n'
        '  const folderButton = (id: string, label: string, count?: number) => (\n'
        '    <button key={id} className="nav-item" aria-current={folder === id ? \'true\' : undefined}\n'
        '      onClick={() => selectFolder(id)}>\n'
        '      <span className="library-folder-name grow">{label}</span>{count !== undefined && <span className="small tx3">{count}</span>}\n'
        '    </button>\n'
        '  );\n'
        '  return (\n'
        '    <div className="col" style={{ gap: \'var(--space-6)\' }}>\n'
        '      <h1>{t.library.title}</h1>\n'
        '      <div className="library-layout">\n'
        '        <nav className="surface card col library-folders" aria-label={t.library.folders}>\n'
        "          {folderButton('all', t.library.all)}\n"
        "          {folderButton('fav', t.library.favorites)}\n"
        "          {folderButton('none', t.library.unfiled)}\n"
        '          <div className="divider" />\n'
        '          {folders.map((f) => folderButton(f.id, f.name, f.count))}\n'
        '          {editMode ? (\n'
        '            <form className="col" onSubmit={(event) => { event.preventDefault(); if (name.trim() && !folderBusy) void saveFolder(); }}>\n'
        '              <input className="field" autoFocus aria-label={t.library.folderName} placeholder={t.library.folderName}\n'
        '                maxLength={OPT_LIMITS.folderName} value={name} onChange={(event) => setName(event.target.value)}\n'
        "                onKeyDown={(event) => { if (event.key === 'Escape') setEditMode(null); }} />\n"
        '              <div className="row wrap">\n'
        '                <button type="submit" className="btn sm primary" disabled={!name.trim() || folderBusy}>{t.common.save}</button>\n'
        '                <button type="button" className="btn sm" disabled={folderBusy} onClick={() => setEditMode(null)}>{t.common.cancel}</button>\n'
        '              </div>\n'
        '            </form>\n'
        '          ) : (\n'
        '            <div className="row wrap">\n'
        '              <button className="btn sm ghost" onClick={() => { setName(\'\'); setEditMode(\'create\'); }}><FolderPlus size={14} aria-hidden />{t.library.newFolder}</button>\n'
        '              {current && !current.is_default && <>\n'
        '                <button className="btn sm ghost" onClick={() => { setName(current.name); setEditMode(\'rename\'); }}><Pencil size={14} aria-hidden />{t.library.rename}</button>\n'
        '                <button className="btn sm ghost danger" onClick={() => setConfirm(\'folder\')}><Trash2 size={14} aria-hidden />{t.common.delete}</button>\n'
        '              </>}\n'
        '            </div>\n'
        '          )}\n'
        '        </nav>\n'
        '        <div className="col grow">\n'
        '          <div className="row wrap">\n'
        '            <input className="field grow" type="search" aria-label={t.library.search} placeholder={t.library.search} value={q} onChange={(e) => { setPage(1); setQ(e.target.value); }} />\n'
        '            <select className="field" style={{ width: \'auto\' }} aria-label={t.library.workflowFilter} value={wf} onChange={(e) => { setPage(1); setWf(e.target.value as OptWorkflow | \'\'); }}><option value="">{t.library.allWorkflows}</option>{OPT_WORKFLOWS.map((w) => <option key={w} value={w}>{t.opt.workflows[w]}</option>)}</select>\n'
        '          </div>\n'
        '          {rows === null ? <Skeletons /> : rows.length === 0 ? <Empty title={t.library.empty} hint={t.library.emptyHint} cta={<button className="btn primary" onClick={() => app.go(\'optimizer\')}>{t.library.cta}</button>} /> : (\n'
        '            <div className="col stagger">\n'
        '              {rows.map((r) => (\n'
        '                <div key={r.id} className="surface card col" style={{ gap: \'var(--space-2)\' }}>\n'
        '                  <div className="row spread wrap">\n'
        '                    <div className="row wrap"><span className="badge">{t.opt.workflows[r.workflow]}</span>{r.has_variables && <span className="badge info">{t.library.template}</span>}\n'
        '                      {r.optimized_score !== null && <span className="badge ok">{r.initial_score?.toFixed(1)} → {r.optimized_score.toFixed(1)}</span>}<span className="small tx3">{fmtDate(r.created_at)}</span></div>\n'
        '                    <div className="row"><StarButton on={r.is_favorite} onClick={() => star(r)} /><button className="btn sm" onClick={() => openItem(r.id)}>{t.library.open}</button></div>\n'
      )),
      ((
        '            </div>\n'
        '          )}\n'
        '        </div>\n'
        '      </div>\n'
        '      {open && <Modal title={open.raw_input.slice(0, 80)} wide onClose={() => { setOpen(null); void load(); void loadFolders(); }} footer={<button className="btn danger" onClick={() => setConfirm(\'item\')}><Trash2 size={15} aria-hidden />{t.common.delete}</button>}>\n'
        '        <OptimizationView item={open} folders={folders} onChange={setOpen} /></Modal>}\n'
        "      {confirm === 'item' && open && <ConfirmModal title={t.common.delete} text={t.library.confirmDelete} danger onClose={() => setConfirm(null)} onConfirm={async () => { try { await del(`/api/optimizer/items/${open.id}`); toast(t.library.deleted, 'ok'); setOpen(null); setConfirm(null); void load(); void loadFolders(); } catch (e) { fail(e); } }} />}\n"
        "      {confirm === 'folder' && current && <ConfirmModal title={t.common.delete} text={t.library.confirmDeleteFolder} danger onClose={() => setConfirm(null)} onConfirm={async () => { try { await del(`/api/optimizer/folders/${current.id}`); setConfirm(null); setFolder('all'); void loadFolders(); void load(); } catch (e) { fail(e); } }} />}\n"
        '    </div>\n'
        '  );\n'
        '}\n'
      ), (
        '            </div>\n'
        '          )}\n'
        '        </div>\n'
        '      </div>\n'
        '      {open && <Modal title={open.raw_input.slice(0, 80)} wide onClose={() => { setOpen(null); refreshItems(); void loadFolders(); }} footer={<button className="btn danger" onClick={() => setConfirm(\'item\')}><Trash2 size={15} aria-hidden />{t.common.delete}</button>}>\n'
        '        <OptimizationView key={open.id} item={open} folders={folders} onChange={setOpen} /></Modal>}\n'
        "      {confirm === 'item' && open && <ConfirmModal title={t.common.delete} text={t.library.confirmDelete} danger onClose={() => setConfirm(null)} onConfirm={async () => { try { await del(`/api/optimizer/items/${open.id}`); toast(t.library.deleted, 'ok'); setOpen(null); setConfirm(null); refreshItems(); void loadFolders(); } catch (e) { fail(e); } }} />}\n"
        "      {confirm === 'folder' && current && <ConfirmModal title={t.common.delete} text={t.library.confirmDeleteFolder} danger onClose={() => setConfirm(null)} onConfirm={async () => { try { await del(`/api/optimizer/folders/${current.id}`); setConfirm(null); selectFolder('all'); void loadFolders(); } catch (e) { fail(e); } }} />}\n"
        '    </div>\n'
        '  );\n'
        '}\n'
      )),
    ),
    'apps/web/src/screens/Optimizer.tsx': (
      ((
        "import { Seg, Spinner, Switch, useToast } from '../ui.tsx';\n"
        '\n'
        'const store = { get: (k: string) => { try { return localStorage.getItem(k); } catch { return null; } }, set: (k: string, v: string) => { try { localStorage.setItem(k, v); } catch { /* ignore */ } } };\n'
        'const MAX_FILE = 200_000;\n'
        '\n'
        'export function OptimizerScreen() {\n'
        '  const toast = useToast(); const file = useRef<HTMLInputElement>(null);\n'
        "  const [workflow, setWorkflow] = useState<OptWorkflow>('magic');\n"
      ), (
        "import { Seg, Spinner, Switch, useToast } from '../ui.tsx';\n"
        '\n'
        'const store = { get: (k: string) => { try { return localStorage.getItem(k); } catch { return null; } }, set: (k: string, v: string) => { try { localStorage.setItem(k, v); } catch { /* ignore */ } } };\n'
        'const MAX_FILE = 200_000;\n'
        'const Chip = ({ on, label, hint, onClick }: { on: boolean; label: string; hint?: string; onClick: () => void }) => (\n'
        "  <button className={`chip ${on ? 'on' : ''}`} aria-pressed={on} title={hint} onClick={onClick}>{label}</button>\n"
        ');\n'
        '\n'
        'export function OptimizerScreen() {\n'
        '  const toast = useToast(); const file = useRef<HTMLInputElement>(null);\n'
        "  const [workflow, setWorkflow] = useState<OptWorkflow>('magic');\n"
      )),
      ((
        "  const setModeSaved = (m: 'beginner' | 'pro') => { setMode(m); store.set('opt_mode', m); };\n"
        '  const canRun = input.trim().length >= OPT_LIMITS.rawMin && !busy;\n'
        '  const run = async () => {\n'
        '    setBusy(true); setItem(null);\n'
        "    try { const r = await post<OptimizationDTO>('/api/optimizer/run', { workflow, raw_input: input.trim(), preset, output_format: format, tone, bridge }); setItem(r); setAnswers(['', '', '']); if (r.status === 'ok') toast(t.opt.saved, 'ok'); }\n"
        '    catch (e) { fail(e); } finally { setBusy(false); }\n'
        '  };\n'
        '  const answer = async (auto: boolean) => {\n'
        '    if (!item) return; setBusy(true);\n'
        "    try { const r = await post<OptimizationDTO>(`/api/optimizer/items/${item.id}/answer`, { answers: auto ? [] : answers, auto }); setItem(r); toast(t.opt.saved, 'ok'); } catch (e) { fail(e); } finally { setBusy(false); }\n"
        '  };\n'
        '  const loadFile = async (f: File) => {\n'
        "    if (f.size > MAX_FILE) { toast(t.opt.fileTooBig, 'err'); return; }\n"
        "    const text = await f.text(); if (text.length > OPT_LIMITS.rawMax) toast(t.opt.fileTruncated, 'ok');\n"
        '    setInput(text.slice(0, OPT_LIMITS.rawMax));\n'
        '  };\n'
        "  const Chip = ({ on, label, hint, onClick }: { on: boolean; label: string; hint?: string; onClick: () => void }) => <button className={`chip ${on ? 'on' : ''}`} aria-pressed={on} title={hint} onClick={onClick}>{label}</button>;\n"
        '  return (\n'
        '    <div className="col" style={{ gap: \'var(--space-6)\' }}>\n'
        '      <div><h1>{t.opt.title}</h1><p className="tx2" style={{ margin: \'var(--space-1) 0 0\' }}>{t.opt.subtitle}</p></div>\n'
        '      <div className="row wrap" role="tablist" aria-label={t.opt.title}>\n'
        '        {OPT_WORKFLOWS.map((w) => <button key={w} role="tab" aria-selected={workflow === w} className={`tab ${workflow === w ? \'on\' : \'\'}`} onClick={() => { setWorkflow(w); setItem(null); }}>{t.opt.workflows[w]}</button>)}\n'
        '      </div>\n'
        '      <section className="glass card col" aria-label={t.opt.workflows[workflow]}>\n'
        '        <p className="small tx2" style={{ margin: 0 }}>{t.opt.workflowHints[workflow]}</p>\n'
        '        <label className="label" htmlFor="opt-input">{t.opt.workflows[workflow]}</label>\n'
        '        <textarea id="opt-input" className="inset-field" rows={workflow === \'reverse\' ? 9 : 5} maxLength={OPT_LIMITS.rawMax} value={input} placeholder={t.opt.placeholders[workflow]} onChange={(e) => setInput(e.target.value)}\n'
        "          onKeyDown={(e) => { if ((e.ctrlKey || e.metaKey) && e.key === 'Enter' && canRun) void run(); }} />\n"
        '        {workflow === \'reverse\' && <div className="row wrap"><button className="btn sm" onClick={() => file.current?.click()}><Upload size={14} aria-hidden />{t.opt.fileHint}</button><span className="small tx3">{t.opt.imagesNote}</span>\n'
        '          <input ref={file} type="file" hidden accept=".txt,.md,.csv,.json,text/plain,text/markdown,application/json,text/csv" onChange={(e) => { const f = e.target.files?.[0]; if (f) void loadFile(f); e.target.value = \'\'; }} /></div>}\n'
        '        <div className="row spread wrap">\n'
      ), (
        "  const setModeSaved = (m: 'beginner' | 'pro') => { setMode(m); store.set('opt_mode', m); };\n"
        '  const canRun = input.trim().length >= OPT_LIMITS.rawMin && !busy;\n'
        '  const run = async () => {\n'
        '    setBusy(true); setItem(null);\n'
        "    try { const r = await post<OptimizationDTO>('/api/optimizer/run', { workflow, raw_input: input.trim(), preset, output_format: format, tone, bridge }); setItem(r); setAnswers(r.clarifying_questions.map(() => '')); if (r.status === 'ok') toast(t.opt.saved, 'ok'); }\n"
        '    catch (e) { fail(e); } finally { setBusy(false); }\n'
        '  };\n'
        '  const answer = async (auto: boolean) => {\n'
        '    if (!item) return; setBusy(true);\n'
        "    try { const r = await post<OptimizationDTO>(`/api/optimizer/items/${item.id}/answer`, { answers: auto ? [] : answers, auto }); setItem(r); toast(t.opt.saved, 'ok'); } catch (e) { fail(e); } finally { setBusy(false); }\n"
        '  };\n'
        '  const loadFile = async (f: File) => {\n'
        "    if (f.size > MAX_FILE) { toast(t.opt.fileTooBig, 'err'); return; }\n"
        '    try {\n'
        '      const text = await f.text();\n'
        "      if (text.length > OPT_LIMITS.rawMax) toast(t.opt.fileTruncated, 'info');\n"
        '      setInput(text.slice(0, OPT_LIMITS.rawMax));\n'
        '    } catch (error) { fail(error); }\n'
        '  };\n'
        '  return (\n'
        '    <div className="col" style={{ gap: \'var(--space-6)\' }}>\n'
        '      <div><h1>{t.opt.title}</h1><p className="tx2" style={{ margin: \'var(--space-1) 0 0\' }}>{t.opt.subtitle}</p></div>\n'
        '      <div className="workflow-picker" role="group" aria-label={t.opt.title}>\n'
        "        {OPT_WORKFLOWS.map((w) => <button key={w} aria-pressed={workflow === w} disabled={busy} className={`tab ${workflow === w ? 'on' : ''}`} onClick={() => { setWorkflow(w); setItem(null); }}>{t.opt.workflows[w]}</button>)}\n"
        '      </div>\n'
        '      <section className="surface card col" aria-label={t.opt.workflows[workflow]}>\n'
        '        <p className="small tx2" style={{ margin: 0 }}>{t.opt.workflowHints[workflow]}</p>\n'
        '        <label className="label" htmlFor="opt-input">{workflow === \'reverse\' ? t.opt.referenceLabel : t.opt.inputLabel}</label>\n'
        '        <textarea id="opt-input" className="field" rows={workflow === \'reverse\' ? 9 : 5} maxLength={OPT_LIMITS.rawMax} value={input} placeholder={t.opt.placeholders[workflow]} onChange={(e) => setInput(e.target.value)}\n'
        "          onKeyDown={(e) => { if ((e.ctrlKey || e.metaKey) && e.key === 'Enter' && canRun) void run(); }} />\n"
        '        {workflow === \'reverse\' && <div className="row wrap"><button className="btn sm" onClick={() => file.current?.click()}><Upload size={14} aria-hidden />{t.opt.fileHint}</button><span className="small tx3">{t.opt.imagesNote}</span>\n'
        '          <input ref={file} type="file" hidden accept=".txt,.md,.csv,.json,text/plain,text/markdown,application/json,text/csv" onChange={(e) => { const f = e.target.files?.[0]; if (f) void loadFile(f); e.target.value = \'\'; }} /></div>}\n'
        '        <div className="row spread wrap">\n'
      )),
      ((
        "            {mode === 'pro'\n"
        '              ? FRAMEWORK_PRESETS.map((p) => <Chip key={p} on={framework === p} label={t.opt.frameworkNames[p]} hint={t.opt.frameworkHints[p]} onClick={() => setFramework(p)} />)\n'
        '              : GOAL_PRESETS.map((p) => <Chip key={p} on={goal === p} label={t.opt.goalNames[p]} hint={t.opt.goalHints[p]} onClick={() => setGoal(goal === p ? null : p)} />)}\n'
        '          </div></div>\n'
        '        <div className="row wrap" style={{ gap: \'var(--space-6)\', alignItems: \'flex-start\' }}>\n'
        '          <div><span className="label">{t.opt.formatTitle}</span><div className="row wrap">{OUTPUT_FORMATS.map((f) => <Chip key={f} on={format === f} label={t.opt.formats[f]} onClick={() => setFormat(f)} />)}</div></div>\n'
        '          <div><span className="label">{t.opt.toneTitle}</span><div className="row wrap">{TONES.map((x) => <Chip key={x} on={tone === x} label={t.opt.tones[x]} onClick={() => setTone(x)} />)}</div></div>\n'
        '        </div>\n'
        '        <div className="row"><Switch on={bridge} onChange={setBridge} label={t.opt.bridge} /><div><span>{t.opt.bridge}</span><div className="small tx3">{t.opt.bridgeHint}</div></div></div>\n'
        '        <div className="row"><button className="btn primary" disabled={!canRun} onClick={run}>{busy ? <Spinner /> : null}{busy ? t.opt.running : t.opt.run[workflow]}</button><span className="small tx3">Ctrl+Enter</span></div>\n'
        '      </section>\n'
        "      {item?.status === 'draft_questions' && (\n"
        '        <section className="glass card col" aria-label={t.opt.questionsTitle}>\n'
        '          <h3>{t.opt.questionsTitle}</h3>\n'
        '          {item.clarifying_questions.map((q, i) => <div key={i}><label className="label" htmlFor={`q-${i}`}>{i + 1}. {q}</label>\n'
        '            <input id={`q-${i}`} className="inset-field" maxLength={OPT_LIMITS.answerMax} placeholder={t.opt.answerPlaceholder} value={answers[i] ?? \'\'} onChange={(e) => setAnswers(answers.map((a, j) => (j === i ? e.target.value : a)))} /></div>)}\n'
        '          <div className="row"><button className="btn primary" disabled={busy} onClick={() => answer(false)}>{busy ? <Spinner /> : null}{t.opt.answerContinue}</button><button className="btn" disabled={busy} onClick={() => answer(true)}>{t.opt.answerSkip}</button></div>\n'
        '        </section>\n'
        '      )}\n'
        "      {item?.status === 'ok' && <OptimizationView item={item} folders={folders} onChange={setItem} />}\n"
        '    </div>\n'
        '  );\n'
        '}\n'
      ), (
        "            {mode === 'pro'\n"
        '              ? FRAMEWORK_PRESETS.map((p) => <Chip key={p} on={framework === p} label={t.opt.frameworkNames[p]} hint={t.opt.frameworkHints[p]} onClick={() => setFramework(p)} />)\n'
        '              : GOAL_PRESETS.map((p) => <Chip key={p} on={goal === p} label={t.opt.goalNames[p]} hint={t.opt.goalHints[p]} onClick={() => setGoal(goal === p ? null : p)} />)}\n'
        '          </div></div>\n'
        '        <div className="form-grid">\n'
        '          <div><span className="label">{t.opt.formatTitle}</span><div className="row wrap">{OUTPUT_FORMATS.map((f) => <Chip key={f} on={format === f} label={t.opt.formats[f]} onClick={() => setFormat(f)} />)}</div></div>\n'
        '          <div><span className="label">{t.opt.toneTitle}</span><div className="row wrap">{TONES.map((x) => <Chip key={x} on={tone === x} label={t.opt.tones[x]} onClick={() => setTone(x)} />)}</div></div>\n'
        '        </div>\n'
        '        <div className="row"><Switch on={bridge} onChange={setBridge} label={t.opt.bridge} /><div><span>{t.opt.bridge}</span><div className="small tx3">{t.opt.bridgeHint}</div></div></div>\n'
        '        <div className="row"><button className="btn primary" disabled={!canRun} onClick={run}>{busy ? <Spinner /> : null}{busy ? t.opt.running : t.opt.run[workflow]}</button><kbd className="small tx3 shortcut">{t.opt.runShortcut}</kbd></div>\n'
        '      </section>\n'
        "      {item?.status === 'draft_questions' && (\n"
        '        <section className="surface card col" aria-label={t.opt.questionsTitle}>\n'
        '          <h3>{t.opt.questionsTitle}</h3>\n'
        '          {item.clarifying_questions.map((q, i) => <div key={i}><label className="label" htmlFor={`q-${i}`}>{i + 1}. {q}</label>\n'
        '            <input id={`q-${i}`} className="field" maxLength={OPT_LIMITS.answerMax} placeholder={t.opt.answerPlaceholder} value={answers[i] ?? \'\'} onChange={(e) => setAnswers(answers.map((a, j) => (j === i ? e.target.value : a)))} /></div>)}\n'
        '          <div className="row"><button className="btn primary" disabled={busy} onClick={() => answer(false)}>{busy ? <Spinner /> : null}{t.opt.answerContinue}</button><button className="btn" disabled={busy} onClick={() => answer(true)}>{t.opt.answerSkip}</button></div>\n'
        '        </section>\n'
        '      )}\n'
        "      {item?.status === 'ok' && <OptimizationView key={item.id} item={item} folders={folders} onChange={setItem} />}\n"
        '    </div>\n'
        '  );\n'
        '}\n'
      )),
    ),
    'apps/web/src/screens/Reports.tsx': (
      ((
        "  useEffect(() => { const p = new URLSearchParams({ page: String(page) }); if (skill) p.set('skill', skill); if (verdict) p.set('verdict', verdict); get<{ items: Report[] }>(`/api/reports?${p}`).then((d) => setItems(d.items)).catch((e) => toast((e as ApiError).message, 'err')); }, [skill, verdict, page]); // eslint-disable-line react-hooks/exhaustive-deps\n"
        '  return (\n'
        '    <div className="col" style={{ gap: 16 }}>\n'
        '      <h1>{t.reports.title}</h1>\n'
        '      <div className="glass card row wrap" style={{ gap: 12 }}>\n'
        '        <select className="inset-field" style={{ flex: \'1 1 160px\' }} value={skill} aria-label={t.gen.systems} onChange={(e) => setSkill(e.target.value)}><option value="">{t.common.all}</option>{Object.entries(SYSTEM_NAMES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>\n'
        '        <select className="inset-field" style={{ flex: \'1 1 180px\' }} value={verdict} aria-label={t.reports.allVerdicts} onChange={(e) => setVerdict(e.target.value)}><option value="">{t.reports.allVerdicts}</option>{Object.entries(t.reports.verdict).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>\n'
        '      </div>\n'
        '      {!items ? <Skeletons /> : items.length === 0 ? <Empty title={t.reports.empty} hint={t.reports.emptyHint} /> : <div className="col stagger">{items.map((r) => (\n'
        '        <article key={r.id} className="glass card col">\n'
        '          <button className="row wrap" style={{ background: \'none\', border: 0, color: \'inherit\', font: \'inherit\', textAlign: \'left\', cursor: \'pointer\', padding: 0 }} onClick={() => setOpen(open === r.id ? null : r.id)} aria-expanded={open === r.id}>\n'
        '            <SystemDot id={r.skill_id} /><strong>{SYSTEM_NAMES[r.skill_id]}</strong><span className={`badge ${tone(r.verdict)}`}>{r.verdict === \'updated\' && r.version_to ? `${t.reports.verdict.updated} → v${r.version_to}` : t.reports.verdict[r.verdict] ?? r.verdict}</span><span className="grow" /><span className="small tx3">{fmtDate(r.created_at)}</span></button>\n'
        '          <p className="tx2" style={{ margin: 0 }}>{r.summary_ru}</p>\n'
        '          {r.changelog.length > 0 && <ul className="small tx2" style={{ margin: 0, paddingLeft: 18 }}>{r.changelog.map((c, i) => <li key={i}>{c.change}</li>)}</ul>}\n'
      ), (
        "  useEffect(() => { const p = new URLSearchParams({ page: String(page) }); if (skill) p.set('skill', skill); if (verdict) p.set('verdict', verdict); get<{ items: Report[] }>(`/api/reports?${p}`).then((d) => setItems(d.items)).catch((e) => toast((e as ApiError).message, 'err')); }, [skill, verdict, page]); // eslint-disable-line react-hooks/exhaustive-deps\n"
        '  return (\n'
        '    <div className="col" style={{ gap: 16 }}>\n'
        '      <h1>{t.reports.title}</h1>\n'
        '      <div className="surface card row wrap" style={{ gap: 12 }}>\n'
        '        <select className="field" style={{ flex: \'1 1 160px\' }} value={skill} aria-label={t.gen.systems} onChange={(e) => setSkill(e.target.value)}><option value="">{t.common.all}</option>{Object.entries(SYSTEM_NAMES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>\n'
        '        <select className="field" style={{ flex: \'1 1 180px\' }} value={verdict} aria-label={t.reports.allVerdicts} onChange={(e) => setVerdict(e.target.value)}><option value="">{t.reports.allVerdicts}</option>{Object.entries(t.reports.verdict).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>\n'
        '      </div>\n'
        '      {!items ? <Skeletons /> : items.length === 0 ? <Empty title={t.reports.empty} hint={t.reports.emptyHint} /> : <div className="col stagger">{items.map((r) => (\n'
        '        <article key={r.id} className="surface card col">\n'
        '          <button className="row wrap" style={{ background: \'none\', border: 0, color: \'inherit\', font: \'inherit\', textAlign: \'left\', cursor: \'pointer\', padding: 0 }} onClick={() => setOpen(open === r.id ? null : r.id)} aria-expanded={open === r.id}>\n'
        '            <SystemDot id={r.skill_id} /><strong>{SYSTEM_NAMES[r.skill_id]}</strong><span className={`badge ${tone(r.verdict)}`}>{r.verdict === \'updated\' && r.version_to ? `${t.reports.verdict.updated} → v${r.version_to}` : t.reports.verdict[r.verdict] ?? r.verdict}</span><span className="grow" /><span className="small tx3">{fmtDate(r.created_at)}</span></button>\n'
        '          <p className="tx2" style={{ margin: 0 }}>{r.summary_ru}</p>\n'
        '          {r.changelog.length > 0 && <ul className="small tx2" style={{ margin: 0, paddingLeft: 18 }}>{r.changelog.map((c, i) => <li key={i}>{c.change}</li>)}</ul>}\n'
      )),
    ),
    'apps/web/src/screens/Settings.tsx': (
      ((
        "import { Seg, Switch, ConfirmModal, useToast } from '../ui.tsx';\n"
        "import { EngineSettings } from '../components/EngineSettings.tsx';\n"
        '\n'
        'interface Model { id: string; name: string; free: boolean; pricing: unknown }\n'
        'export function SettingsScreen() {\n'
        '  const app = useApp(); const toast = useToast(); const admin = !!app.me?.is_admin; const s = app.settings; const file = useRef<HTMLInputElement>(null);\n'
        '  const [models, setModels] = useState<Model[]>([]); const [usage, setUsage] = useState<any>(null); const [confirm, setConfirm] = useState(false);\n'
        "  useEffect(() => { get<{ items: Model[] }>('/api/models').then((d) => setModels(d.items)).catch(() => {}); get<any>('/api/usage').then(setUsage).catch(() => {}); }, []);\n"
      ), (
        "import { Seg, Switch, ConfirmModal, useToast } from '../ui.tsx';\n"
        "import { EngineSettings } from '../components/EngineSettings.tsx';\n"
        '\n'
        'interface Model { id: string; name: string; free: boolean; pricing: unknown }\n'
        'const Section = ({ title, children }: { title: string; children: React.ReactNode }) => <section className="surface card col" aria-label={title}><h3>{title}</h3>{children}</section>;\n'
        '\n'
        'export function SettingsScreen() {\n'
        '  const app = useApp(); const toast = useToast(); const admin = !!app.me?.is_admin; const s = app.settings; const file = useRef<HTMLInputElement>(null);\n'
        '  const [models, setModels] = useState<Model[]>([]); const [usage, setUsage] = useState<any>(null); const [confirm, setConfirm] = useState(false);\n'
        "  useEffect(() => { get<{ items: Model[] }>('/api/models').then((d) => setModels(d.items)).catch(() => {}); get<any>('/api/usage').then(setUsage).catch(() => {}); }, []);\n"
      )),
      ((
        "  const exportJson = async () => { const d = await post<unknown>('/api/export'); const url = URL.createObjectURL(new Blob([JSON.stringify(d, null, 2)], { type: 'application/json' })); const a = document.createElement('a'); a.href = url; a.download = 'promptolog-export.json'; a.click(); URL.revokeObjectURL(url); };\n"
        "  const importTpl = async (f: File) => { try { const j = JSON.parse(await f.text()); const r = await post<{ imported: number; errors: string[] }>('/api/import/templates', { templates: Array.isArray(j) ? j : j.templates ?? [] }); toast(`${t.settings.imported}: ${r.imported}${r.errors.length ? ` (ошибок: ${r.errors.length})` : ''}`, r.errors.length ? 'err' : 'ok'); } catch (e) { toast((e as ApiError).message || t.common.error, 'err'); } };\n"
        "  const clear = async () => { try { const r = await post<{ removed: number }>('/api/history/clear'); toast(`${t.common.delete}: ${r.removed}`, 'ok'); } catch (e) { toast((e as ApiError).message, 'err'); } };\n"
        "  const modelSelect = (id: string, value: string, key: 'transformer_model' | 'analyzer_model', label: string) => (\n"
        '    <div><label className="label" htmlFor={id}>{label}</label><select id={id} className="inset-field" disabled={!admin} value={value} onChange={(e) => save({ [key]: e.target.value })}>{[...new Set([value, ...models.map((m) => m.id)])].map((m) => <option key={m} value={m}>{m}{models.find((x) => x.id === m)?.free ? ` · ${t.settings.free}` : \'\'}</option>)}</select></div>);\n'
        "  const schedulerText = app.agent?.scheduler_mode === 'job' ? t.agent.cron : t.agent.fallback;\n"
        "  const next = app.agent?.next_check_at ? new Date(app.agent.next_check_at).toLocaleString('ru-RU') : '—';\n"
        '  const Section = ({ title, children }: { title: string; children: React.ReactNode }) => <section className="glass card col" aria-label={title}><h3>{title}</h3>{children}</section>;\n'
        '  return (\n'
        '    <div className="col" style={{ gap: 16 }}>\n'
        '      <h1>{t.settings.title}</h1>\n'
        '      {!admin && <div className="banner warn">{t.settings.adminOnly}</div>}\n'
      ), (
        "  const exportJson = async () => { const d = await post<unknown>('/api/export'); const url = URL.createObjectURL(new Blob([JSON.stringify(d, null, 2)], { type: 'application/json' })); const a = document.createElement('a'); a.href = url; a.download = 'promptolog-export.json'; a.click(); URL.revokeObjectURL(url); };\n"
        "  const importTpl = async (f: File) => { try { const j = JSON.parse(await f.text()); const r = await post<{ imported: number; errors: string[] }>('/api/import/templates', { templates: Array.isArray(j) ? j : j.templates ?? [] }); toast(`${t.settings.imported}: ${r.imported}${r.errors.length ? ` (ошибок: ${r.errors.length})` : ''}`, r.errors.length ? 'err' : 'ok'); } catch (e) { toast((e as ApiError).message || t.common.error, 'err'); } };\n"
        "  const clear = async () => { try { const r = await post<{ removed: number }>('/api/history/clear'); toast(`${t.common.delete}: ${r.removed}`, 'ok'); } catch (e) { toast((e as ApiError).message, 'err'); } };\n"
        "  const modelSelect = (id: string, value: string, key: 'transformer_model' | 'analyzer_model', label: string) => (\n"
        '    <div><label className="label" htmlFor={id}>{label}</label><select id={id} className="field" disabled={!admin} value={value} onChange={(e) => save({ [key]: e.target.value })}>{[...new Set([value, ...models.map((m) => m.id)])].map((m) => <option key={m} value={m}>{m}{models.find((x) => x.id === m)?.free ? ` · ${t.settings.free}` : \'\'}</option>)}</select></div>);\n'
        "  const schedulerText = app.agent?.scheduler_mode === 'job' ? t.agent.cron : t.agent.fallback;\n"
        "  const next = app.agent?.next_check_at ? new Date(app.agent.next_check_at).toLocaleString('ru-RU') : '—';\n"
        '  return (\n'
        '    <div className="col" style={{ gap: 16 }}>\n'
        '      <h1>{t.settings.title}</h1>\n'
        '      {!admin && <div className="banner warn">{t.settings.adminOnly}</div>}\n'
      )),
      ((
        '          <div><span className="label">{t.gen.detail}</span><Seg label={t.gen.detail} value={s.default_detail} onChange={(v) => save({ default_detail: v })} options={Object.entries(t.gen.details).map(([value, label]) => ({ value: value as Settings[\'default_detail\'], label }))} /></div>\n'
        '          <div><span className="label">{t.gen.assumptions}</span><Seg label={t.gen.assumptions} value={s.default_assumptions_mode} onChange={(v) => save({ default_assumptions_mode: v })} options={Object.entries(t.gen.modes).map(([value, label]) => ({ value: value as Settings[\'default_assumptions_mode\'], label }))} /></div>\n'
        '        </div>\n'
        '        <div><span className="label">{t.settings.defSystems}</span><div className="row wrap">{SYSTEM_IDS.map((id) => { const on = s.default_systems.includes(id); return <button key={id} className={`chip ${on ? \'on\' : \'\'}`} aria-pressed={on} disabled={!admin} onClick={() => { const next = on ? s.default_systems.filter((x) => x !== id) : [...s.default_systems, id]; if (next.length) void save({ default_systems: next }); }}>{SYSTEM_NAMES[id]}</button>; })}</div></div>\n'
        '        <div><label className="label" htmlFor="ret">{t.settings.retention}</label><input id="ret" className="inset-field" type="number" min={20} max={5000} style={{ maxWidth: 160 }} disabled={!admin} defaultValue={s.history_retention} onBlur={(e) => { const v = Number(e.target.value); if (v >= 20 && v <= 5000 && v !== s.history_retention) void save({ history_retention: v }); }} /></div>\n'
        '      </Section>\n'
        '      <Section title={t.settings.agent}>\n'
        '        <div className="row"><Switch on={s.auto_refresh_enabled} disabled={!admin} onChange={(v) => save({ auto_refresh_enabled: v })} label={t.settings.masterSwitch} /><span>{t.settings.masterSwitch}</span></div>\n'
        '        <p className="small tx2" style={{ margin: 0 }}>{t.settings.interval}</p>\n'
      ), (
        '          <div><span className="label">{t.gen.detail}</span><Seg label={t.gen.detail} value={s.default_detail} onChange={(v) => save({ default_detail: v })} options={Object.entries(t.gen.details).map(([value, label]) => ({ value: value as Settings[\'default_detail\'], label }))} /></div>\n'
        '          <div><span className="label">{t.gen.assumptions}</span><Seg label={t.gen.assumptions} value={s.default_assumptions_mode} onChange={(v) => save({ default_assumptions_mode: v })} options={Object.entries(t.gen.modes).map(([value, label]) => ({ value: value as Settings[\'default_assumptions_mode\'], label }))} /></div>\n'
        '        </div>\n'
        '        <div><span className="label">{t.settings.defSystems}</span><div className="row wrap">{SYSTEM_IDS.map((id) => { const on = s.default_systems.includes(id); return <button key={id} className={`chip ${on ? \'on\' : \'\'}`} aria-pressed={on} disabled={!admin} onClick={() => { const next = on ? s.default_systems.filter((x) => x !== id) : [...s.default_systems, id]; if (next.length) void save({ default_systems: next }); }}>{SYSTEM_NAMES[id]}</button>; })}</div></div>\n'
        '        <div><label className="label" htmlFor="ret">{t.settings.retention}</label><input id="ret" className="field" type="number" min={20} max={5000} style={{ maxWidth: 160 }} disabled={!admin} defaultValue={s.history_retention} onBlur={(e) => { const v = Number(e.target.value); if (v >= 20 && v <= 5000 && v !== s.history_retention) void save({ history_retention: v }); }} /></div>\n'
        '      </Section>\n'
        '      <Section title={t.settings.agent}>\n'
        '        <div className="row"><Switch on={s.auto_refresh_enabled} disabled={!admin} onChange={(v) => save({ auto_refresh_enabled: v })} label={t.settings.masterSwitch} /><span>{t.settings.masterSwitch}</span></div>\n'
        '        <p className="small tx2" style={{ margin: 0 }}>{t.settings.interval}</p>\n'
      )),
    ),
    'apps/web/src/screens/Skills.tsx': (
      ((
        '      <div className="row spread wrap"><h1>{t.skills.title}</h1><button className="btn" disabled={!admin} title={admin ? \'\' : t.common.noAccess} onClick={checkAll}><RefreshCw size={16} />{t.skills.refreshAll}</button></div>\n'
        '      {!items ? <Skeletons n={5} h={150} /> : <div className="grid-cards stagger">{items.map((s) => {\n'
        '        const last = daysFrom(s.last_check_at); const next = daysFrom(s.next_check_at);\n'
        "        const tip = !admin ? t.common.noAccess : s.refresh_blocked_reason === 'cooldown' ? t.skills.cooldown : s.refresh_blocked_reason === 'busy' ? t.skills.busy : '';\n"
        '        return <article key={s.id} className="glass card hover col">\n'
        '          <div className="row spread"><div className="row"><SystemDot id={s.id} /><h3>{s.display_name}</h3><span className="badge info">v{s.current_version}</span></div>\n'
        '            <span className="row small tx2"><span className={`dot ${statusDot(s.status)}`} />{t.skills.status[s.status]}</span></div>\n'
        '          <p className="small tx2" style={{ margin: 0 }}>{s.model_lineup.join(\' · \')}</p>\n'
        '          <div className="small tx3 col" style={{ gap: 2 }}><span>{t.skills.checkedAgo}: {last === null ? t.common.never : last >= 0 ? t.common.today : `${-last} ${t.skills.ago}`}</span><span>{t.skills.nextCheck}: {next === null ? \'—\' : `${t.skills.approx}${Math.max(0, next)} ${t.agent.days}`}</span></div>\n'
      ), (
        '      <div className="row spread wrap"><h1>{t.skills.title}</h1><button className="btn" disabled={!admin} title={admin ? \'\' : t.common.noAccess} onClick={checkAll}><RefreshCw size={16} />{t.skills.refreshAll}</button></div>\n'
        '      {!items ? <Skeletons n={5} h={150} /> : <div className="grid-cards stagger">{items.map((s) => {\n'
        '        const last = daysFrom(s.last_check_at); const next = daysFrom(s.next_check_at);\n'
        "        const tip = !admin ? t.common.noAccess : s.refresh_blocked_reason === 'cooldown' ? t.skills.cooldown : s.refresh_blocked_reason === 'busy' ? t.skills.busy : '';\n"
        '        return <article key={s.id} className="surface card hover col">\n'
        '          <div className="row spread"><div className="row"><SystemDot id={s.id} /><h3>{s.display_name}</h3><span className="badge info">v{s.current_version}</span></div>\n'
        '            <span className="row small tx2"><span className={`dot ${statusDot(s.status)}`} />{t.skills.status[s.status]}</span></div>\n'
        '          <p className="small tx2" style={{ margin: 0 }}>{s.model_lineup.join(\' · \')}</p>\n'
        '          <div className="small tx3 col" style={{ gap: 2 }}><span>{t.skills.checkedAgo}: {last === null ? t.common.never : last >= 0 ? t.common.today : `${-last} ${t.skills.ago}`}</span><span>{t.skills.nextCheck}: {next === null ? \'—\' : `${t.skills.approx}${Math.max(0, next)} ${t.agent.days}`}</span></div>\n'
      )),
      ((
        '  const toggleSel = (n: number) => setSel((s) => (s.includes(n) ? s.filter((x) => x !== n) : [...s, n].slice(-2)));\n'
        '  return (\n'
        '    <Drawer title={<span className="row"><SystemDot id={id} />{SYSTEM_NAMES[id]} {d && <span className="badge info">v{d.skill.current_version}</span>}</span>} onClose={onClose}>\n'
        '      {!d ? <Skeletons n={2} h={140} /> : <div className="col">\n'
        '        {d.version.changelog.length > 0 && <div className="glass dense card"><span className="label">{t.skills.changelog}</span><ul className="tx2 small" style={{ margin: 0, paddingLeft: 18 }}>{d.version.changelog.map((c, i) => <li key={i}>{c.change}</li>)}</ul></div>}\n'
        '        <div className="row wrap" role="tablist">{([\'skill\', \'versions\', \'sources\'] as const).map((k) => <button key={k} role="tab" aria-selected={tab === k} className={`tab ${tab === k ? \'on\' : \'\'}`} onClick={() => setTab(k)}>{t.skills.tabs[k]}</button>)}</div>\n'
        '        {tab === \'skill\' && <><div className="small tx3">{t.skills.lineup}: {d.skill.model_lineup.join(\' · \')}</div><Markdown md={d.version.body_md} /></>}\n'
        '        {tab === \'versions\' && <div className="col">\n'
        '          <p className="small tx3" style={{ margin: 0 }}>{t.skills.pickTwo}</p>\n'
        '          {vers.map((v) => <div key={v.id} className="glass dense card row wrap" style={{ padding: 12 }}>\n'
        '            <input type="checkbox" checked={sel.includes(v.version)} onChange={() => toggleSel(v.version)} aria-label={`${t.skills.diff} v${v.version}`} />\n'
        '            <strong>v{v.version}</strong><span className="badge">{t.skills.origin[v.origin]}</span>{v.is_current && <span className="badge ok">{t.skills.current}</span>}<span className="small tx3 grow">{fmtDate(v.created_at)}</span>\n'
        '            {!v.is_current && <button className="btn sm" disabled={!admin} title={admin ? \'\' : t.common.noAccess} onClick={() => setRb(v)}>{t.skills.rollback}</button>}</div>)}\n'
        '          {diff && <div className="prompt-box full" aria-label={`${t.skills.diff} v${diff.from} → v${diff.to}`}>{diff.parts.map((p, i) => <div key={i} className={p.added ? \'diff-add\' : p.removed ? \'diff-del\' : \'\'} style={{ opacity: !p.added && !p.removed ? 0.7 : 1 }}>{p.value.split(\'\\n\').filter((l, j, a) => j < a.length - 1 || l).map((l, j) => <div key={j}>{p.added ? \'+ \' : p.removed ? \'- \' : \'  \'}{l}</div>)}</div>)}</div>}\n'
        '        </div>}\n'
        '        {tab === \'sources\' && <div className="col">{d.version.sources.length === 0 ? <p className="tx3">—</p> : d.version.sources.map((s) => <div key={s.url} className="glass dense card" style={{ padding: 12 }}><a href={s.url} target="_blank" rel="noopener noreferrer">{s.title || s.url}</a><div className="small tx3">{new URL(s.url).hostname} · {s.checked_at}</div></div>)}</div>}\n'
        '      </div>}\n'
        '      {rb && <ConfirmModal title={`${t.skills.rollback} v${rb.version}`} text={t.skills.rollbackConfirm} onConfirm={() => rollback(rb)} onClose={() => setRb(null)} />}\n'
        '    </Drawer>\n'
        '  );\n'
      ), (
        '  const toggleSel = (n: number) => setSel((s) => (s.includes(n) ? s.filter((x) => x !== n) : [...s, n].slice(-2)));\n'
        '  return (\n'
        '    <Drawer title={<span className="row"><SystemDot id={id} />{SYSTEM_NAMES[id]} {d && <span className="badge info">v{d.skill.current_version}</span>}</span>} onClose={onClose}>\n'
        '      {!d ? <Skeletons n={2} h={140} /> : <div className="col">\n'
        '        {d.version.changelog.length > 0 && <div className="surface card"><span className="label">{t.skills.changelog}</span><ul className="tx2 small" style={{ margin: 0, paddingLeft: 18 }}>{d.version.changelog.map((c, i) => <li key={i}>{c.change}</li>)}</ul></div>}\n'
        '        <div className="row wrap" role="tablist">{([\'skill\', \'versions\', \'sources\'] as const).map((k) => <button key={k} role="tab" aria-selected={tab === k} className={`tab ${tab === k ? \'on\' : \'\'}`} onClick={() => setTab(k)}>{t.skills.tabs[k]}</button>)}</div>\n'
        '        {tab === \'skill\' && <><div className="small tx3">{t.skills.lineup}: {d.skill.model_lineup.join(\' · \')}</div><Markdown md={d.version.body_md} /></>}\n'
        '        {tab === \'versions\' && <div className="col">\n'
        '          <p className="small tx3" style={{ margin: 0 }}>{t.skills.pickTwo}</p>\n'
        '          {vers.map((v) => <div key={v.id} className="surface card row wrap" style={{ padding: 12 }}>\n'
        '            <input type="checkbox" checked={sel.includes(v.version)} onChange={() => toggleSel(v.version)} aria-label={`${t.skills.diff} v${v.version}`} />\n'
        '            <strong>v{v.version}</strong><span className="badge">{t.skills.origin[v.origin]}</span>{v.is_current && <span className="badge ok">{t.skills.current}</span>}<span className="small tx3 grow">{fmtDate(v.created_at)}</span>\n'
        '            {!v.is_current && <button className="btn sm" disabled={!admin} title={admin ? \'\' : t.common.noAccess} onClick={() => setRb(v)}>{t.skills.rollback}</button>}</div>)}\n'
        '          {diff && <div className="prompt-box full" aria-label={`${t.skills.diff} v${diff.from} → v${diff.to}`}>{diff.parts.map((p, i) => <div key={i} className={p.added ? \'diff-add\' : p.removed ? \'diff-del\' : \'\'} style={{ opacity: !p.added && !p.removed ? 0.7 : 1 }}>{p.value.split(\'\\n\').filter((l, j, a) => j < a.length - 1 || l).map((l, j) => <div key={j}>{p.added ? \'+ \' : p.removed ? \'- \' : \'  \'}{l}</div>)}</div>)}</div>}\n'
        '        </div>}\n'
        '        {tab === \'sources\' && <div className="col">{d.version.sources.length === 0 ? <p className="tx3">—</p> : d.version.sources.map((s) => <div key={s.url} className="surface card" style={{ padding: 12 }}><a href={s.url} target="_blank" rel="noopener noreferrer">{s.title || s.url}</a><div className="small tx3">{new URL(s.url).hostname} · {s.checked_at}</div></div>)}</div>}\n'
        '      </div>}\n'
        '      {rb && <ConfirmModal title={`${t.skills.rollback} v${rb.version}`} text={t.skills.rollbackConfirm} onConfirm={() => rollback(rb)} onClose={() => setRb(null)} />}\n'
        '    </Drawer>\n'
        '  );\n'
      )),
    ),
    'apps/web/src/screens/Templates.tsx': (
      ((
        "  const remove = async (tp: TemplateDTO) => { try { await del(`/api/templates/${tp.id}`); await load(); } catch (e) { toast((e as ApiError).message, 'err'); } };\n"
        '  return (\n'
        '    <div className="col" style={{ gap: 16 }}>\n'
        '      <div className="row spread wrap"><h1>{t.templates.title}</h1><button className="btn primary" onClick={() => setEditing(\'new\')}><Plus size={17} />{t.templates.new}</button></div>\n'
        '      <div className="glass card"><input className="inset-field" value={q} placeholder={t.common.search} aria-label={t.common.search} onChange={(e) => setQ(e.target.value)} /></div>\n'
        '      {!items ? <Skeletons /> : items.length === 0 ? <Empty title={t.templates.empty} hint={t.templates.emptyHint} /> : (\n'
        '        <div className="grid-cards stagger">{items.map((tp) => (\n'
        '          <article key={tp.id} className="glass card hover col" style={{ position: \'relative\' }}>\n'
        '            <div className="row spread"><h3 style={{ fontSize: 16 }}>{tp.title}</h3><div className="row">{tp.is_seed && <span className="badge info">{t.templates.seed}</span>}<span className="badge">{tp.language.toUpperCase()}</span></div></div>\n'
        '            <p className="tx2 small" style={{ margin: 0, display: \'-webkit-box\', WebkitLineClamp: 2, WebkitBoxOrient: \'vertical\', overflow: \'hidden\' }}>{tp.description || tp.body}</p>\n'
        '            <div className="row wrap">{tp.default_systems.map((s) => <SystemChip key={s} id={s} />)}</div>\n'
        '            <div className="row wrap">{tp.tags.map((x) => <span key={x} className="badge">#{x}</span>)}</div>\n'
        '            <div className="row spread"><span className="small tx3">{t.templates.used} {tp.usage_count} {t.templates.times}</span>\n'
        '              <div className="row"><button className="btn sm primary" onClick={() => setUsing(tp)}>{t.templates.use}</button>\n'
        '                <button className="icon-btn" aria-label={t.common.more} aria-haspopup="menu" aria-expanded={menu === tp.id} onClick={() => setMenu(menu === tp.id ? null : tp.id)}><MoreHorizontal size={18} /></button></div></div>\n'
        '            {menu === tp.id && <div className="glass dense col" role="menu" style={{ position: \'absolute\', right: 12, bottom: 56, padding: 8, gap: 2, zIndex: 3 }}>\n'
        '              {!tp.is_seed && <button className="nav-item" role="menuitem" onClick={() => { setMenu(null); setEditing(tp); }}>{t.common.edit}</button>}\n'
        '              <button className="nav-item" role="menuitem" onClick={() => { setMenu(null); void dup(tp); }}>{t.common.duplicate}</button>\n'
        '              {!tp.is_seed && <button className="nav-item" role="menuitem" style={{ color: \'var(--err)\' }} onClick={() => { setMenu(null); setRemoving(tp); }}>{t.common.delete}</button>}</div>}\n'
        '          </article>))}</div>)}\n'
        '      {using && <UseModal tp={using} onClose={() => setUsing(null)} onGo={(text) => { app.setPrefill({ raw_input: text, systems: using.default_systems, language: using.language }); setUsing(null); void load(); }} />}\n'
        "      {editing && <EditorModal tp={editing === 'new' ? null : editing} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); void load(); }} />}\n"
        '      {removing && <ConfirmModal title={t.common.delete} text={t.templates.confirmDelete} danger onConfirm={() => remove(removing)} onClose={() => setRemoving(null)} />}\n'
      ), (
        "  const remove = async (tp: TemplateDTO) => { try { await del(`/api/templates/${tp.id}`); await load(); } catch (e) { toast((e as ApiError).message, 'err'); } };\n"
        '  return (\n'
        '    <div className="col" style={{ gap: 16 }}>\n'
        '      <div className="row spread wrap"><h1>{t.templates.title}</h1><button className="btn primary" onClick={() => setEditing(\'new\')}><Plus size={17} />{t.templates.new}</button></div>\n'
        '      <div className="surface card"><input className="field" value={q} placeholder={t.common.search} aria-label={t.common.search} onChange={(e) => setQ(e.target.value)} /></div>\n'
        '      {!items ? <Skeletons /> : items.length === 0 ? <Empty title={t.templates.empty} hint={t.templates.emptyHint} /> : (\n'
        '        <div className="grid-cards stagger">{items.map((tp) => (\n'
        '          <article key={tp.id} className="surface card hover col" style={{ position: \'relative\' }}>\n'
        '            <div className="row spread"><h3 style={{ fontSize: 16 }}>{tp.title}</h3><div className="row">{tp.is_seed && <span className="badge info">{t.templates.seed}</span>}<span className="badge">{tp.language.toUpperCase()}</span></div></div>\n'
        '            <p className="tx2 small" style={{ margin: 0, display: \'-webkit-box\', WebkitLineClamp: 2, WebkitBoxOrient: \'vertical\', overflow: \'hidden\' }}>{tp.description || tp.body}</p>\n'
        '            <div className="row wrap">{tp.default_systems.map((s) => <SystemChip key={s} id={s} />)}</div>\n'
        '            <div className="row wrap">{tp.tags.map((x) => <span key={x} className="badge">#{x}</span>)}</div>\n'
        '            <div className="row spread"><span className="small tx3">{t.templates.used} {tp.usage_count} {t.templates.times}</span>\n'
        '              <div className="row"><button className="btn sm primary" onClick={() => setUsing(tp)}>{t.templates.use}</button>\n'
        '                <button className="icon-btn" aria-label={t.common.more} aria-haspopup="menu" aria-expanded={menu === tp.id} onClick={() => setMenu(menu === tp.id ? null : tp.id)}><MoreHorizontal size={18} /></button></div></div>\n'
        '            {menu === tp.id && <div className="surface col" role="menu" style={{ position: \'absolute\', right: 12, bottom: 56, padding: 8, gap: 2, zIndex: 3 }}>\n'
        '              {!tp.is_seed && <button className="nav-item" role="menuitem" onClick={() => { setMenu(null); setEditing(tp); }}>{t.common.edit}</button>}\n'
        '              <button className="nav-item" role="menuitem" onClick={() => { setMenu(null); void dup(tp); }}>{t.common.duplicate}</button>\n'
        '              {!tp.is_seed && <button className="nav-item" role="menuitem" style={{ color: \'var(--color-danger)\' }} onClick={() => { setMenu(null); setRemoving(tp); }}>{t.common.delete}</button>}</div>}\n'
        '          </article>))}</div>)}\n'
        '      {using && <UseModal tp={using} onClose={() => setUsing(null)} onGo={(text) => { app.setPrefill({ raw_input: text, systems: using.default_systems, language: using.language }); setUsing(null); void load(); }} />}\n'
        "      {editing && <EditorModal tp={editing === 'new' ? null : editing} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); void load(); }} />}\n"
        '      {removing && <ConfirmModal title={t.common.delete} text={t.templates.confirmDelete} danger onConfirm={() => remove(removing)} onClose={() => setRemoving(null)} />}\n'
      )),
      ((
        '  const preview = useMemo(() => substituteVariables(tp.body, values), [tp.body, values]);\n'
        "  const go = async () => { setBusy(true); try { const r = await post<{ text: string }>(`/api/templates/${tp.id}/use`, { values }); onGo(r.text); } catch (e) { toast((e as ApiError).message, 'err'); } finally { setBusy(false); } };\n"
        '  return <Modal title={`${t.templates.useTitle}: ${tp.title}`} wide onClose={onClose} footer={<><button className="btn" onClick={onClose}>{t.common.cancel}</button><button className="btn primary" disabled={busy} onClick={go}>{busy && <Spinner />}{t.templates.toGenerator}</button></>}>\n'
        '    {tp.variables.map((v) => <div key={v}><label className="label" htmlFor={`v-${v}`}>{v}</label>{/(notes|text|error|body|content)/.test(v)\n'
        '      ? <textarea id={`v-${v}`} className="inset-field" rows={4} value={values[v] ?? \'\'} onChange={(e) => setValues({ ...values, [v]: e.target.value })} />\n'
        '      : <input id={`v-${v}`} className="inset-field" value={values[v] ?? \'\'} onChange={(e) => setValues({ ...values, [v]: e.target.value })} />}</div>)}\n'
        '    <div><span className="label">{t.templates.preview}</span><div className="prompt-box">{preview}</div></div>\n'
        '  </Modal>;\n'
        '}\n'
        '\n'
      ), (
        '  const preview = useMemo(() => substituteVariables(tp.body, values), [tp.body, values]);\n'
        "  const go = async () => { setBusy(true); try { const r = await post<{ text: string }>(`/api/templates/${tp.id}/use`, { values }); onGo(r.text); } catch (e) { toast((e as ApiError).message, 'err'); } finally { setBusy(false); } };\n"
        '  return <Modal title={`${t.templates.useTitle}: ${tp.title}`} wide onClose={onClose} footer={<><button className="btn" onClick={onClose}>{t.common.cancel}</button><button className="btn primary" disabled={busy} onClick={go}>{busy && <Spinner />}{t.templates.toGenerator}</button></>}>\n'
        '    {tp.variables.map((v) => <div key={v}><label className="label" htmlFor={`v-${v}`}>{v}</label>{/(notes|text|error|body|content)/.test(v)\n'
        '      ? <textarea id={`v-${v}`} className="field" rows={4} value={values[v] ?? \'\'} onChange={(e) => setValues({ ...values, [v]: e.target.value })} />\n'
        '      : <input id={`v-${v}`} className="field" value={values[v] ?? \'\'} onChange={(e) => setValues({ ...values, [v]: e.target.value })} />}</div>)}\n'
        '    <div><span className="label">{t.templates.preview}</span><div className="prompt-box">{preview}</div></div>\n'
        '  </Modal>;\n'
        '}\n'
        '\n'
      )),
      ((
        "    try { tp ? await patch(`/api/templates/${tp.id}`, payload) : await post('/api/templates', payload); toast(t.templates.saved, 'ok'); onSaved(); } catch (e) { toast((e as ApiError).message, 'err'); } finally { setBusy(false); }\n"
        '  };\n'
        '  const mono = { fontFamily: "\'JetBrains Mono\', monospace", fontSize: 13, lineHeight: 1.6, padding: 12, whiteSpace: \'pre-wrap\' as const, wordBreak: \'break-word\' as const, border: \'1px solid transparent\' };\n'
        '  return <Modal title={t.templates.editor} wide onClose={onClose} footer={<><button className="btn" onClick={onClose}>{t.common.cancel}</button><button className="btn primary" disabled={busy || !title.trim() || !body.trim() || tooMany} onClick={save}>{busy && <Spinner />}{t.common.save}</button></>}>\n'
        '    <div><label className="label" htmlFor="e-title">{t.templates.titleField}</label><input id="e-title" className="inset-field" value={title} maxLength={120} onChange={(e) => setTitle(e.target.value)} /></div>\n'
        '    <div><label className="label" htmlFor="e-desc">{t.templates.descField}</label><input id="e-desc" className="inset-field" value={description} maxLength={400} onChange={(e) => setDescription(e.target.value)} /></div>\n'
        '    <div><label className="label" htmlFor="e-body">{t.templates.bodyField}</label>\n'
        "      <div style={{ position: 'relative', background: 'var(--inset)', borderRadius: 14, border: '1px solid var(--glass-border)' }}>\n"
        "        <div ref={bd} aria-hidden style={{ ...mono, position: 'absolute', inset: 0, overflow: 'hidden', pointerEvents: 'none', color: 'transparent' }}>{hl}{'\\n'}</div>\n"
        '        <textarea id="e-body" rows={9} value={body} onChange={(e) => setBody(e.target.value)} onScroll={(e) => { if (bd.current) bd.current.scrollTop = e.currentTarget.scrollTop; }}\n'
        "          style={{ ...mono, position: 'relative', width: '100%', background: 'transparent', color: 'var(--tx)', outline: 'none', resize: 'vertical', borderRadius: 14, display: 'block' }} /></div>\n"
        '      <div className="row wrap small" style={{ marginTop: 6 }}><span className="tx3">{t.templates.variables}:</span>{vars.map((v) => <span key={v} className="badge">{`{{${v}}}`}</span>)}{tooMany && <span style={{ color: \'var(--err)\' }}>{t.templates.maxVars}</span>}</div></div>\n'
        '    <div className="row wrap" style={{ gap: 16 }}><Seg label="language" value={language} onChange={setLanguage} options={[{ value: \'ru\', label: \'RU\' }, { value: \'en\', label: \'EN\' }]} />\n'
        '      <div className="row wrap">{SYSTEM_IDS.map((id) => <button key={id} type="button" className={`chip ${systems.includes(id) ? \'on\' : \'\'}`} aria-pressed={systems.includes(id)} onClick={() => toggle(id)}>{id}</button>)}</div></div>\n'
        '    <div><label className="label" htmlFor="e-tags">{t.templates.tagsField}</label><input id="e-tags" className="inset-field" value={tags} onChange={(e) => setTags(e.target.value)} /></div>\n'
        '  </Modal>;\n'
        '}\n'
        'void Sparkles;\n'
      ), (
        "    try { tp ? await patch(`/api/templates/${tp.id}`, payload) : await post('/api/templates', payload); toast(t.templates.saved, 'ok'); onSaved(); } catch (e) { toast((e as ApiError).message, 'err'); } finally { setBusy(false); }\n"
        '  };\n'
        '  const mono = { fontFamily: "\'JetBrains Mono\', monospace", fontSize: 13, lineHeight: 1.6, padding: 12, whiteSpace: \'pre-wrap\' as const, wordBreak: \'break-word\' as const, border: \'1px solid transparent\' };\n'
        '  return <Modal title={t.templates.editor} wide onClose={onClose} footer={<><button className="btn" onClick={onClose}>{t.common.cancel}</button><button className="btn primary" disabled={busy || !title.trim() || !body.trim() || tooMany} onClick={save}>{busy && <Spinner />}{t.common.save}</button></>}>\n'
        '    <div><label className="label" htmlFor="e-title">{t.templates.titleField}</label><input id="e-title" className="field" value={title} maxLength={120} onChange={(e) => setTitle(e.target.value)} /></div>\n'
        '    <div><label className="label" htmlFor="e-desc">{t.templates.descField}</label><input id="e-desc" className="field" value={description} maxLength={400} onChange={(e) => setDescription(e.target.value)} /></div>\n'
        '    <div><label className="label" htmlFor="e-body">{t.templates.bodyField}</label>\n'
        "      <div style={{ position: 'relative', background: 'var(--color-surface-secondary)', borderRadius: 14, border: '1px solid var(--color-border)' }}>\n"
        "        <div ref={bd} aria-hidden style={{ ...mono, position: 'absolute', inset: 0, overflow: 'hidden', pointerEvents: 'none', color: 'transparent' }}>{hl}{'\\n'}</div>\n"
        '        <textarea id="e-body" rows={9} value={body} onChange={(e) => setBody(e.target.value)} onScroll={(e) => { if (bd.current) bd.current.scrollTop = e.currentTarget.scrollTop; }}\n'
        "          style={{ ...mono, position: 'relative', width: '100%', background: 'transparent', color: 'var(--color-text-primary)', outline: 'none', resize: 'vertical', borderRadius: 14, display: 'block' }} /></div>\n"
        '      <div className="row wrap small" style={{ marginTop: 6 }}><span className="tx3">{t.templates.variables}:</span>{vars.map((v) => <span key={v} className="badge">{`{{${v}}}`}</span>)}{tooMany && <span style={{ color: \'var(--color-danger)\' }}>{t.templates.maxVars}</span>}</div></div>\n'
        '    <div className="row wrap" style={{ gap: 16 }}><Seg label="language" value={language} onChange={setLanguage} options={[{ value: \'ru\', label: \'RU\' }, { value: \'en\', label: \'EN\' }]} />\n'
        '      <div className="row wrap">{SYSTEM_IDS.map((id) => <button key={id} type="button" className={`chip ${systems.includes(id) ? \'on\' : \'\'}`} aria-pressed={systems.includes(id)} onClick={() => toggle(id)}>{id}</button>)}</div></div>\n'
        '    <div><label className="label" htmlFor="e-tags">{t.templates.tagsField}</label><input id="e-tags" className="field" value={tags} onChange={(e) => setTags(e.target.value)} /></div>\n'
        '  </Modal>;\n'
        '}\n'
        'void Sparkles;\n'
      )),
    ),
    'apps/web/src/strings.ru.ts': (
      ((
        '// All UI strings live here (i18n-ready). No literals elsewhere in components.\n'
        'export const t = {\n'
        "  appName: 'Промптолог',\n"
        "  nav: { generator: 'Генератор', history: 'История', templates: 'Шаблоны', favorites: 'Избранное', skills: 'Скиллы', reports: 'Отчёты', settings: 'Настройки', optimizer: 'Оптимизатор', library: 'Библиотека', more: 'Ещё', new: 'Новый промпт', groupWork: 'Работа', groupSystem: 'Система', collapse: 'Свернуть меню', expand: 'Развернуть меню', mainLabel: 'Главное меню', tabsLabel: 'Навигация', themeLabel: 'Тема', userFallback: 'Пользователь' },\n"
        "  analytics: { nav: 'Аналитика', title: 'Аналитика продукта', state: { restricted: 'Раздел доступен администраторам', coming: 'Раздел скоро появится' } },\n"
        "  agent: { active: 'Агент: активен', soon: 'след. проверка через', days: 'дн', paused: 'Агент на паузе', off: 'Агент выключен', fallback: 'Fallback: проверка при использовании', cron: 'Платформенный cron активен', busy: 'Агент: выполняет проверку' },\n"
        "  common: { copy: 'Копировать', copied: 'Скопировано', retry: 'Повторить', cancel: 'Отмена', save: 'Сохранить', delete: 'Удалить', close: 'Закрыть', open: 'Открыть', edit: 'Редактировать', duplicate: 'Дублировать',\n"
        "    loading: 'Загрузка…', confirm: 'Подтвердить', reuse: 'Переиспользовать', toTemplate: 'В шаблон', favorite: 'В избранное', unfavorite: 'Убрать из избранного', search: 'Поиск', all: 'Все', expand: 'Развернуть', collapse: 'Свернуть',\n"
      ), (
        '// All UI strings live here (i18n-ready). No literals elsewhere in components.\n'
        'export const t = {\n'
        "  appName: 'Промптолог',\n"
        "  nav: { optimizerShort: 'Улучшить', libraryShort: 'Папки', generator: 'Генератор', history: 'История', templates: 'Шаблоны', favorites: 'Избранное', skills: 'Скиллы', reports: 'Отчёты', settings: 'Настройки', optimizer: 'Оптимизатор', library: 'Библиотека', more: 'Ещё', new: 'Новый промпт', groupWork: 'Работа', groupSystem: 'Система', collapse: 'Свернуть меню', expand: 'Развернуть меню', mainLabel: 'Главное меню', tabsLabel: 'Навигация', themeLabel: 'Тема', userFallback: 'Пользователь' },\n"
        "  analytics: { nav: 'Аналитика', title: 'Аналитика продукта', state: { restricted: 'Раздел доступен администраторам', coming: 'Раздел скоро появится' } },\n"
        "  agent: { active: 'Агент: активен', soon: 'след. проверка через', days: 'дн', paused: 'Агент на паузе', off: 'Агент выключен', fallback: 'Fallback: проверка при использовании', cron: 'Платформенный cron активен', busy: 'Агент: выполняет проверку' },\n"
        "  common: { copy: 'Копировать', copied: 'Скопировано', retry: 'Повторить', cancel: 'Отмена', save: 'Сохранить', delete: 'Удалить', close: 'Закрыть', open: 'Открыть', edit: 'Редактировать', duplicate: 'Дублировать',\n"
        "    loading: 'Загрузка…', confirm: 'Подтвердить', reuse: 'Переиспользовать', toTemplate: 'В шаблон', favorite: 'В избранное', unfavorite: 'Убрать из избранного', search: 'Поиск', all: 'Все', expand: 'Развернуть', collapse: 'Свернуть',\n"
      )),
      ((
        "  settings: { title: 'Настройки', models: 'Модели', transformer: 'Модель-трансформер', analyzer: 'Модель-аналитик', free: 'бесплатно', usage: 'Потребление за 30 дней', defaults: 'По умолчанию', defLanguage: 'Язык', defSystems: 'Системы', agent: 'Агент обновлений',\n"
        "    masterSwitch: 'Автообновление скиллов', interval: 'Интервал: 10–15 дней, случайный график для каждого скилла', scheduler: 'Планировщик', lastRuns: 'Ближайшая проверка', checkAll: 'Проверить все сейчас', notifications: 'Уведомления', notifOn: 'Уведомлять владельца в Bitrix24',\n"
        "    notifNote: 'Если у ключа нет нужного scope, уведомления тихо отключаются.', appearance: 'Внешний вид', theme: { dark: 'Тёмная', light: 'Светлая', system: 'Системная' }, data: 'Данные', export: 'Экспорт JSON', importTpl: 'Импорт шаблонов', clear: 'Очистить историю',\n"
        "    clearConfirm: 'Все генерации, кроме избранных, будут удалены. Это нельзя отменить.', saved: 'Сохранено', adminOnly: 'Изменять настройки может только администратор', imported: 'Импортировано', retention: 'Хранить генераций', jobSecret: 'Секрет job', secretOk: 'настроен', secretMissing: 'не настроен (см. OPERATIONS.md)' },\n"
        '  opt: {\n'
        "    title: 'Оптимизатор промптов', subtitle: 'Превращает сырую мысль в точный промпт, оценивает улучшение и сохраняет в библиотеку.',\n"
        "    workflows: { magic: 'Один клик', clarify: 'Уточнение', template: 'Шаблон', reverse: 'Реверс' },\n"
        "    workflowHints: { magic: 'Вставьте запрос и нажмите кнопку: роль, структуру и ограничения система додумает сама.',\n"
        "      clarify: 'Система задаст 3 вопроса по недостающему контексту и соберёт точный промпт из ответов.',\n"
      ), (
        "  settings: { title: 'Настройки', models: 'Модели', transformer: 'Модель-трансформер', analyzer: 'Модель-аналитик', free: 'бесплатно', usage: 'Потребление за 30 дней', defaults: 'По умолчанию', defLanguage: 'Язык', defSystems: 'Системы', agent: 'Агент обновлений',\n"
        "    masterSwitch: 'Автообновление скиллов', interval: 'Интервал: 10–15 дней, случайный график для каждого скилла', scheduler: 'Планировщик', lastRuns: 'Ближайшая проверка', checkAll: 'Проверить все сейчас', notifications: 'Уведомления', notifOn: 'Уведомлять владельца в Bitrix24',\n"
        "    notifNote: 'Если у ключа нет нужного scope, уведомления тихо отключаются.', appearance: 'Внешний вид', theme: { dark: 'Тёмная', light: 'Светлая', system: 'Системная' }, data: 'Данные', export: 'Экспорт JSON', importTpl: 'Импорт шаблонов', clear: 'Очистить историю',\n"
        "    clearConfirm: 'Все генерации, кроме избранных, будут удалены. Это нельзя отменить.', saved: 'Сохранено', adminOnly: 'Изменять настройки может только администратор', imported: 'Импортировано', retention: 'Хранить генераций', jobSecret: 'Секрет job', secretOk: 'настроен', secretMissing: 'не настроен (см. OPERATIONS.md)' },\n"
        "  opt: { inputLabel: 'Ваш запрос', referenceLabel: 'Текст для разбора', runShortcut: 'Ctrl / ⌘ + Enter',\n"
        "    title: 'Оптимизатор промптов', subtitle: 'Превращает сырую мысль в точный промпт, оценивает улучшение и сохраняет в библиотеку.',\n"
        "    workflows: { magic: 'Один клик', clarify: 'Уточнение', template: 'Шаблон', reverse: 'Реверс' },\n"
        "    workflowHints: { magic: 'Вставьте запрос и нажмите кнопку: роль, структуру и ограничения система додумает сама.',\n"
        "      clarify: 'Система задаст 3 вопроса по недостающему контексту и соберёт точный промпт из ответов.',\n"
      )),
      ((
        "    toneTitle: 'Тон', tones: { none: 'Не задавать', academic: 'Академичный', persuasive: 'Убеждающий', friendly: 'Дружелюбный', concise: 'Лаконичный', no_yapping: 'Без воды' },\n"
        "    bridge: 'Мост языков: ввод RU, промпт EN, ответ RU', bridgeHint: 'Промпт будет на английском, а в конец добавится жёсткая инструкция отвечать по-русски.',\n"
        "    questionsTitle: 'Уточните три момента', answerPlaceholder: 'Ваш ответ', answerContinue: 'Продолжить', answerSkip: 'Пропустить (авто)',\n"
        "    initial: 'Исходный запрос', optimized: 'После оптимизации', scoreNote: 'Оценка модели, не измерение', changelog: 'Что изменено и зачем', finalPrompt: 'Готовый промпт', framework: 'Применено',\n"
        "    compress: 'Сжать промпт', compressing: 'Сжимаю…', compressed: 'Сжато с {a} до {b} токенов (−{p}% к стоимости API, оценка)', noGain: 'Сжатие не дало выигрыша без потери смысла: оставлен исходный промпт.',\n"
        "    showOriginal: 'Исходный', showCompressed: 'Сжатый', variables: 'Переменные', variablesHint: 'Введите значения: промпт обновится, копируется итоговый текст.',\n"
        "    saved: 'Сохранено в библиотеку', folder: 'Папка', noFolder: 'Без папки', tags: 'Теги через запятую', engine: 'Движок',\n"
        "    fileTooBig: 'Файл больше 200 КБ', fileTruncated: 'Текст обрезан до лимита', fileHint: 'Загрузить .txt / .md / .csv / .json', imagesNote: 'Изображения и документы пока не поддерживаются: вставьте текст.',\n"
        '  },\n'
        '  library: {\n'
        "    title: 'Библиотека', empty: 'Библиотека пуста', emptyHint: 'Каждая оптимизация сохраняется автоматически.', cta: 'К оптимизатору', search: 'Поиск по запросам, промптам и тегам',\n"
        "    all: 'Все', unfiled: 'Без папки', favorites: 'Избранное', folders: 'Папки', newFolder: 'Новая папка', folderName: 'Название папки', rename: 'Переименовать',\n"
        "    confirmDeleteFolder: 'Удалить папку? Промпты останутся без папки.', confirmDelete: 'Удалить промпт из библиотеки?', deleted: 'Удалено', score: 'оценка', template: 'шаблон',\n"
        "    workflowFilter: 'Сценарий', allWorkflows: 'Все сценарии', open: 'Открыть', folderExists: 'Такая папка уже есть',\n"
        '  },\n'
        '  engine: {\n'
        "    title: 'ИИ-движок оптимизатора', provider: 'Провайдер', providers: { platform: 'Платформа Bitrix24 (по умолчанию)', anthropic: 'Anthropic', openai: 'OpenAI', google: 'Google', alibaba: 'Alibaba (Qwen)', moonshot: 'Moonshot AI (Kimi)', custom: 'Свой (OpenAI-совместимый)' },\n"
        "    model: 'Модель', customModel: 'Своя модель (ID)', baseUrl: 'Custom Base URL', baseUrlHint: 'Только https. Внутренние адреса запрещены.', temperature: 'Температура', apiKey: 'Ключ API', apiKeyKept: 'Ключ сохранён', apiKeyNew: 'Введите новый ключ', apiKeyClear: 'Удалить ключ',\n"
        "    secretMissing: 'ENGINE_SECRET не задан на сервере: ключи API сохранять нельзя.', unverified: 'ID модели не проверен по документации провайдера', save: 'Сохранить движок', test: 'Проверить соединение', testOk: 'Соединение работает', ms: 'мс',\n"
        "    adminOnly: 'Менять движок может только администратор', note: 'Ключ хранится на сервере в зашифрованном виде и не возвращается в браузер.',\n"
        '  },\n'
        "  empty: { glyph: '✦' },\n"
        '} as const;\n'
      ), (
        "    toneTitle: 'Тон', tones: { none: 'Не задавать', academic: 'Академичный', persuasive: 'Убеждающий', friendly: 'Дружелюбный', concise: 'Лаконичный', no_yapping: 'Без воды' },\n"
        "    bridge: 'Мост языков: ввод RU, промпт EN, ответ RU', bridgeHint: 'Промпт будет на английском, а в конец добавится жёсткая инструкция отвечать по-русски.',\n"
        "    questionsTitle: 'Уточните три момента', answerPlaceholder: 'Ваш ответ', answerContinue: 'Продолжить', answerSkip: 'Пропустить (авто)',\n"
        "    initial: 'Исходный запрос', optimized: 'После оптимизации', scoreNote: 'Оценка модели, не измерение', changelog: 'Что изменено и зачем', finalPrompt: 'Готовый промпт', framework: 'Применено',\n"
        "    compress: 'Сжать промпт', compressing: 'Сжимаю…', compressed: 'Примерно {a} → {b} токенов (−{p}%)', noGain: 'Более короткий вариант с теми же переменными получить не удалось.',\n"
        "    showOriginal: 'Исходный', showCompressed: 'Сжатый', variables: 'Переменные', variablesHint: 'Введите значения: промпт обновится, копируется итоговый текст.',\n"
        "    saved: 'Сохранено в библиотеку', folder: 'Папка', noFolder: 'Без папки', tags: 'Теги через запятую', engine: 'Движок',\n"
        "    fileTooBig: 'Файл больше 200 КБ', fileTruncated: 'Текст обрезан до лимита', fileHint: 'Загрузить .txt / .md / .csv / .json', imagesNote: 'Изображения и документы пока не поддерживаются: вставьте текст.',\n"
        '  },\n'
        '  library: {\n'
        "    title: 'Библиотека', empty: 'Библиотека пуста', emptyHint: 'Каждая оптимизация сохраняется автоматически.', cta: 'К оптимизатору', search: 'Поиск по запросам, промптам и тегам',\n"
        "    all: 'Все', unfiled: 'Без папки', favorites: 'Избранное', folders: 'Папки', newFolder: 'Новая папка', folderName: 'Название папки', rename: 'Переименовать',\n"
        "    confirmDeleteFolder: 'Удалить папку? Промпты останутся без папки.', confirmDelete: 'Удалить промпт из библиотеки?', deleted: 'Удалено', template: 'шаблон',\n"
        "    workflowFilter: 'Сценарий', allWorkflows: 'Все сценарии', open: 'Открыть',\n"
        '  },\n'
        "  engine: { keyDestinationChanged: 'При смене адреса или провайдера введите новый ключ. Сохранённый ключ будет удалён.', loadError: 'Не удалось загрузить настройки движка. Откройте настройки снова.',\n"
        "    title: 'ИИ-движок оптимизатора', provider: 'Провайдер', providers: { platform: 'Платформа Bitrix24 (по умолчанию)', anthropic: 'Anthropic', openai: 'OpenAI', google: 'Google', alibaba: 'Alibaba (Qwen)', moonshot: 'Moonshot AI (Kimi)', custom: 'Свой (OpenAI-совместимый)' },\n"
        "    model: 'Модель', customModel: 'Своя модель (ID)', baseUrl: 'Custom Base URL', baseUrlHint: 'Только https. Внутренние адреса запрещены.', temperature: 'Температура', apiKey: 'Ключ API', apiKeyKept: 'Ключ сохранён', apiKeyNew: 'Введите новый ключ', apiKeyClear: 'Удалить ключ',\n"
        "    secretMissing: 'ENGINE_SECRET не задан на сервере: ключи API сохранять нельзя.', save: 'Сохранить движок', test: 'Проверить сохранённое подключение', testOk: 'Соединение работает', ms: 'мс',\n"
        "    adminOnly: 'Менять движок может только администратор', note: 'Ключ хранится на сервере в зашифрованном виде и не возвращается в браузер.',\n"
        '  },\n'
        "  empty: { glyph: '✦' },\n"
        '} as const;\n'
      )),
    ),
    'apps/web/src/styles/tokens.css': (
      ((
        '  --duration-fast: 150ms;\n'
        '  --ease-standard: cubic-bezier(0.2, 0, 0, 1);\n'
        '\n'
        '  /* layout and density */\n'
        '  --sidebar-width: 280px;\n'
        '  --sidebar-width-collapsed: 64px;\n'
        '  --control-height: 32px;\n'
        '  --control-height-sm: 28px;\n'
      ), (
        '  --duration-fast: 150ms;\n'
        '  --ease-standard: cubic-bezier(0.2, 0, 0, 1);\n'
        '\n'
        '  /* layout and density */\n'
        '  --card-min-width: 300px;\n'
        '  --form-column-min: 200px;\n'
        '  --library-sidebar-width: 220px;\n'
        '  --dialog-width: 560px;\n'
        '  --dialog-wide-width: 860px;\n'
        '  --dialog-height: 800px;\n'
        '  --drawer-width: 780px;\n'
        '  --toast-width: 360px;\n'
        '  --sidebar-width: 280px;\n'
        '  --sidebar-width-collapsed: 64px;\n'
        '  --control-height: 32px;\n'
        '  --control-height-sm: 28px;\n'
      )),
      ((
        '  --status-success: var(--color-success-text);\n'
        '  --status-warning: var(--color-warning);\n'
        '  --status-error: var(--color-danger);\n'
        '\n'
        '  /* deprecated alias, remove when screens are migrated */\n'
        '  --bg: var(--color-canvas);\n'
        '  --glass: var(--color-surface);\n'
        '  --glass-strong: var(--color-surface-secondary);\n'
        '  --solid2: var(--color-surface-secondary);\n'
        '  --inset: var(--color-surface-secondary);\n'
        '  --solid: var(--color-surface);\n'
        '  --glass-border: var(--color-border);\n'
        '  --glass-hi: none;\n'
        '  --glass-shadow: none;\n'
        '  --tx: var(--color-text-primary);\n'
        '  --tx2: var(--color-text-secondary);\n'
        '  --tx3: var(--color-text-muted);\n'
        '  --accent1: var(--color-accent);\n'
        '  --accent2: var(--color-accent);\n'
        '  --ok: var(--color-success-text);\n'
        '  --warn: var(--color-warning);\n'
        '  --err: var(--color-danger);\n'
        '  --info: var(--color-text-secondary);\n'
        '  --diff-add: var(--color-success-bg);\n'
        '  --diff-del: var(--color-danger-bg);\n'
        '}\n'
        '\n'
        ":root[data-theme='dark'] {\n"
        '  color-scheme: dark;\n'
      ), (
        '  --status-success: var(--color-success-text);\n'
        '  --status-warning: var(--color-warning);\n'
        '  --status-error: var(--color-danger);\n'
        '\n'
        '}\n'
        '\n'
        ":root[data-theme='dark'] {\n"
        '  color-scheme: dark;\n'
      )),
    ),
    'apps/web/src/ui.tsx': (
      ((
        "import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react';\n"
        "import { Check, Copy, X, Star } from 'lucide-react';\n"
        "import { marked } from 'marked';\n"
        "import DOMPurify from 'dompurify';\n"
        "import { SYSTEM_NAMES, type SystemId } from '../../../shared/src/index.ts';\n"
        "import { t } from './strings.ru.ts';\n"
        '\n'
        "export const SYSTEM_COLORS: Record<SystemId, string> = { claude: 'var(--color-system-claude)', chatgpt: 'var(--color-system-chatgpt)', kimi: 'var(--color-system-kimi)', qwen: 'var(--color-system-qwen)', grok: 'var(--color-system-grok)' };\n"
        'export const SystemDot = ({ id }: { id: SystemId }) => <span className="dot" style={{ background: SYSTEM_COLORS[id] }} aria-hidden />;\n'
        'export const SystemChip = ({ id }: { id: SystemId }) => <span className="chip static"><SystemDot id={id} />{SYSTEM_NAMES[id]}</span>;\n'
        '\n'
        '// ---- toasts ----\n'
      ), (
        "import { createContext, useCallback, useContext, useEffect, useId, useRef, useState, type ReactNode } from 'react';\n"
        "import { Check, Copy, X, Star } from 'lucide-react';\n"
        "import { marked } from 'marked';\n"
        "import DOMPurify from 'dompurify';\n"
        "import { SYSTEM_NAMES, type SystemId } from '../../../shared/src/index.ts';\n"
        "import { t } from './strings.ru.ts';\n"
        '\n'
        "const SYSTEM_COLORS: Record<SystemId, string> = { claude: 'var(--color-system-claude)', chatgpt: 'var(--color-system-chatgpt)', kimi: 'var(--color-system-kimi)', qwen: 'var(--color-system-qwen)', grok: 'var(--color-system-grok)' };\n"
        'export const SystemDot = ({ id }: { id: SystemId }) => <span className="dot" style={{ background: SYSTEM_COLORS[id] }} aria-hidden />;\n'
        'export const SystemChip = ({ id }: { id: SystemId }) => <span className="chip static"><SystemDot id={id} />{SYSTEM_NAMES[id]}</span>;\n'
        '\n'
        '// ---- toasts ----\n'
      )),
      ((
        "  const push = useCallback((text: string, kind: ToastItem['kind'] = 'info') => {\n"
        '    const id = ++n.current; setItems((x) => [...x, { id, text, kind }]);\n'
        '    setTimeout(() => setItems((x) => x.filter((i) => i.id !== id)), 3500);\n'
        '  }, []);\n'
        '  return <ToastCtx.Provider value={push}>{children}<div className="toasts" role="status" aria-live="polite">{items.map((i) => <div key={i.id} className={`toast glass ${i.kind}`}>{i.text}</div>)}</div></ToastCtx.Provider>;\n'
        '}\n'
        '\n'
        '// ---- clipboard with fallback (iframes may block navigator.clipboard) ----\n'
        'export async function copyText(text: string): Promise<boolean> {\n'
        '  try { await navigator.clipboard.writeText(text); return true; } catch { /* fall through */ }\n'
        '  try {\n'
        "    const ta = document.createElement('textarea'); ta.value = text; ta.style.position = 'fixed'; ta.style.opacity = '0'; document.body.appendChild(ta); ta.select();\n"
        "    const ok = document.execCommand('copy'); document.body.removeChild(ta); return ok;\n"
        '  } catch { return false; }\n'
        '}\n'
        'export function CopyButton({ text, label = t.common.copy, primary = false }: { text: string; label?: string; primary?: boolean }) {\n'
        '  const [done, setDone] = useState(false); const toast = useToast();\n'
      ), (
        "  const push = useCallback((text: string, kind: ToastItem['kind'] = 'info') => {\n"
        '    const id = ++n.current; setItems((x) => [...x, { id, text, kind }]);\n'
        '    setTimeout(() => setItems((x) => x.filter((i) => i.id !== id)), 3500);\n'
        '  }, []);\n'
        '  return <ToastCtx.Provider value={push}>{children}<div className="toasts" role="status" aria-live="polite">{items.map((i) => <div key={i.id} className={`toast surface ${i.kind}`}>{i.text}</div>)}</div></ToastCtx.Provider>;\n'
        '}\n'
        '\n'
        '// ---- clipboard with fallback (iframes may block navigator.clipboard) ----\n'
        'export async function copyText(text: string): Promise<boolean> {\n'
        '  try { await navigator.clipboard.writeText(text); return true; } catch { /* fall through */ }\n'
        '  try {\n'
        '    const previous = document.activeElement;\n'
        "    const ta = document.createElement('textarea');\n"
        '    ta.value = text;\n'
        "    ta.style.position = 'fixed';\n"
        "    ta.style.opacity = '0';\n"
        "    (previous?.closest('dialog') ?? document.body).appendChild(ta);\n"
        '    ta.select();\n'
        "    try { return document.execCommand('copy'); }\n"
        '    finally { ta.remove(); if (previous instanceof HTMLElement) previous.focus({ preventScroll: true }); }\n'
        '  } catch { return false; }\n'
        '}\n'
        'export function CopyButton({ text, label = t.common.copy, primary = false }: { text: string; label?: string; primary?: boolean }) {\n'
        '  const [done, setDone] = useState(false); const toast = useToast();\n'
      )),
      ((
        'export const StarButton = ({ on, onClick }: { on: boolean; onClick: () => void }) => (\n'
        '  <button className="icon-btn" aria-label={on ? t.common.unfavorite : t.common.favorite} aria-pressed={on} onClick={onClick}><Star size={18} fill={on ? \'var(--color-warning)\' : \'none\'} color={on ? \'var(--color-warning)\' : \'currentColor\'} /></button>\n'
        ');\n'
        '\n'
        '// ---- modal / drawer with focus trap and Esc ----\n'
        'function useTrap(onClose: () => void) {\n'
        '  const ref = useRef<HTMLDivElement>(null);\n'
        '  useEffect(() => {\n'
        '    const prev = document.activeElement as HTMLElement | null; const el = ref.current;\n'
        '    const focusable = () => Array.from(el?.querySelectorAll<HTMLElement>(\'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])\') ?? []).filter((x) => !x.hasAttribute(\'disabled\'));\n'
        '    (focusable()[0] ?? el)?.focus();\n'
        '    const key = (e: KeyboardEvent) => {\n'
        "      if (e.key === 'Escape') { e.stopPropagation(); onClose(); }\n"
        "      if (e.key === 'Tab') { const f = focusable(); if (!f.length) return; const first = f[0]!; const last = f[f.length - 1]!;\n"
        '        if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); } else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); } }\n'
        '    };\n'
        "    document.addEventListener('keydown', key);\n"
        "    return () => { document.removeEventListener('keydown', key); prev?.focus?.(); };\n"
        '  }, [onClose]);\n'
        '  return ref;\n'
        '}\n'
        'export function Modal({ title, onClose, children, wide = false, footer }: { title: string; onClose: () => void; children: ReactNode; wide?: boolean; footer?: ReactNode }) {\n'
        '  const ref = useTrap(onClose);\n'
        '  return <div className="overlay" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>\n'
        '    <div ref={ref} className={`glass modal ${wide ? \'wide\' : \'\'}`} role="dialog" aria-modal="true" aria-label={title} tabIndex={-1}>\n'
        '      <div className="row spread" style={{ marginBottom: 14 }}><h3>{title}</h3><button className="icon-btn" aria-label={t.common.close} onClick={onClose}><X size={18} /></button></div>\n'
        '      <div className="col">{children}</div>{footer && <div className="row" style={{ justifyContent: \'flex-end\', marginTop: 16 }}>{footer}</div>}\n'
        '    </div></div>;\n'
        '}\n'
        'export function Drawer({ title, onClose, children }: { title: ReactNode; onClose: () => void; children: ReactNode }) {\n'
        '  const ref = useTrap(onClose);\n'
        '  return <div className="overlay" style={{ justifyContent: \'flex-end\', padding: 0 }} onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>\n'
        '    <div ref={ref} className="glass drawer" role="dialog" aria-modal="true" tabIndex={-1}>\n'
        '      <div className="row spread" style={{ marginBottom: 16 }}><h2>{title}</h2><button className="icon-btn" aria-label={t.common.close} onClick={onClose}><X size={20} /></button></div>{children}\n'
        '    </div></div>;\n'
        '}\n'
        'export function ConfirmModal({ title, text, danger = false, onConfirm, onClose }: { title: string; text: string; danger?: boolean; onConfirm: () => void; onClose: () => void }) {\n'
        '  return <Modal title={title} onClose={onClose} footer={<><button className="btn" onClick={onClose}>{t.common.cancel}</button><button className={`btn ${danger ? \'danger\' : \'primary\'}`} onClick={() => { onConfirm(); onClose(); }}>{t.common.confirm}</button></>}><p className="tx2" style={{ margin: 0 }}>{text}</p></Modal>;\n'
        '}\n'
        '\n'
        'export const Switch = ({ on, onChange, label, disabled }: { on: boolean; onChange: (v: boolean) => void; label: string; disabled?: boolean }) =>\n'
        '  <button type="button" role="switch" aria-checked={on} aria-label={label} disabled={disabled} className={`switch ${on ? \'on\' : \'\'}`} onClick={() => onChange(!on)} />;\n'
        'export function Seg<T extends string>({ value, options, onChange, label }: { value: T; options: { value: T; label: string }[]; onChange: (v: T) => void; label: string }) {\n'
        '  return <div className="seg" role="group" aria-label={label}>{options.map((o) => <button key={o.value} type="button" className={o.value === value ? \'on\' : \'\'} aria-pressed={o.value === value} onClick={() => onChange(o.value)}>{o.label}</button>)}</div>;\n'
        '}\n'
        'export const Empty = ({ title, hint, cta }: { title: string; hint?: string; cta?: ReactNode }) =>\n'
        '  <div className="empty glass"><div className="glyph" aria-hidden>{t.empty.glyph}</div><h3 style={{ marginTop: 8 }}>{title}</h3>{hint && <p className="tx2" style={{ margin: \'6px 0 14px\' }}>{hint}</p>}{cta}</div>;\n'
        'export const Skeletons = ({ n = 3, h = 90 }: { n?: number; h?: number }) => <div className="col">{Array.from({ length: n }, (_, i) => <div key={i} className="skeleton glass" style={{ height: h }} />)}</div>;\n'
        'export const Spinner = () => <span className="spinner" aria-hidden />;\n'
        '\n'
        '// ---- helpers ----\n'
        'export function daysFrom(iso: string | null | undefined, now = Date.now()): number | null { return iso ? Math.round((Date.parse(iso) - now) / 86_400_000) : null; }\n'
        "export function fmtDate(iso: string): string { return new Date(iso).toLocaleString('ru-RU', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }); }\n"
        "export function renderMarkdown(md: string): string { return DOMPurify.sanitize(marked.parse(md, { async: false }) as string, { FORBID_TAGS: ['style', 'script', 'iframe'], USE_PROFILES: { html: true } }); }\n"
        'export const Markdown = ({ md }: { md: string }) => <div className="md" dangerouslySetInnerHTML={{ __html: renderMarkdown(md) }} />;\n'
        '\n'
        '/** Highlights XML tags and Markdown headings without a heavy syntax highlighter. */\n'
        'export function HighlightedPrompt({ text }: { text: string }) {\n'
      ), (
        'export const StarButton = ({ on, onClick }: { on: boolean; onClick: () => void }) => (\n'
        '  <button className="icon-btn" aria-label={on ? t.common.unfavorite : t.common.favorite} aria-pressed={on} onClick={onClick}><Star size={18} fill={on ? \'var(--color-warning)\' : \'none\'} color={on ? \'var(--color-warning)\' : \'currentColor\'} /></button>\n'
        ');\n'
        '\n'
        '// ---- dialogs ----\n'
        'function Dialog({ title, onClose, children, footer, wide, side }: {\n'
        '  title: ReactNode;\n'
        '  onClose: () => void;\n'
        '  children: ReactNode;\n'
        '  footer?: ReactNode;\n'
        '  wide?: boolean;\n'
        '  side?: boolean;\n'
        '}) {\n'
        '  const ref = useRef<HTMLDialogElement>(null);\n'
        '  const titleId = useId();\n'
        '  useEffect(() => {\n'
        '    const dialog = ref.current!;\n'
        '    const previous = document.activeElement;\n'
        '    dialog.showModal();\n'
        '    return () => {\n'
        '      dialog.close();\n'
        '      if (previous instanceof HTMLElement && previous.isConnected) previous.focus({ preventScroll: true });\n'
        '    };\n'
        '  }, []);\n'
        '  return (\n'
        "    <dialog ref={ref} className={side ? 'surface drawer' : `surface modal ${wide ? 'wide' : ''}`}\n"
        '      aria-labelledby={titleId} onCancel={(event) => { event.preventDefault(); onClose(); }}\n'
        '      onClick={(event) => {\n'
        '        if (event.target !== event.currentTarget) return;\n'
        '        const rect = event.currentTarget.getBoundingClientRect();\n'
        '        if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) onClose();\n'
        '      }}>\n'
        '      <header className="dialog-head row spread">\n'
        '        {side ? <h2 id={titleId}>{title}</h2> : <h3 id={titleId}>{title}</h3>}\n'
        '        <button className="icon-btn" aria-label={t.common.close} onClick={onClose}><X size={18} aria-hidden /></button>\n'
        '      </header>\n'
        '      <div className="col">{children}</div>\n'
        '      {footer && <footer className="dialog-footer row wrap">{footer}</footer>}\n'
        '    </dialog>\n'
        '  );\n'
        '}\n'
        '\n'
        'export function Modal(props: { title: string; onClose: () => void; children: ReactNode; wide?: boolean; footer?: ReactNode }) {\n'
        '  return <Dialog {...props} />;\n'
        '}\n'
        'export function Drawer(props: { title: ReactNode; onClose: () => void; children: ReactNode }) {\n'
        '  return <Dialog {...props} side />;\n'
        '}\n'
        'export function ConfirmModal({ title, text, danger = false, onConfirm, onClose }: {\n'
        '  title: string; text: string; danger?: boolean;\n'
        '  onConfirm: () => void | Promise<void>; onClose: () => void;\n'
        '}) {\n'
        '  const [busy, setBusy] = useState(false);\n'
        '  const confirm = async () => {\n'
        '    setBusy(true);\n'
        '    try { await onConfirm(); onClose(); }\n'
        '    finally { setBusy(false); }\n'
        '  };\n'
        '  return <Modal title={title} onClose={onClose} footer={\n'
        '    <>\n'
        '      <button className="btn" disabled={busy} onClick={onClose}>{t.common.cancel}</button>\n'
        "      <button className={`btn ${danger ? 'danger' : 'primary'}`} disabled={busy} onClick={confirm}>{t.common.confirm}</button>\n"
        '    </>\n'
        '  }><p className="tx2">{text}</p></Modal>;\n'
        '}\n'
        '\n'
        'export const Switch = ({ on, onChange, label, disabled }: { on: boolean; onChange: (v: boolean) => void; label: string; disabled?: boolean }) =>\n'
        '  <button type="button" role="switch" aria-checked={on} aria-label={label} disabled={disabled} className={`switch ${on ? \'on\' : \'\'}`} onClick={() => onChange(!on)} />;\n'
        'export function Seg<T extends string>({ value, options, onChange, label }: { value: T; options: { value: T; label: string }[]; onChange: (v: T) => void; label: string }) {\n'
        '  return <div className="seg" role="group" aria-label={label}>{options.map((o) => <button key={o.value} type="button" className={o.value === value ? \'on\' : \'\'} aria-pressed={o.value === value} onClick={() => onChange(o.value)}>{o.label}</button>)}</div>;\n'
        '}\n'
        'export const Empty = ({ title, hint, cta }: { title: string; hint?: string; cta?: ReactNode }) =>\n'
        '  <div className="empty surface"><div className="glyph" aria-hidden>{t.empty.glyph}</div><h3 style={{ marginTop: 8 }}>{title}</h3>{hint && <p className="tx2" style={{ margin: \'6px 0 14px\' }}>{hint}</p>}{cta}</div>;\n'
        'export const Skeletons = ({ n = 3, h = 90 }: { n?: number; h?: number }) => <div className="col">{Array.from({ length: n }, (_, i) => <div key={i} className="skeleton" style={{ height: h }} />)}</div>;\n'
        'export const Spinner = () => <span className="spinner" aria-hidden />;\n'
        '\n'
        '// ---- helpers ----\n'
        'export function daysFrom(iso: string | null | undefined, now = Date.now()): number | null { return iso ? Math.round((Date.parse(iso) - now) / 86_400_000) : null; }\n'
        "export function fmtDate(iso: string): string { return new Date(iso).toLocaleString('ru-RU', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }); }\n"
        "function renderMarkdown(md: string): string { return DOMPurify.sanitize(marked.parse(md, { async: false }) as string, { FORBID_TAGS: ['style', 'script', 'iframe'], USE_PROFILES: { html: true } }); }\n"
        'export const Markdown = ({ md }: { md: string }) => <div className="md" dangerouslySetInnerHTML={{ __html: renderMarkdown(md) }} />;\n'
        '\n'
        '/** Highlights XML tags and Markdown headings without a heavy syntax highlighter. */\n'
        'export function HighlightedPrompt({ text }: { text: string }) {\n'
      )),
    ),
    'apps/web/vite.config.ts': (
      ((
        "import react from '@vitejs/plugin-react';\n"
        "import path from 'node:path';\n"
        '\n'
        'export default defineConfig({\n'
        '  root: path.resolve(__dirname),\n'
        '  plugins: [react()],\n'
        "  build: { outDir: path.resolve(__dirname, '../../dist/public'), emptyOutDir: true, sourcemap: false, chunkSizeWarningLimit: 900 },\n"
        "  server: { port: 5173, proxy: { '/api': 'http://localhost:3000', '/healthz': 'http://localhost:3000' } },\n"
        '});\n'
      ), (
        "import react from '@vitejs/plugin-react';\n"
        "import path from 'node:path';\n"
        '\n'
        'export default defineConfig({\n'
        '  root: import.meta.dirname,\n'
        '  plugins: [react()],\n'
        "  build: { outDir: path.resolve(import.meta.dirname, '../../dist/public'), emptyOutDir: true, sourcemap: false, chunkSizeWarningLimit: 900 },\n"
        "  server: { port: 5173, proxy: { '/api': 'http://localhost:3000', '/healthz': 'http://localhost:3000' } },\n"
        '});\n'
      )),
    ),
    'package.json': (
      ((
        '  "private": true,\n'
        '  "type": "module",\n'
        '  "description": "Promptolog: prompt generator with self-updating per-system skills, built for the Alaio Vibecode (Bitrix24) platform.",\n'
        '  "engines": {\n'
        '    "node": ">=22.5"\n'
        '  },\n'
        '  "scripts": {\n'
        '    "dev:server": "node --experimental-transform-types apps/server/src/main.ts",\n'
        '    "dev:web": "vite --config apps/web/vite.config.ts",\n'
      ), (
        '  "private": true,\n'
        '  "type": "module",\n'
        '  "description": "Promptolog: prompt generator with self-updating per-system skills, built for the Alaio Vibecode (Bitrix24) platform.",\n'
        '  "engines": {\n'
        '    "node": ">=22.12"\n'
        '  },\n'
        '  "scripts": {\n'
        '    "dev:server": "node --experimental-transform-types apps/server/src/main.ts",\n'
        '    "dev:web": "vite --config apps/web/vite.config.ts",\n'
      )),
      ((
        '  },\n'
        '  "devDependencies": {\n'
        '    "@fontsource/jetbrains-mono": "^5.3.0",\n'
        '    "@fontsource/manrope": "^5.3.0",\n'
        '    "@types/node": "^26.6.6",\n'
        '    "@types/react": "^18.3.31",\n'
        '    "@types/react-dom": "^18.3.7",\n'
        '    "@vitejs/plugin-react": "^6.3.0",\n'
        '    "autoprefixer": "^10.6.2",\n'
      ), (
        '  },\n'
        '  "devDependencies": {\n'
        '    "@fontsource/jetbrains-mono": "^5.3.0",\n'
        '    "@fontsource/manrope": "^5.3.0",\n'
        '    "@types/node": "22.20.5",\n'
        '    "@types/react": "^18.3.31",\n'
        '    "@types/react-dom": "^18.3.7",\n'
        '    "@vitejs/plugin-react": "^6.3.0",\n'
        '    "autoprefixer": "^10.6.2",\n'
      )),
    ),
    'shared/src/optimizer.ts': (
      ((
        'export const OPT_PRESETS = [...GOAL_PRESETS, ...FRAMEWORK_PRESETS] as const;\n'
        'export type OptPreset = (typeof OPT_PRESETS)[number];\n'
        "export const OUTPUT_FORMATS = ['none', 'table', 'json', 'markdown_list', 'prose', 'code', 'slides'] as const;\n"
        "export const TONES = ['none', 'academic', 'persuasive', 'friendly', 'concise', 'no_yapping'] as const;\n"
        'export const OPT_LIMITS = { rawMin: 3, rawMax: 12000, answerMax: 1000, promptMax: 20000, questions: 3, folderName: 60, maxFolders: 40 } as const;\n'
        'export const DEFAULT_FOLDERS = [\n'
        "  { key: 'work', name: 'Работа' }, { key: 'marketing', name: 'Маркетинг' }, { key: 'coding', name: 'Код' },\n"
        '] as const;\n'
        '\n'
      ), (
        'export const OPT_PRESETS = [...GOAL_PRESETS, ...FRAMEWORK_PRESETS] as const;\n'
        'export type OptPreset = (typeof OPT_PRESETS)[number];\n'
        "export const OUTPUT_FORMATS = ['none', 'table', 'json', 'markdown_list', 'prose', 'code', 'slides'] as const;\n"
        "export const TONES = ['none', 'academic', 'persuasive', 'friendly', 'concise', 'no_yapping'] as const;\n"
        'export const OPT_LIMITS = { rawMin: 3, rawMax: 12000, answerMax: 1000, promptMax: 20000, questions: 3, folderName: 60, variableValue: 2000, maxFolders: 40 } as const;\n'
        'export const DEFAULT_FOLDERS = [\n'
        "  { key: 'work', name: 'Работа' }, { key: 'marketing', name: 'Маркетинг' }, { key: 'coding', name: 'Код' },\n"
        '] as const;\n'
        '\n'
      )),
      ((
        '\n'
        '// ---------- engine (provider, model, key) ----------\n'
        "export const PROVIDERS = ['platform', 'anthropic', 'openai', 'google', 'alibaba', 'moonshot', 'custom'] as const;\n"
        'export type Provider = (typeof PROVIDERS)[number];\n'
        'export interface CatalogModel { id: string; label: string; verified: boolean; recommended?: boolean }\n'
        "/** Model ids other than Anthropic's are taken from the product spec and are NOT verified against provider docs: use the custom model field if one differs. */\n"
        "export const ENGINE_CATALOG: Record<Exclude<Provider, 'platform' | 'custom'>, CatalogModel[]> = {\n"
        "  anthropic: [{ id: 'claude-opus-5-5', label: 'Claude Opus 5.5', verified: true, recommended: true }, { id: 'claude-sonnet-5-5', label: 'Claude Sonnet 5.5', verified: true }],\n"
        "  openai: [{ id: 'chatgpt-6-omni', label: 'ChatGPT 6 Omni', verified: false }, { id: 'gpt-6-reasoning', label: 'GPT-6 Reasoning', verified: false }],\n"
        "  google: [{ id: 'gemini-4-ultra', label: 'Gemini 4 Ultra', verified: false }, { id: 'gemini-4-pro', label: 'Gemini 4 Pro', verified: false }],\n"
        "  alibaba: [{ id: 'qwen-4-max', label: 'Qwen 4 Max', verified: false }, { id: 'qwen-4-coder', label: 'Qwen 4 Coder', verified: false }],\n"
        "  moonshot: [{ id: 'kimi-3.1-ultra', label: 'Kimi 3.1 Ultra', verified: false }],\n"
        '};\n'
        'export const engineConfigSchema = z.object({\n'
        "  provider: z.enum(PROVIDERS).default('platform'),\n"
        "  model: z.string().trim().min(1).max(120).default('bitrix/bitrixgpt-5.5'),\n"
        "  base_url: z.string().trim().max(300).default(''),\n"
        '  temperature: z.number().min(0).max(1.5).default(0.4),\n'
        '});\n'
        'export type EngineConfig = z.infer<typeof engineConfigSchema>;\n'
        'export const engineUpdateSchema = engineConfigSchema.partial().extend({\n'
        '  /** Plain key from the admin form. Empty string clears the stored key; omitted keeps it. */\n'
        '  api_key: z.string().max(500).optional(),\n'
        '});\n'
        'export interface EngineView extends EngineConfig {\n'
        '  has_key: boolean; key_hint: string; secret_configured: boolean;\n'
        '  catalog: typeof ENGINE_CATALOG; default_base_urls: Record<string, string>;\n'
      ), (
        '\n'
        '// ---------- engine (provider, model, key) ----------\n'
        "export const PROVIDERS = ['platform', 'anthropic', 'openai', 'google', 'alibaba', 'moonshot', 'custom'] as const;\n"
        'export type Provider = (typeof PROVIDERS)[number];\n'
        'export interface CatalogModel { id: string; label: string; recommended?: boolean }\n'
        "/** Published model IDs for the supported API adapters. Other providers accept a model ID from the user's account. */\n"
        "export const ENGINE_CATALOG: Record<Exclude<Provider, 'platform' | 'custom'>, CatalogModel[]> = {\n"
        "  anthropic: [{ id: 'claude-opus-5-5', label: 'Claude Opus 5.5' }, { id: 'claude-sonnet-5-5', label: 'Claude Sonnet 5.5', recommended: true }],\n"
        "  openai: [{ id: 'gpt-6.2-sol', label: 'GPT-6.2 Sol' }],\n"
        '  google: [],\n'
        '  alibaba: [],\n'
        '  moonshot: [],\n'
        '};\n'
        'export function supportsCustomTemperature(provider: Provider, model: string): boolean {\n'
        "  if (provider === 'anthropic') return !/^claude-(?:\\w+-5|opus-4-(?:[7-9]|\\d{2,}))(?:-|$)/i.test(model);\n"
        "  if (provider === 'openai') return !/^(?:gpt-[56](?:[.\\-]|$)|o\\d)/i.test(model);\n"
        '  return true;\n'
        '}\n'
        '\n'
        "export const DEFAULT_ENGINE_MODEL = 'bitrix/bitrixgpt-5.5';\n"
        'export const engineConfigSchema = z.object({\n'
        "  provider: z.enum(PROVIDERS).default('platform'),\n"
        '  model: z.string().trim().min(1).max(120).default(DEFAULT_ENGINE_MODEL),\n'
        "  base_url: z.string().trim().max(300).default(''),\n"
        '  temperature: z.number().min(0).max(1.5).default(0.4),\n'
        '});\n'
        'export type EngineConfig = z.infer<typeof engineConfigSchema>;\n'
        'export const engineUpdateSchema = z.object({\n'
        '  provider: engineConfigSchema.shape.provider.unwrap().optional(),\n'
        '  model: engineConfigSchema.shape.model.unwrap().optional(),\n'
        '  base_url: engineConfigSchema.shape.base_url.unwrap().optional(),\n'
        '  temperature: engineConfigSchema.shape.temperature.unwrap().optional(),\n'
        '  /** Plain key from the admin form. Empty string clears the stored key; omitted keeps it. */\n'
        '  api_key: z.string().trim().max(500).optional(),\n'
        '});\n'
        'export interface EngineView extends EngineConfig {\n'
        '  has_key: boolean; key_hint: string; secret_configured: boolean;\n'
        '  catalog: typeof ENGINE_CATALOG; default_base_urls: Record<string, string>;\n'
      )),
      ((
        '  for (const m of text.matchAll(BR_RE)) { const v = m[1]!.trim(); if (/\\p{L}/u.test(v)) seen.add(v); }\n'
        '  return [...seen].slice(0, 20);\n'
        '}\n'
        'export function substituteBracketVars(text: string, values: Record<string, string>): string {\n'
        "  return text.replace(BR_RE, (m, name: string) => { const v = values[name.trim()]; return v !== undefined && v !== '' ? v : m; });\n"
        '}\n'
        '/** Rough token estimate without a tokenizer: about 4 Latin characters, or 2.5 Cyrillic characters, per token. Always shown as approximate. */\n'
        'export function estimateTokens(text: string): number {\n'
        '  let latin = 0; let cyr = 0; let other = 0;\n'
      ), (
        '  for (const m of text.matchAll(BR_RE)) { const v = m[1]!.trim(); if (/\\p{L}/u.test(v)) seen.add(v); }\n'
        '  return [...seen].slice(0, 20);\n'
        '}\n'
        'export function substituteBracketVars(text: string, values: Record<string, string>): string {\n'
        '  return text.replace(BR_RE, (match, name: string) => {\n'
        '    const key = name.trim();\n'
        "    return Object.hasOwn(values, key) && values[key] !== '' ? values[key]! : match;\n"
        '  });\n'
        '}\n'
        '/** Rough token estimate without a tokenizer: about 4 Latin characters, or 2.5 Cyrillic characters, per token. Always shown as approximate. */\n'
        'export function estimateTokens(text: string): number {\n'
        '  let latin = 0; let cyr = 0; let other = 0;\n'
      )),
      ((
        '    if (/[\\u0400-\\u04FF]/.test(ch)) cyr++; else if (/[\\u0021-\\u007E]/.test(ch)) latin++; else other++;\n'
        '  }\n'
        '  return Math.max(1, Math.ceil(latin / 4 + cyr / 2.5 + other * 0.8 + text.split(/\\s+/).filter(Boolean).length * 0.1));\n'
        '}\n'
        "export function frameworkOf(preset: OptPreset): 'goal' | 'framework' { return (FRAMEWORK_PRESETS as readonly string[]).includes(preset) ? 'framework' : 'goal'; }\n"
      ), (
        '    if (/[\\u0400-\\u04FF]/.test(ch)) cyr++; else if (/[\\u0021-\\u007E]/.test(ch)) latin++; else other++;\n'
        '  }\n'
        '  return Math.max(1, Math.ceil(latin / 4 + cyr / 2.5 + other * 0.8 + text.split(/\\s+/).filter(Boolean).length * 0.1));\n'
        '}\n'
      )),
    ),
    'tests/optimizer.test.ts': (
      ((
        "import { describe, it, expect, beforeEach } from 'vitest';\n"
        "import { freshDb } from './helpers.ts';\n"
        "import { buildApp } from '../apps/server/src/routes.ts';\n"
        "import { resetRateLimits, clearIdentityCache } from '../apps/server/src/auth.ts';\n"
        "import { config } from '../apps/server/src/config.ts';\n"
        "import { VibeError, type VibeClient } from '../apps/server/src/vibe.ts';\n"
        "import { assertSafeBaseUrl, decryptSecret, encryptSecret, engineChat, engineJson, engineView, EngineOutputError, getEngineConfig, updateEngine } from '../apps/server/src/engine.ts';\n"
        "import { applyBridge, buildOptimizeMessages } from '../apps/server/src/optimizer.ts';\n"
        "import { BRIDGE_CONSTRAINT, clarifierOutputSchema, estimateTokens, extractBracketVars, optimizeRequestSchema, substituteBracketVars } from '../shared/src/index.ts';\n"
        '\n'
        "const U = { 'x-vibe-user-id': '42', 'x-vibe-user-role': 'ADMIN', 'x-vibe-authorization': 'Bearer vibe_session_test' };\n"
      ), (
        "import { resolveEngineUrl } from '../apps/server/src/engine-url.ts';\n"
        "import { describe, it, expect, beforeEach } from 'vitest';\n"
        "import { freshDb } from './helpers.ts';\n"
        "import { buildApp } from '../apps/server/src/routes.ts';\n"
        "import { resetRateLimits, clearIdentityCache } from '../apps/server/src/auth.ts';\n"
        "import { config } from '../apps/server/src/config.ts';\n"
        "import { VibeError, type VibeClient } from '../apps/server/src/vibe.ts';\n"
        "import { decryptSecret, encryptSecret, engineChat, engineJson, engineView, EngineOutputError, getEngineConfig, updateEngine } from '../apps/server/src/engine.ts';\n"
        "import { applyBridge, buildOptimizeMessages } from '../apps/server/src/optimizer.ts';\n"
        "import { BRIDGE_CONSTRAINT, clarifierOutputSchema, estimateTokens, extractBracketVars, optimizeRequestSchema, substituteBracketVars } from '../shared/src/index.ts';\n"
        '\n'
        "const U = { 'x-vibe-user-id': '42', 'x-vibe-user-role': 'ADMIN', 'x-vibe-authorization': 'Bearer vibe_session_test' };\n"
      )),
      ((
        "const RAW = 'Напиши пост про котиков для инсты';\n"
        "const OUT = (o: Record<string, unknown> = {}) => JSON.stringify({ initial_score: 2, initial_critique: 'Слишком расплывчато', optimized_score: 9.5, changelog_explanation: ['Добавлена роль: эксперт SMM', 'Добавлена структура поста', 'Заданы ограничения'], final_prompt: 'You are an expert SMM manager. Write an Instagram post about cats. Structure: hook, body, question, hashtags.', framework_used: 'RTF', ...o });\n"
        '\n'
        'interface Calls { systems: string[]; users: string[] }\n'
        "function fakeEngineVibe(handlers: Partial<Record<'optimize' | 'clarify' | 'compress', () => string>> = {}, calls: Calls = { systems: [], users: [] }): VibeClient {\n"
        '  return {\n'
        '    async chat(_m: string, messages: { role: string; content: string }[]) {\n'
        '      const sys = messages[0]!.content; calls.systems.push(sys); calls.users.push(messages[messages.length - 1]!.content);\n'
        "      const kind = sys.includes('prompt compressor') ? 'compress' : sys.includes('prepare an interview') ? 'clarify' : 'optimize';\n"
        "      const body = handlers[kind]?.() ?? (kind === 'clarify' ? JSON.stringify({ clarifying_questions: ['Возраст, вес, пол?', 'Дом или зал?', 'Цель: масса или похудение?'] })\n"
        "        : kind === 'compress' ? JSON.stringify({ compressed_prompt: 'Role: SMM expert. Task: Instagram cat post. Structure: hook, body, question, hashtags.' }) : OUT());\n"
        "      return { content: body, totalTokens: 50, model: 'fake-model' };\n"
        '    },\n'
        "    async models() { return []; }, async usage() { return {}; }, async me() { return { currentUser: { bitrixUserId: '42' }, portal: 'p' }; },\n"
      ), (
        "const RAW = 'Напиши пост про котиков для инсты';\n"
        "const OUT = (o: Record<string, unknown> = {}) => JSON.stringify({ initial_score: 2, initial_critique: 'Слишком расплывчато', optimized_score: 9.5, changelog_explanation: ['Добавлена роль: эксперт SMM', 'Добавлена структура поста', 'Заданы ограничения'], final_prompt: 'You are an expert SMM manager. Write an Instagram post about cats. Structure: hook, body, question, hashtags.', framework_used: 'RTF', ...o });\n"
        '\n'
        'interface Calls { systems: string[]; users: string[] }\n'
        "function fakeEngineVibe(handlers: Partial<Record<'optimize' | 'clarify' | 'compress', () => string | Promise<string>>> = {}, calls: Calls = { systems: [], users: [] }): VibeClient {\n"
        '  return {\n'
        '    async chat(_m: string, messages: { role: string; content: string }[]) {\n'
        '      const sys = messages[0]!.content; calls.systems.push(sys); calls.users.push(messages[messages.length - 1]!.content);\n'
        "      const kind = sys.includes('prompt compressor') ? 'compress' : sys.includes('prepare an interview') ? 'clarify' : 'optimize';\n"
        "      const body = await handlers[kind]?.() ?? (kind === 'clarify' ? JSON.stringify({ clarifying_questions: ['Возраст, вес, пол?', 'Дом или зал?', 'Цель: масса или похудение?'] })\n"
        "        : kind === 'compress' ? JSON.stringify({ compressed_prompt: 'Role: SMM expert. Task: Instagram cat post. Structure: hook, body, question, hashtags.' }) : OUT());\n"
        "      return { content: body, totalTokens: 50, model: 'fake-model' };\n"
        '    },\n'
        "    async models() { return []; }, async usage() { return {}; }, async me() { return { currentUser: { bitrixUserId: '42' }, portal: 'p' }; },\n"
      )),
      ((
        "    expect(JSON.stringify(db.all('SELECT * FROM settings'))).not.toContain('sk-secret');\n"
        "    expect((await updateEngine(db, { api_key: '' })).has_key).toBe(false);\n"
        '  });\n'
        "  it('blocks unsafe Custom_Base_URL values', async () => {\n"
        "    for (const u of ['http://example.com/v1', 'https://localhost/v1', 'https://127.0.0.1/v1', 'https://10.0.0.5/v1', 'https://169.254.169.254/', 'https://[::1]/', 'https://user:pw@93.184.216.34/', 'ftp://x.y', 'not a url']) await expect(assertSafeBaseUrl(u)).rejects.toMatchObject({ code: 'bad_base_url' });\n"
        "    await expect(assertSafeBaseUrl('https://93.184.216.34/v1')).resolves.toBeInstanceOf(URL);\n"
        '  });\n'
        "  const setup = async (provider: string, extra: Record<string, unknown> = {}) => { const db = freshDb(); await updateEngine(db, { provider: provider as any, model: 'mdl', base_url: 'https://93.184.216.34/api', temperature: 0.3, api_key: 'sk-live-KEY12345', ...extra }); return db; };\n"
        "  const msgs = [{ role: 'system' as const, content: 'SYS' }, { role: 'user' as const, content: 'hello' }];\n"
        "  it('speaks Anthropic, OpenAI-compatible and Google shapes', async () => {\n"
      ), (
        "    expect(JSON.stringify(db.all('SELECT * FROM settings'))).not.toContain('sk-secret');\n"
        "    expect((await updateEngine(db, { api_key: '' })).has_key).toBe(false);\n"
        '  });\n'
        "  it('blocks unsafe Custom_Base_URL values', async () => {\n"
        "    for (const u of ['http://example.com/v1', 'https://localhost/v1', 'https://127.0.0.1/v1', 'https://10.0.0.5/v1', 'https://169.254.169.254/', 'https://[::1]/', 'https://user:pw@93.184.216.34/', 'ftp://x.y', 'not a url']) await expect(resolveEngineUrl(u)).rejects.toMatchObject({ code: 'bad_base_url' });\n"
        "    await expect(resolveEngineUrl('https://93.184.216.34/v1')).resolves.toMatchObject({ url: expect.any(URL) });\n"
        '  });\n'
        "  const setup = async (provider: string, extra: Record<string, unknown> = {}) => { const db = freshDb(); await updateEngine(db, { provider: provider as any, model: 'mdl', base_url: 'https://93.184.216.34/api', temperature: 0.3, api_key: 'sk-live-KEY12345', ...extra }); return db; };\n"
        "  const msgs = [{ role: 'system' as const, content: 'SYS' }, { role: 'user' as const, content: 'hello' }];\n"
        "  it('speaks Anthropic, OpenAI-compatible and Google shapes', async () => {\n"
      )),
      ((
        "    expect((await call('PUT', '/api/optimizer/engine', U, { provider: 'platform' })).body.provider).toBe('platform');\n"
        "    const t = await call('POST', '/api/optimizer/engine/test', U); expect(t.body).toMatchObject({ ok: true, provider: 'platform' });\n"
        "    expect((await call('POST', '/api/optimizer/engine/test', M)).status).toBe(403);\n"
        '  });\n'
        "  it('surfaces a bad model reply as 502 and stores nothing', async () => {\n"
        "    const { call } = await mk({ optimize: () => 'not json' });\n"
        "    const r = await call('POST', '/api/optimizer/run', U, { raw_input: RAW });\n"
        "    expect(r.status).toBe(502); expect(r.body.error.code).toBe('engine_bad_output');\n"
      ), (
        "    expect((await call('PUT', '/api/optimizer/engine', U, { provider: 'platform' })).body.provider).toBe('platform');\n"
        "    const t = await call('POST', '/api/optimizer/engine/test', U); expect(t.body).toMatchObject({ ok: true, provider: 'platform' });\n"
        "    expect((await call('POST', '/api/optimizer/engine/test', M)).status).toBe(403);\n"
        '  });\n'
        "  it('preserves engine fields on partial updates and scopes keys to the selected destination', async () => {\n"
        '    const { call } = await mk();\n'
        "    const saved = await call('PUT', '/api/optimizer/engine', U, {\n"
        "      provider: 'anthropic', model: 'claude-opus-5-5', api_key: 'test-credential', base_url: 'https://93.184.216.34/v1',\n"
        '    });\n'
        '    expect(saved.status).toBe(200);\n'
        "    expect((await call('PUT', '/api/optimizer/engine', U, { temperature: 0.8 })).body)\n"
        "      .toMatchObject({ provider: 'anthropic', model: 'claude-opus-5-5', temperature: 0.8, has_key: true });\n"
        "    expect((await call('PUT', '/api/optimizer/engine', U, { provider: 'openai', model: 'gpt-6.2-sol' })).body)\n"
        "      .toMatchObject({ provider: 'openai', model: 'gpt-6.2-sol', base_url: '', has_key: false });\n"
        '  });\n'
        "  it('allows one overlapping answer and counts both model calls', async () => {\n"
        '    let complete!: (answer: string) => void;\n'
        '    let notify!: () => void;\n'
        '    const started = new Promise<void>((resolve) => { notify = resolve; });\n'
        '    const waiting = new Promise<string>((resolve) => { complete = resolve; });\n'
        '    const { call, db } = await mk({ optimize: () => { notify(); return waiting; } });\n'
        "    const draft = await call('POST', '/api/optimizer/run', U, { raw_input: RAW, workflow: 'clarify' });\n"
        '    const url = `/api/optimizer/items/${draft.body.id}/answer`;\n'
        "    const first = call('POST', url, U, { answers: ['', 'Команда'] });\n"
        '    await started;\n'
        '    try {\n'
        "      expect((await call('POST', url, U, { auto: true })).body.error.code).toBe('optimization_busy');\n"
        '    } finally { complete(OUT()); }\n'
        "    expect((await first).body.answers).toEqual(['', 'Команда', '']);\n"
        "    expect(db.get('SELECT tokens_used FROM optimizations WHERE id = ?', draft.body.id)?.tokens_used).toBe(100);\n"
        '  });\n'
        "  it('keeps the best saved compression after a non-improving retry', async () => {\n"
        "    const full = 'Please write a long, careful article about [Article Topic] for [Target Audience] and make sure to include a title.';\n"
        "    const short = 'Title and article: [Article Topic], for [Target Audience].';\n"
        '    let candidate = short;\n'
        '    const { call } = await mk({\n'
        '      optimize: () => OUT({ final_prompt: full }),\n'
        '      compress: () => JSON.stringify({ compressed_prompt: candidate }),\n'
        '    });\n'
        "    const result = await call('POST', '/api/optimizer/run', U, { raw_input: RAW, workflow: 'template' });\n"
        '    const path = `/api/optimizer/items/${result.body.id}/compress`;\n'
        "    expect((await call('POST', path, U)).body).toMatchObject({ no_gain: false, compressed_prompt: short });\n"
        "    candidate = 'Write something short but omit a variable.';\n"
        "    expect((await call('POST', path, U)).body).toMatchObject({ no_gain: true, compressed_prompt: short });\n"
        '  });\n'
        "  it('surfaces a bad model reply as 502 and stores nothing', async () => {\n"
        "    const { call } = await mk({ optimize: () => 'not json' });\n"
        "    const r = await call('POST', '/api/optimizer/run', U, { raw_input: RAW });\n"
        "    expect(r.status).toBe(502); expect(r.body.error.code).toBe('engine_bad_output');\n"
      )),
    ),
    'tests/pipeline.test.ts': (
      ((
        "  it('golden tests: new must never lose', async () => {\n"
        "    const cur = getCurrentVersion(db, 'claude');\n"
        "    const win = await goldenTests(fakeVibe({ judgeWinner: 'new' }), 'm', 'j', 'claude', cur, cur.body_md + 'NEWSKILL', (a) => a);\n"
        "    expect(win.every((g) => g.winner === 'new')).toBe(true);\n"
        "    const lose = await goldenTests(fakeVibe({ judgeWinner: 'old' }), 'm', 'j', 'claude', cur, cur.body_md + 'NEWSKILL', (a, b) => b);\n"
        "    expect(lose.every((g) => g.winner === 'old')).toBe(true);\n"
        '  });\n'
        '});\n'
        '\n'
      ), (
        "  it('golden tests: new must never lose', async () => {\n"
        "    const cur = getCurrentVersion(db, 'claude');\n"
        "    const win = await goldenTests(fakeVibe({ judgeWinner: 'new' }), 'm', 'j', 'claude', cur, cur.body_md + 'NEWSKILL', (a) => a);\n"
        "    expect(win.every((g) => g.winner === 'new')).toBe(true);\n"
        "    const lose = await goldenTests(fakeVibe({ judgeWinner: 'old' }), 'm', 'j', 'claude', cur, cur.body_md + 'NEWSKILL', (_old, next) => next);\n"
        "    expect(lose.every((g) => g.winner === 'old')).toBe(true);\n"
        '  });\n'
        '});\n'
        '\n'
      )),
      ((
        "    const body = JSON.stringify({ type: 'scheduled_job.run', jobId: 'j1', runId: 'run-1', scheduledFor: '2026-11-13T04:17:00.000Z', attempt: 1, late: false, trigger: 'schedule' });\n"
        '    const t = Math.floor(Date.now() / 1000);\n'
        "    const sig = `t=${t},v1=${createHmac('sha256', secret).update(`${t}.${body}`).digest('hex')}`;\n"
        "    const h = { 'content-type': 'application/json', 'x-vibe-caller-kind': 'schedule', 'vibe-signature': sig };\n"
        "    expect((await app.inject({ method: 'POST', url: '/internal/jobs/dispatcher', headers: { ...h, 'vibe-signature': sig.replace(/.$/, '0') }, payload: body })).statusCode).toBe(401);\n"
        "    expect((await app.inject({ method: 'POST', url: '/internal/jobs/dispatcher', headers: { ...h, 'x-vibe-caller-kind': 'user' }, payload: body })).statusCode).toBe(401);\n"
        "    expect((await app.inject({ method: 'POST', url: '/internal/jobs/dispatcher', headers: h, payload: body })).statusCode).toBe(200);\n"
        "    expect((await app.inject({ method: 'POST', url: '/internal/jobs/dispatcher', headers: h, payload: body })).statusCode).toBe(200);\n"
        "    expect(db.all('SELECT * FROM job_dedupe')).toHaveLength(1);\n"
      ), (
        "    const body = JSON.stringify({ type: 'scheduled_job.run', jobId: 'j1', runId: 'run-1', scheduledFor: '2026-11-13T04:17:00.000Z', attempt: 1, late: false, trigger: 'schedule' });\n"
        '    const t = Math.floor(Date.now() / 1000);\n'
        "    const sig = `t=${t},v1=${createHmac('sha256', secret).update(`${t}.${body}`).digest('hex')}`;\n"
        "    const h = { 'content-type': 'application/json', 'x-vibe-caller-kind': 'schedule', 'vibe-signature': sig };\n"
        "    expect((await app.inject({ method: 'POST', url: '/internal/jobs/dispatcher', headers: { ...h, 'vibe-signature': sig.replace(/.$/, (last) => last === '0' ? '1' : '0') }, payload: body })).statusCode).toBe(401);\n"
        "    expect((await app.inject({ method: 'POST', url: '/internal/jobs/dispatcher', headers: { ...h, 'x-vibe-caller-kind': 'user' }, payload: body })).statusCode).toBe(401);\n"
        "    expect((await app.inject({ method: 'POST', url: '/internal/jobs/dispatcher', headers: h, payload: body })).statusCode).toBe(200);\n"
        "    expect((await app.inject({ method: 'POST', url: '/internal/jobs/dispatcher', headers: h, payload: body })).statusCode).toBe(200);\n"
        "    expect(db.all('SELECT * FROM job_dedupe')).toHaveLength(1);\n"
      )),
    ),
    'tsconfig.base.json': (
      ((
        '    "target": "ES2023",\n'
        '    "module": "ESNext",\n'
        '    "moduleResolution": "Bundler",\n'
        '    "strict": true,\n'
        '    "noUncheckedIndexedAccess": false,\n'
        '    "esModuleInterop": true,\n'
        '    "skipLibCheck": true,\n'
        '    "resolveJsonModule": true,\n'
      ), (
        '    "target": "ES2023",\n'
        '    "module": "ESNext",\n'
        '    "moduleResolution": "Bundler",\n'
        '    "strict": true,\n'
        '    "noUnusedLocals": true,\n'
        '    "noUnusedParameters": true,\n'
        '    "noUncheckedIndexedAccess": false,\n'
        '    "esModuleInterop": true,\n'
        '    "skipLibCheck": true,\n'
        '    "resolveJsonModule": true,\n'
      )),
    ),
}

NEW_FILES = {'apps/server/src/engine-url.ts': "import { BlockList, isIP } from 'node:net';\n"
                                  "import { lookup } from 'node:dns/promises';\n"
                                  "import { request as httpsRequest } from 'node:https';\n"
                                  "import { config } from './config.ts';\n"
                                  "import { AppError } from './util.ts';\n"
                                  '\n'
                                  'const reserved = new BlockList();\n'
                                  'const reservedV4 = [\n'
                                  "  ['0.0.0.0', 8], ['10.0.0.0', 8], ['100.64.0.0', 10], ['127.0.0.0', 8],\n"
                                  "  ['169.254.0.0', 16], ['172.16.0.0', 12], ['192.0.0.0', 24], ['192.0.2.0', 24],\n"
                                  "  ['192.168.0.0', 16], ['198.18.0.0', 15], ['198.51.100.0', 24], ['203.0.113.0', 24], "
                                  "['224.0.0.0', 3],\n"
                                  '] as const;\n'
                                  "for (const [address, bits] of reservedV4) reserved.addSubnet(address, bits, 'ipv4');\n"
                                  'const globalV6 = new BlockList();\n'
                                  "globalV6.addSubnet('2000::', 3, 'ipv6');\n"
                                  "for (const [address, bits] of [['2001::', 23], ['2001:db8::', 32], ['2002::', 16], "
                                  "['3fff::', 20]] as const) {\n"
                                  "  reserved.addSubnet(address, bits, 'ipv6');\n"
                                  '}\n'
                                  '\n'
                                  'function isPublic(address: string, family: number): boolean {\n'
                                  "  if (family === 4) return !reserved.check(address, 'ipv4');\n"
                                  "  return family === 6 && globalV6.check(address, 'ipv6') && !reserved.check(address, "
                                  "'ipv6');\n"
                                  '}\n'
                                  '\n'
                                  'export async function resolveEngineUrl(raw: string) {\n'
                                  '  let url: URL;\n'
                                  '  try { url = new URL(raw); }\n'
                                  "  catch { throw new AppError(400, 'bad_base_url', 'Custom Base URL: некорректный "
                                  "адрес'); }\n"
                                  '\n'
                                  '  const allowPrivate = config.engineAllowPrivate;\n'
                                  "  if (url.protocol !== 'https:' && !(allowPrivate && url.protocol === 'http:')) {\n"
                                  "    throw new AppError(400, 'bad_base_url', 'Custom Base URL должен начинаться с "
                                  "https://');\n"
                                  '  }\n'
                                  '  if (url.username || url.password || url.search || url.hash) {\n'
                                  "    throw new AppError(400, 'bad_base_url', 'Custom Base URL должен содержать только "
                                  "адрес и путь');\n"
                                  '  }\n'
                                  '  if (allowPrivate) return { url, addresses: [] };\n'
                                  '\n'
                                  "  const host = url.hostname.replace(/^\\[|\\]$/g, '');\n"
                                  '  const family = isIP(host);\n'
                                  '  const addresses = family ? [{ address: host, family }] : await lookup(host, { all: '
                                  'true }).catch(() => []);\n'
                                  '  if (!addresses.length || addresses.some((entry) => !isPublic(entry.address, '
                                  'entry.family))) {\n'
                                  "    throw new AppError(400, 'bad_base_url', 'Custom Base URL: требуется публичный "
                                  "адрес');\n"
                                  '  }\n'
                                  '  return { url, addresses };\n'
                                  '}\n'
                                  '\n'
                                  'const MAX_RESPONSE_BYTES = 2_000_000;\n'
                                  '\n'
                                  '/** This lookup runs inside the connection, so it cannot resolve an unchecked address. '
                                  '*/\n'
                                  'export function engineUrlFetch(base: Awaited<ReturnType<typeof resolveEngineUrl>>): '
                                  'typeof fetch {\n'
                                  '  const { url, addresses } = base;\n'
                                  '  if (!addresses.length) return fetch;\n'
                                  '  return (input, init) => new Promise<Response>((resolve, reject) => {\n'
                                  '    const target = new URL(String(input));\n'
                                  '    if (target.origin !== url.origin) {\n'
                                  "      reject(new Error('Unexpected provider origin'));\n"
                                  '      return;\n'
                                  '    }\n'
                                  '    const req = httpsRequest(target, {\n'
                                  '      method: init?.method,\n'
                                  '      headers: init?.headers as Record<string, string>,\n'
                                  '      signal: init?.signal ?? undefined,\n'
                                  '      agent: false,\n'
                                  '      // Use only the validated addresses, while retaining the URL hostname for TLS.\n'
                                  '      lookup: (_hostname, options, callback) => {\n'
                                  '        if (options.all) callback(null, addresses);\n'
                                  '        else callback(null, addresses[0]!.address, addresses[0]!.family);\n'
                                  '      },\n'
                                  '    }, (res) => {\n'
                                  '      const status = res.statusCode ?? 502;\n'
                                  '      if (status >= 300 && status < 400) {\n'
                                  '        res.destroy();\n'
                                  "        reject(new Error('Provider redirected the request'));\n"
                                  '        return;\n'
                                  '      }\n'
                                  '      const chunks: Uint8Array[] = [];\n'
                                  '      let bytes = 0;\n'
                                  "      res.on('error', reject);\n"
                                  "      res.on('data', (chunk: Buffer) => {\n"
                                  '        bytes += chunk.length;\n'
                                  "        if (bytes > MAX_RESPONSE_BYTES) res.destroy(new Error('Provider response "
                                  "exceeded size limit'));\n"
                                  '        else chunks.push(chunk);\n'
                                  '      });\n'
                                  "      res.on('end', () => {\n"
                                  '        const noBody = status === 204 || status === 205;\n'
                                  "        const retryAfter = res.headers['retry-after'];\n"
                                  '        resolve(new Response(noBody ? null : Buffer.concat(chunks), {\n'
                                  '          status,\n'
                                  "          headers: retryAfter ? { 'retry-after': retryAfter } : {},\n"
                                  '        }));\n'
                                  '      });\n'
                                  '    });\n'
                                  "    req.on('error', reject);\n"
                                  '    req.end(init?.body as string | undefined);\n'
                                  '  });\n'
                                  '}\n'}

LOCK_BEFORE = {'node_modules/@types/node': {'version': '26.6.6',
                              'resolved': 'https://registry.npmjs.org/@types/node/-/node-26.6.6.tgz',
                              'integrity': 'sha512-MzQj+8Kx3XI40OmUAE6Qoh58ZMNstNNMwn2nfd3qWsfe7nDNSqJNzes4njhz6AHwrSHOffSLwXU6yb474Q4aog==',
                              'dev': True,
                              'license': 'MIT',
                              'dependencies': {'undici-types': '~8.9.0'}},
 'node_modules/undici-types': {'version': '8.9.0',
                               'resolved': 'https://registry.npmjs.org/undici-types/-/undici-types-8.9.0.tgz',
                               'integrity': 'sha512-KTDyRTYX8sWmKXAikPHHSyc63CRPETMctyjKFupcC6OBLXT3xsN0e9aF7m+mIXutFWpUXuedtowG7iLOzp0kQg==',
                               'dev': True,
                               'license': 'MIT'}}

LOCK_AFTER = {'node_modules/@types/node': {'version': '22.20.5',
                              'resolved': 'https://registry.npmjs.org/@types/node/-/node-22.20.5.tgz',
                              'integrity': 'sha512-U2+DNr+wSjpsTS/wZGYHq7GcwfuSmKiKvoPvK22zwTlRhU91yOniN4qRR5KhIjvif7ysw/dz/hKmfDH0Ris4aA==',
                              'dev': True,
                              'license': 'MIT',
                              'dependencies': {'undici-types': '~6.21.0'}},
 'node_modules/undici-types': {'version': '6.21.0',
                               'resolved': 'https://registry.npmjs.org/undici-types/-/undici-types-6.21.0.tgz',
                               'integrity': 'sha512-iwDZqg0QAGrg9Rav5H4n0M64c3mkR59cJ6wQp+7C4nI0gsmExaedaYLNO44eT4AtBBwjbTiGPMlt2Md0T9H9JQ==',
                               'dev': True,
                               'license': 'MIT'}}


class PatchError(Exception):
    """The current repository cannot safely accept the patch."""


@dataclass(frozen=True)
class Change:
    original: bytes | None
    updated: bytes


def find_root(start: Path | None) -> Path:
    starts = [start.resolve()] if start else [Path.cwd(), Path(__file__).resolve().parent]
    for directory in starts:
        for root in (directory, *directory.parents):
            package = root / 'package.json'
            if package.is_file():
                try:
                    if json.loads(package.read_text(encoding='utf-8')).get('name') == 'promptolog':
                        return root
                except (OSError, ValueError):
                    continue
    raise PatchError('Promptolog repository root not found. Pass --root PATH.')


def safe_path(root: Path, relative: str) -> Path:
    output = root / relative
    if output.resolve() != output or not output.is_relative_to(root):
        raise PatchError(f'Unexpected path or symlink: {relative}')
    return output


def replace_once(relative: str, text: str, old: str, new: str) -> str:
    matches = text.count(old)
    if text.count(new) == 1 and (matches == 0 or old in new):
        return text
    if matches == 1:
        return text.replace(old, new, 1)
    first_change = next((line[2:].strip() for line in difflib.ndiff(old.splitlines(), new.splitlines()) if line.startswith('- ')), old.splitlines()[0].strip())
    raise PatchError(f'{relative}: expected one source match near {first_change[:100]!r}. Found {matches}. Review against the supplied snapshot.')


def sync_lockfile(text: str, manifest: dict) -> str:
    lock = json.loads(text)
    packages = lock.get('packages', {})
    main = packages.get('', {})
    if lock.get('name') != manifest['name'] or main.get('version') != manifest['version']:
        raise PatchError('package-lock.json does not match the Promptolog manifest.')
    if main.get('dependencies') != manifest['dependencies']:
        raise PatchError('Unexpected production dependencies in package-lock.json.')
    expected = manifest['devDependencies']
    before = {**expected, '@types/node': '^26.6.6'}
    if main.get('devDependencies') not in (before, expected):
        raise PatchError('Unexpected devDependencies in package-lock.json.')
    if main.get('engines') not in ({'node': '>=22.5'}, manifest['engines']):
        raise PatchError('Unexpected Node engine declaration in package-lock.json.')

    # The npm-generated replacement is limited to the Node types and their sole dependency.
    for key, update in LOCK_AFTER.items():
        present = packages.get(key, {})
        prior = LOCK_BEFORE[key]
        # Registry URL and metadata can vary with npm and mirrors. The version
        # and dependency edges must match the tree verified for this update.
        if not any(
            present.get('version') == known['version']
            and present.get('dependencies', {}) == known.get('dependencies', {})
            for known in (prior, update)
        ):
            raise PatchError(f'Unexpected lockfile entry: {key}. Review the version before applying.')
        packages[key] = update if present.get('version') != update['version'] else present
    main['devDependencies'] = expected
    main['engines'] = manifest['engines']
    return json.dumps(lock, ensure_ascii=False, indent=2) + '\n'


def build_plan(root: Path) -> dict[str, Change]:
    plan: dict[str, Change] = {}

    def load(relative: str) -> bytes:
        try:
            return safe_path(root, relative).read_bytes()
        except FileNotFoundError as error:
            raise PatchError(f'Missing {relative}. Use the original repository checkout.') from error

    def queue(relative: str, original: bytes | None, updated: bytes) -> None:
        if original != updated:
            plan[relative] = Change(original, updated)

    def create(relative: str, updated: bytes) -> None:
        path = safe_path(root, relative)
        original = path.read_bytes() if path.exists() else None
        if original is not None and original != updated:
            raise PatchError(f'{relative} already exists with different contents.')
        queue(relative, original, updated)

    for relative, replacements in HUNKS.items():
        original = load(relative)
        text = original.decode('utf-8').replace('\r\n', '\n')
        for old, new in replacements:
            text = replace_once(relative, text, old, new)
        queue(relative, original, text.encode('utf-8'))

    for relative, text in NEW_FILES.items():
        create(relative, text.encode('utf-8'))

    package = plan.get('package.json')
    manifest = json.loads(package.updated if package else load('package.json'))
    lock = load('package-lock.json')
    queue('package-lock.json', lock, sync_lockfile(lock.decode('utf-8'), manifest).encode('utf-8'))

    docs = safe_path(root, 'scripts/docs_update.py')
    helpers = runpy.run_path(str(docs))
    changelog = load('CHANGELOG.md')
    text = helpers['changelog_add'](changelog.decode('utf-8'), {
        'Changed': [
            'Match the Node typings to the oldest supported runtime and use an ESM-native Vite config.',
            'Use shared Obsidian surfaces, fields, responsive grids and accessible browser dialogs across screens.',
            'List published model presets and accept account-specific model IDs for other providers.',
        ],
        'Fixed': [
            'Preserve engine settings on partial updates and send provider-compatible completion parameters.',
            'Serialize optimizer answers and compression, count clarification tokens, and retain the best saved compression.',
            'Keep copy, folder editing, filtering, navigation and long text usable on narrow screens.',
            'Use the response lifecycle for SSE cleanup and prevent repeated generation answers.',
        ],
        'Security': [
            'Resolve and pin checked public addresses for custom engine connections and clear saved provider keys on destination changes.',
            'Prevent shared caches from storing authenticated API responses.',
        ],
    })
    queue('CHANGELOG.md', changelog, text.encode('utf-8'))

    handoff = load('HANDOFF.md')
    text = helpers['handoff_apply'](
        handoff.decode('utf-8'), PATCH_DATE,
        decisions=[
            'Production audit: Node 22.12+ is the declared minimum and the platform target stays Node 24. The dependency lock keeps its existing graph except for the Node typings and their dependency.',
            'Custom engine connections use validated public DNS addresses through TLS. Changing the provider or effective URL requires a fresh provider key.',
        ],
        limitations=[
            'Third-party billing, external provider access, iframe host placement, and scheduler delivery still require a smoke test in the target Bitrix24 environment. The iframe resize message is documented by the platform.',
        ],
        patches=[f'{PATCH_ID}: production audit for persistence, provider settings, responsive UI and dependency compatibility'],
    )
    queue('HANDOFF.md', handoff, text.encode('utf-8'))

    create(f'patches/{PATCH_FILE}', Path(__file__).read_bytes())
    return plan


def show_plan(plan: dict[str, Change], diff: bool) -> None:
    for relative, change in plan.items():
        print(f'{"update" if change.original is not None else "create"}  {relative}')
        if diff:
            if relative == f'patches/{PATCH_FILE}':
                continue  # The archive is an exact copy of the running patch.
            before = (change.original or b'').decode('utf-8').splitlines(True)
            after = change.updated.decode('utf-8').splitlines(True)
            sys.stdout.writelines(difflib.unified_diff(before, after, f'a/{relative}', f'b/{relative}'))


def atomic_write(path: Path, contents: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o644
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        try:
            handle.write(contents)
            handle.close()
            temporary.chmod(mode)
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)


def apply_plan(root: Path, plan: dict[str, Change], backup: bool) -> None:
    for relative, change in plan.items():
        path = safe_path(root, relative)
        current = path.read_bytes() if path.exists() else None
        if current != change.original:
            raise PatchError(f'{relative} changed during patch validation. Run the patch again.')

    if backup:
        for relative, change in plan.items():
            if change.original is None:
                continue
            target = safe_path(root, f'.patch-backup/{PATCH_ID}/{relative}')
            if not target.exists():
                atomic_write(target, change.original)

    written = []
    try:
        for relative, change in plan.items():
            atomic_write(safe_path(root, relative), change.updated)
            written.append(relative)
    except (OSError, PatchError, KeyboardInterrupt):
        for relative in reversed(written):
            path = safe_path(root, relative)
            original = plan[relative].original
            if original is None:
                path.unlink()
            else:
                atomic_write(path, original)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--root', type=Path)
    parser.add_argument('--dry-run', action='store_true', help='validate the entire plan without writing')
    parser.add_argument('--diff', action='store_true', help='show the planned source diffs')
    parser.add_argument('--no-backup', action='store_true')
    parser.add_argument('--commit', action='store_true', help='commit only the files changed by this run')
    args = parser.parse_args()
    if args.dry_run and args.commit:
        parser.error('--commit cannot be used with --dry-run')

    try:
        root = find_root(args.root)
        plan = build_plan(root)
        if not plan:
            print('Nothing to do')
            return 0
        show_plan(plan, args.diff)
        if args.dry_run:
            print(f'Dry run: {len(plan)} files planned.')
            return 0
        if args.commit:
            subprocess.run(['git', 'rev-parse', '--is-inside-work-tree'], cwd=root, check=True, capture_output=True)
        apply_plan(root, plan, not args.no_backup)
        print(f'Applied {PATCH_ID}: {len(plan)} files.')
        if args.commit:
            paths = list(plan)
            subprocess.run(['git', 'add', '--', *paths], cwd=root, check=True)
            subprocess.run(['git', 'commit', '--only', '-m', COMMIT_MESSAGE, '--', *paths], cwd=root, check=True)
        return 0
    except (PatchError, OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f'Patch error: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
