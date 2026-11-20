import {
  LIMITS, REQUIRED_SKILL_SECTIONS, PROTECTED_INVARIANTS, SYSTEM_IDS, SYSTEM_NAMES, detectPromptLanguage,
  type SystemId, type SkillDTO, type SkillStatus,
} from '../../../shared/src/index.ts';
import { type Db, type Row } from './db.ts';
import { uid, nowIso, jsonParse, randBetween } from './util.ts';
import { SEED_SKILLS, seedFrontmatter } from './seed/skills.ts';
import { SEED_TEMPLATES } from './seed/templates.ts';
import { extractVariables } from '../../../shared/src/index.ts';
import { computeNextCheck } from './scheduler.ts';
import { indexDoc } from './db.ts';

export interface SkillVersion {
  id: string; skill_id: SystemId; version: number; frontmatter: Record<string, any>; body_md: string;
  changelog: { change: string; reason: string; source_url: string }[]; sources: { url: string; title: string; checked_at: string }[];
  origin: 'seed' | 'agent' | 'rollback'; golden_result: any; created_at: string;
}
export const rowToVersion = (r: Row): SkillVersion => ({
  id: r.id, skill_id: r.skill_id, version: r.version, frontmatter: jsonParse(r.frontmatter, {}), body_md: r.body_md,
  changelog: jsonParse(r.changelog, []), sources: jsonParse(r.sources, []), origin: r.origin, golden_result: jsonParse(r.golden_result, null), created_at: r.created_at,
});

export function seedAll(db: Db, rand: (min: number, max: number) => number = randBetween): void {
  db.tx(() => {
    for (const s of SEED_SKILLS) {
      if (db.get('SELECT id FROM skills WHERE id = ?', s.id)) continue;
      const vid = uid(); const now = nowIso();
      db.run('INSERT INTO skill_versions(id, skill_id, version, frontmatter, body_md, changelog, sources, origin, created_at) VALUES(?,?,?,?,?,?,?,?,?)',
        vid, s.id, 1, JSON.stringify(seedFrontmatter(s, 1)), s.body_md, JSON.stringify([{ change: 'Initial seed from the product brief digest', reason: 'seed', source_url: s.sources[0]!.url }]), JSON.stringify(s.sources), 'seed', now);
      db.run('INSERT INTO skills(id, display_name, current_version_id, model_lineup, sources, last_check_at, next_check_at, status, created_at, updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)',
        s.id, s.display_name, vid, JSON.stringify(s.model_lineup), JSON.stringify(s.sources), null,
        computeNextCheck(new Date(), rand).toISOString(), 'fresh', now, now);
    }
    for (const t of SEED_TEMPLATES) {
      if (db.get('SELECT id FROM templates WHERE is_seed = 1 AND title = ?', t.title)) continue;
      const id = uid(); const now = nowIso();
      db.run('INSERT INTO templates(id, user_id, title, description, body, language, default_systems, tags, is_seed, usage_count, created_at, updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
        id, null, t.title, t.description, t.body, t.language, JSON.stringify(t.default_systems), JSON.stringify(t.tags), 1, 0, now, now);
      indexDoc(db, 'tpl', id, null, `${t.title} ${t.body}`);
    }
  });
}

export function getCurrentVersion(db: Db, skillId: SystemId): SkillVersion {
  const r = db.get('SELECT v.* FROM skill_versions v JOIN skills s ON s.current_version_id = v.id WHERE s.id = ?', skillId);
  if (!r) throw new Error(`Skill ${skillId} has no current version`);
  return rowToVersion(r);
}
export const getVersionById = (db: Db, id: string): SkillVersion | null => { const r = db.get('SELECT * FROM skill_versions WHERE id = ?', id); return r ? rowToVersion(r) : null; };
export const listVersions = (db: Db, skillId: string): SkillVersion[] =>
  db.all('SELECT * FROM skill_versions WHERE skill_id = ? ORDER BY version DESC', skillId).map(rowToVersion);

export const REFRESH_COOLDOWN_MS = 6 * 3_600_000;
export function skillToDto(db: Db, row: Row, now = Date.now(), busy = false): SkillDTO {
  const v = getCurrentVersion(db, row.id);
  const lastManual = db.get<{ started_at: string }>("SELECT started_at FROM refresh_runs WHERE skill_id = ? AND trigger = 'manual' ORDER BY started_at DESC LIMIT 1", row.id);
  let blocked: string | null = null;
  if (row.status === 'running' || busy) blocked = 'busy';
  else if (lastManual && now - Date.parse(lastManual.started_at) < REFRESH_COOLDOWN_MS) blocked = 'cooldown';
  let status = row.status as SkillStatus;
  if (row.paused) status = 'paused';
  else if (status === 'fresh' && row.next_check_at && Date.parse(row.next_check_at) <= now) status = 'due';
  return {
    id: row.id, display_name: row.display_name, current_version: v.version, current_version_id: v.id,
    model_lineup: jsonParse(row.model_lineup, []), last_check_at: row.last_check_at, next_check_at: row.next_check_at, status,
    paused: !!row.paused, consecutive_failures: row.consecutive_failures, changelog: v.changelog, can_refresh: blocked === null, refresh_blocked_reason: blocked,
  };
}

// ---------- checklist ----------
export interface ChecklistItem { text: string; has: string[]; hasAny: string[][] }
export function sectionOf(body: string, heading: string): string {
  const i = body.indexOf(heading);
  if (i < 0) return '';
  const rest = body.slice(i + heading.length);
  const next = rest.search(/\n## /);
  return next < 0 ? rest : rest.slice(0, next);
}
export function parseChecklist(body: string): ChecklistItem[] {
  const items: ChecklistItem[] = [];
  for (const line of sectionOf(body, '## Validation Checklist').split('\n')) {
    const t = line.trim();
    if (!/^[-*]\s+/.test(t) && !/^\d+\.\s+/.test(t)) continue;
    const has: string[] = []; const hasAny: string[][] = [];
    for (const m of t.matchAll(/`has:([^`]+)`/g)) has.push(m[1]!);
    for (const m of t.matchAll(/`has-any:([^`]+)`/g)) hasAny.push(m[1]!.split('|').filter(Boolean));
    items.push({ text: t.replace(/^[-*\d.]+\s+/, ''), has, hasAny });
  }
  return items;
}
const LEAK_PATTERNS = [/Ты — Промптолог/i, /<raw_request>/i, /единственный источник правил/i, /Skill is the only source/i, /Верни ТОЛЬКО JSON по схеме/i];
export function runChecklist(skillBody: string, promptText: string, language: 'ru' | 'en'): { ok: boolean; errors: string[] } {
  const errors: string[] = [];
  const lower = promptText.toLowerCase();
  if (promptText.trim().length < 20) errors.push('Prompt is empty or too short');
  if (promptText.length > LIMITS.promptText) errors.push(`Prompt exceeds ${LIMITS.promptText} characters`);
  for (const p of LEAK_PATTERNS) if (p.test(promptText)) errors.push('Prompt leaks the transformer meta-prompt');
  const lang = detectPromptLanguage(promptText);
  if (language === 'ru' && lang === 'en') errors.push('Prompt must be written in Russian');
  if (language === 'en' && lang === 'ru') errors.push('Prompt must be written in English');
  const directive = language === 'ru' ? /(на русском|по-русски|русск\w+ язык|in russian|russian)/i : /(in english|english|respond in en|write in en)/i;
  if (!directive.test(promptText)) errors.push(`Prompt lacks an explicit ${language === 'ru' ? 'Russian' : 'English'} language directive`);
  const items = parseChecklist(skillBody);
  for (const it of items) {
    for (const h of it.has) if (!lower.includes(h.toLowerCase())) errors.push(`Missing required marker "${h}"`);
    for (const group of it.hasAny) if (!group.some((h) => lower.includes(h.toLowerCase()))) errors.push(`Missing one of markers: ${group.join(' | ')}`);
  }
  return { ok: errors.length === 0, errors };
}

// ---------- draft validation (agent output) ----------
const norm = (s: string) => s.replace(/\s+/g, ' ').trim().toLowerCase();
export function validateSkillDraft(opts: { body: string; frontmatter: Record<string, any>; whitelist: string[]; changelog: { source_url: string }[] }): string[] {
  const errors: string[] = [];
  const { body } = opts;
  if (body.length > LIMITS.skillBody) errors.push(`Skill body exceeds ${LIMITS.skillBody} chars`);
  for (const sec of REQUIRED_SKILL_SECTIONS) if (!body.includes(sec)) errors.push(`Missing section ${sec}`);
  const nb = norm(body);
  for (const inv of PROTECTED_INVARIANTS) if (!nb.includes(norm(inv))) errors.push(`Protected invariant missing or weakened: "${inv}"`);
  const items = parseChecklist(body);
  if (items.length < 5 || items.length > 10) errors.push(`Validation Checklist must have 5-10 items (found ${items.length})`);
  for (const c of opts.changelog) {
    let host = '';
    try { host = new URL(c.source_url).hostname; } catch { /* invalid */ }
    if (!host || !opts.whitelist.some((d) => host === d || host.endsWith(`.${d}`))) errors.push(`Changelog source not in whitelist: ${c.source_url}`);
  }
  return errors;
}

export function allSkillIds(): readonly SystemId[] { return SYSTEM_IDS; }
export const displayName = (id: SystemId) => SYSTEM_NAMES[id];
export { extractVariables };
