#!/usr/bin/env node
// WCAG contrast audit for apps/web/src/styles/tokens.css (no dependencies).
// Text pairs need 4.5:1, non-text pairs 3:1. Translucent colors are composited over the surface they sit on.
// Exits non-zero on any failure.
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const css = readFileSync(resolve(root, 'apps/web/src/styles/tokens.css'), 'utf8').replace(/\/\*[\s\S]*?\*\//g, '');

function block(selector) {
  const start = css.indexOf(selector);
  if (start < 0) throw new Error(`selector not found: ${selector}`);
  const open = css.indexOf('{', start);
  const close = css.indexOf('}', open);
  const vars = {};
  for (const m of css.slice(open + 1, close).matchAll(/(--[\w-]+)\s*:\s*([^;]+);/g)) vars[m[1]] = m[2].trim();
  return vars;
}
const light = block(":root, :root[data-theme='light'] {");
const themes = { light, dark: { ...light, ...block(":root[data-theme='dark']") } };

function resolveVar(vars, name, depth = 0) {
  const raw = vars[name];
  if (raw === undefined || depth > 8) throw new Error(`unresolved token ${name}`);
  const ref = raw.match(/^var\((--[\w-]+)\)$/);
  return ref ? resolveVar(vars, ref[1], depth + 1) : raw;
}
// -> { rgb: [r,g,b], a }
function parse(v) {
  const hex = v.match(/^#([0-9a-fA-F]{6})$/);
  if (hex) return { rgb: [0, 2, 4].map((i) => parseInt(hex[1].slice(i, i + 2), 16)), a: 1 };
  const m = v.match(/^rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*([\d.]+)\s*)?\)$/);
  if (m) return { rgb: [+m[1], +m[2], +m[3]], a: m[4] === undefined ? 1 : +m[4] };
  throw new Error(`unsupported color: ${v}`);
}
const over = (top, under) => top.a >= 1 ? top.rgb : top.rgb.map((c, i) => Math.round(top.a * c + (1 - top.a) * under[i]));
const lin = (c) => { const s = c / 255; return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4; };
const lum = ([r, g, b]) => 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
const ratioRgb = (a, b) => { const [x, y] = [lum(a), lum(b)]; return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };

// fg on bg, where a translucent bg sits on `under` (a solid surface token).
function contrast(vars, fg, bg, under) {
  const base = parse(resolveVar(vars, under));
  const bgRgb = over(parse(resolveVar(vars, bg)), base.rgb);
  const fgRgb = over(parse(resolveVar(vars, fg)), bgRgb);
  return ratioRgb(fgRgb, bgRgb);
}

const T = 4.5, N = 3;
const solids = ['--color-canvas', '--color-surface', '--color-surface-secondary', '--color-elevated'];
const tints = [['--color-success-text', '--color-success-bg'], ['--color-warning', '--color-warning-bg'], ['--color-danger', '--color-danger-bg'], ['--color-accent-text', '--color-info-bg']];
const pairs = []; // [fg, bg, under, min, kind]
const add = (fg, bg, min, kind, under = bg) => pairs.push([fg, bg, under, min, kind]);
for (const s of solids) {
  for (const f of ['--color-text-primary', '--color-text-secondary', '--color-text-muted', '--color-accent-text', '--color-success-text', '--color-warning', '--color-danger']) add(f, s, T, 'text');
  add('--color-control-border', s, N, 'non-text');
  add('--color-focus', s, N, 'non-text');
}
for (const s of solids.slice(0, 2)) {
  add('--viz-series-primary', s, N, 'non-text'); add('--viz-series-neutral', s, N, 'non-text'); add('--color-accent', s, N, 'non-text');
  for (const [f, b] of tints) add(f, b, T, 'tint text', s);
}
add('--color-on-accent', '--color-accent', T, 'text'); add('--color-on-accent', '--color-accent-hover', T, 'text');
add('--color-text-primary', '--color-accent-soft', T, 'text'); add('--color-accent-text', '--color-accent-soft', T, 'text');
for (const [, b] of tints) add('--color-text-primary', b, T, 'tint text', '--color-surface');

let failed = 0;
const rows = [];
for (const theme of Object.keys(themes)) {
  const vars = themes[theme];
  for (const [fg, bg, under, min, kind] of pairs) {
    const r = contrast(vars, fg, bg, under);
    const ok = r >= min;
    if (!ok) failed++;
    rows.push(`${ok ? 'PASS' : 'FAIL'}  ${theme.padEnd(5)} ${kind.padEnd(10)} ${r.toFixed(2).padStart(5)} (min ${min})  ${fg} on ${bg}${under !== bg ? ' over ' + under : ''}`);
  }
  // Heat-map cell text: the best of primary text, on-accent and canvas must reach 4.5 (analytics brief §7.2).
  for (let i = 1; i <= 5; i++) {
    const best = Math.max(...['--color-text-primary', '--color-on-accent', '--color-canvas'].map((f) => contrast(vars, f, `--viz-ramp-${i}`, '--color-canvas')));
    const ok = best >= T;
    if (!ok) failed++;
    rows.push(`${ok ? 'PASS' : 'FAIL'}  ${theme.padEnd(5)} ramp-${i} text ${best.toFixed(2).padStart(5)} (min ${T})  best of primary / on-accent / canvas on --viz-ramp-${i}`);
  }
}
console.log(rows.join('\n'));
console.log(`\n${rows.length - failed}/${rows.length} checks pass`);
process.exit(failed ? 1 : 0);
