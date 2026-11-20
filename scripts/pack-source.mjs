#!/usr/bin/env node
// Creates deliverables/promptolog-source-v<version>.zip with every file needed to build, deploy and hand over the project.
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';

const root = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
const version = JSON.parse(fs.readFileSync(path.join(root, 'package.json'), 'utf8')).version;
const out = path.join(root, 'deliverables', `promptolog-source-v${version}.zip`);
const EXCLUDE_DIRS = new Set(['node_modules', '.git', 'dist', 'deliverables', 'data', 'coverage', '.vite']);
const EXCLUDE_FILE = (n) => n === '.env' || (n.startsWith('.env.') && n !== '.env.example') || /\.(db|db-wal|db-shm|log)$/.test(n) || n === '.DS_Store' || n === 'job_secret';
const files = [];
(function walk(dir) { for (const e of fs.readdirSync(dir, { withFileTypes: true })) { if (e.isDirectory()) { if (!EXCLUDE_DIRS.has(e.name)) walk(path.join(dir, e.name)); } else if (!EXCLUDE_FILE(e.name)) files.push(path.relative(root, path.join(dir, e.name))); } })(root);
files.sort();
fs.mkdirSync(path.dirname(out), { recursive: true }); fs.rmSync(out, { force: true });
execFileSync('zip', ['-q', '-X', out, '-@'], { cwd: root, input: files.join('\n') });
const sha = createHash('sha256').update(fs.readFileSync(out)).digest('hex');
console.log(JSON.stringify({ path: path.relative(root, out), sha256: sha, bytes: fs.statSync(out).size, files: files.length }, null, 2));
