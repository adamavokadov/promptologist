#!/usr/bin/env python3
"""Patch 2026-11-20: Karpathy-style agent-graph seed template + repository hygiene + scripted docs.

Run from the repo root (idempotent, stdlib only, two-phase: everything is validated in memory first,
nothing is written if any anchor is missing):

    python3 patch_2026-11-20_agent-graph-and-hygiene.py --dry-run     # preview
    python3 patch_2026-11-20_agent-graph-and-hygiene.py               # apply (backups in .patch-backup/)
    python3 patch_2026-11-20_agent-graph-and-hygiene.py --commit      # apply + git add/commit

What it does:
  1. Adds the Spanish agent-graph prompt (Karpathy autoresearch-inspired, Opus 5.5) as seed template #9.
  2. Updates tests / smoke script / README / OPERATIONS for 9 seed templates; adds seed-template tests.
  3. Adds .editorconfig, .gitattributes, .nvmrc, .devcontainer, CI workflow, repomix.config.json; extends .gitignore.
  4. Installs scripts/docs_update.py + `docs:*` npm scripts, and updates CHANGELOG.md / HANDOFF.md through it.
"""
from __future__ import annotations

import argparse
import difflib
import json
import pathlib
import re
import shutil
import subprocess
import sys
import types

PATCH_ID = "2026-11-20-agent-graph-and-hygiene"
PATCH_DATE = "2026-11-20"

TEMPLATE_TITLE = "Граф узлов для Claude Code (по Karpathy, Opus 5.5)"
TEMPLATE_DESC = (
    "Испанский шаблон: задача раскладывается на граф ограниченных узлов с субагентами, проверочными «воротами» и файлами "
    "graph.md / checks.md / progress.md. Заметка про Claude Code и графы агентов; идея из autoresearch Андрея Карпати "
    "(одного из основателей OpenAI), рассчитан на Opus 5.5. Текст на испанском, поэтому язык помечен EN."
)
TEMPLATE_TAGS = ["agent", "claude-code", "graph", "karpathy", "es", "research"]
TEMPLATE_VARS = ["alcance", "checks", "fuentes", "limite", "salida", "tarea"]

DOCS_UPDATE_SRC = r'''#!/usr/bin/env python3
"""Scripted maintenance of CHANGELOG.md and HANDOFF.md (stdlib only, idempotent).

Project rule: these two files are NEVER edited by hand; every change goes through this tool.

Usage (run from the repo root):
  python3 scripts/docs_update.py changelog --added "text" --changed "text" --fixed "text" [--version Unreleased]
  python3 scripts/docs_update.py release 1.1.0 [--date YYYY-MM-DD] [--no-bump]
  python3 scripts/docs_update.py handoff --decision "text" --limitation "text" --patch "id: summary" --sub "old" "new"
Common flags (placed AFTER the subcommand): --dry-run prints a diff instead of writing; --date YYYY-MM-DD; --root PATH.
Re-running the same command changes nothing (entries are matched by exact text).
"""
from __future__ import annotations

import argparse
import datetime
import difflib
import json
import pathlib
import re
import sys

CATEGORIES = ["Added", "Changed", "Deprecated", "Removed", "Fixed", "Security"]
CHANGELOG_HEAD = (
    "# Changelog\n\nAll notable changes to this project are documented here. "
    "Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), "
    "versioning: [SemVer](https://semver.org/).\n"
)
HANDOFF_MAINTENANCE_TITLE = "## 15. Scripted maintenance"
HANDOFF_MAINTENANCE_BODY = (
    "CHANGELOG.md and HANDOFF.md are maintained ONLY by `scripts/docs_update.py` (stdlib Python, idempotent). "
    "Never edit them by hand.\n"
    "```\n"
    "python3 scripts/docs_update.py changelog --added \"...\" --changed \"...\" --fixed \"...\"   # into [Unreleased]\n"
    "python3 scripts/docs_update.py release X.Y.Z                                           # [Unreleased] -> [X.Y.Z], bumps package.json/lock\n"
    "python3 scripts/docs_update.py handoff --decision \"...\" --limitation \"...\" --patch \"id: summary\"\n"
    "python3 scripts/docs_update.py handoff --sub \"old text\" \"new text\"                      # exact, idempotent substitution\n"
    "```\n"
    "Add `--dry-run` after the subcommand to preview a diff. Patch scripts live in `patches/` and call the same functions."
)
HANDOFF_PATCHLOG_TITLE = "## 16. Patch log"


# ---------------------------------------------------------------- changelog
def _split(text: str):
    parts = re.split(r"(?m)^(?=## \[)", text)
    return parts[0], parts[1:]


def _parse_section(section: str):
    heading, _, body = section.partition("\n")
    preamble: list[str] = []
    cats: dict[str, list[str]] = {}
    cur = None
    for line in body.split("\n"):
        if line.startswith("### "):
            cur = line[4:].strip()
            cats.setdefault(cur, [])
        elif cur is None:
            preamble.append(line)
        else:
            cats[cur].append(line)
    for k in cats:
        while cats[k] and not cats[k][-1].strip():
            cats[k].pop()
        while cats[k] and not cats[k][0].strip():
            cats[k].pop(0)
    return heading.rstrip(), "\n".join(preamble).strip("\n"), cats


def _render_section(heading: str, preamble: str, cats: dict[str, list[str]]) -> str:
    out = [heading, ""]
    if preamble.strip():
        out += [preamble, ""]
    for name, lines in cats.items():
        if lines:
            out += [f"### {name}"] + lines + [""]
    return "\n".join(out).rstrip("\n") + "\n\n"


def _join(head: str, sections: list[str]) -> str:
    return head.rstrip("\n") + "\n\n" + "".join(sections).rstrip("\n") + "\n"


def changelog_add(text: str, entries: dict[str, list[str]], version: str = "Unreleased", date: str | None = None) -> str:
    if not text.strip():
        text = CHANGELOG_HEAD
    head, sections = _split(text)
    idx = next((i for i, s in enumerate(sections) if s.startswith(f"## [{version}]")), None)
    if idx is None:
        heading = f"## [{version}]" + (f" - {date}" if version != "Unreleased" and date else "")
        sections.insert(1 if (sections and sections[0].startswith("## [Unreleased]") and version != "Unreleased") else 0, heading + "\n\n")
        idx = 1 if (len(sections) > 1 and sections[0].startswith("## [Unreleased]") and version != "Unreleased") else 0
    heading, preamble, cats = _parse_section(sections[idx])
    for cat in CATEGORIES:
        items = entries.get(cat, [])
        for item in items:
            line = f"- {item}"
            bucket = cats.setdefault(cat, [])
            if line not in [b.strip() for b in bucket]:
                bucket.append(line)
    sections[idx] = _render_section(heading, preamble, cats)
    return _join(head, sections)


def changelog_release(text: str, version: str, date: str) -> str:
    head, sections = _split(text)
    if any(s.startswith(f"## [{version}]") for s in sections):
        raise SystemExit(f"error: version {version} already exists in CHANGELOG.md")
    idx = next((i for i, s in enumerate(sections) if s.startswith("## [Unreleased]")), None)
    if idx is None:
        raise SystemExit("error: no [Unreleased] section in CHANGELOG.md")
    _, preamble, cats = _parse_section(sections[idx])
    if not any(cats.values()) and not preamble.strip():
        raise SystemExit("error: [Unreleased] is empty, nothing to release")
    released = _render_section(f"## [{version}] - {date}", preamble, cats)
    sections[idx] = "## [Unreleased]\n\n" + released
    return _join(head, sections)


def bump_package_version(root: pathlib.Path, version: str, dry: bool = False) -> list[str]:
    done = []
    pj = root / "package.json"
    if pj.exists():
        t = pj.read_text(encoding="utf-8")
        n = re.sub(r'("version"\s*:\s*)"[^"]*"', rf'\g<1>"{version}"', t, count=1)
        if n != t:
            done.append("package.json")
            if not dry:
                pj.write_text(n, encoding="utf-8")
    lock = root / "package-lock.json"
    if lock.exists():
        data = json.loads(lock.read_text(encoding="utf-8"))
        changed = False
        if data.get("version") != version:
            data["version"] = version
            changed = True
        root_pkg = data.get("packages", {}).get("")
        if root_pkg is not None and root_pkg.get("version") != version:
            root_pkg["version"] = version
            changed = True
        if changed:
            done.append("package-lock.json")
            if not dry:
                lock.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return done


# ------------------------------------------------------------------ handoff
def handoff_stamp(text: str, date: str) -> str:
    line = f"_Last scripted update: {date}. Release history: CHANGELOG.md._"
    if re.search(r"(?m)^_Last scripted update: .*_$", text):
        return re.sub(r"(?m)^_Last scripted update: .*_$", line, text, count=1)
    m = re.match(r"# [^\n]*\n", text)
    if not m:
        return line + "\n\n" + text
    return m.group(0) + "\n" + line + "\n" + text[m.end():]


def _section_span(text: str, prefix: str):
    m = re.search(rf"(?m)^## {re.escape(prefix)}[^\n]*\n", text)
    if not m:
        return None
    nxt = re.search(r"(?m)^## ", text[m.end():])
    end = m.end() + nxt.start() if nxt else len(text)
    return m.end(), end


def handoff_numbered(text: str, prefix: str, item: str) -> str:
    span = _section_span(text, prefix)
    if span is None:
        raise SystemExit(f"error: HANDOFF.md has no section '## {prefix}'")
    start, end = span
    body = text[start:end]
    if f". {item}" in body:
        return text
    nums = [int(n) for n in re.findall(r"(?m)^(\d+)\. ", body)]
    new_body = body.rstrip("\n") + f"\n{max(nums, default=0) + 1}. {item}\n\n"
    return text[:start] + new_body + text[end:]


def handoff_bullet(text: str, title: str, body_if_new: str, line: str) -> str:
    prefix = title[3:].split(" ", 1)[0]
    if _section_span(text, prefix) is None:
        text = text.rstrip("\n") + f"\n\n{title}\n{body_if_new}\n\n"
    start, end = _section_span(text, prefix)
    body = text[start:end]
    if f"- {line}" in body:
        return text
    return text[:start] + body.rstrip("\n") + f"\n- {line}\n\n" + text[end:]


def handoff_sub(text: str, old: str, new: str) -> str:
    if new in text:
        return text
    if text.count(old) != 1:
        raise SystemExit(f"error: anchor must occur exactly once in HANDOFF.md (found {text.count(old)}): {old[:70]!r}")
    return text.replace(old, new, 1)


def handoff_apply(text: str, date: str, decisions=(), limitations=(), patches=(), subs=()) -> str:
    for old, new in subs:
        text = handoff_sub(text, old, new)
    for d in decisions:
        text = handoff_numbered(text, "12.", d)
    for lim in limitations:
        text = handoff_numbered(text, "10.", lim)
    if _section_span(text, "15.") is None:
        text = text.rstrip("\n") + f"\n\n{HANDOFF_MAINTENANCE_TITLE}\n{HANDOFF_MAINTENANCE_BODY}\n\n"
    for p in patches:
        text = handoff_bullet(text, HANDOFF_PATCHLOG_TITLE, "Applied patch scripts (newest last); sources in `patches/`.", f"{date} {p}")
    return handoff_stamp(text, date).rstrip("\n") + "\n"


# ---------------------------------------------------------------------- cli
def _emit(path: pathlib.Path, old: str, new: str, dry: bool) -> None:
    if old == new:
        print(f"unchanged  {path.name}")
        return
    if dry:
        sys.stdout.writelines(difflib.unified_diff(old.splitlines(True), new.splitlines(True), f"a/{path.name}", f"b/{path.name}"))
    else:
        path.write_text(new, encoding="utf-8")
        print(f"updated    {path.name}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--root", default=str(pathlib.Path(__file__).resolve().parents[1]))
    common.add_argument("--dry-run", action="store_true")
    common.add_argument("--date", default=datetime.date.today().isoformat())
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("changelog", parents=[common])
    c.add_argument("--version", default="Unreleased")
    for cat in CATEGORIES:
        c.add_argument(f"--{cat.lower()}", action="append", default=[], metavar="TEXT")
    r = sub.add_parser("release", parents=[common])
    r.add_argument("version")
    r.add_argument("--no-bump", action="store_true")
    h = sub.add_parser("handoff", parents=[common])
    h.add_argument("--decision", action="append", default=[], metavar="TEXT")
    h.add_argument("--limitation", action="append", default=[], metavar="TEXT")
    h.add_argument("--patch", action="append", default=[], metavar="ID: SUMMARY")
    h.add_argument("--sub", action="append", default=[], nargs=2, metavar=("OLD", "NEW"))
    a = ap.parse_args(argv)
    root = pathlib.Path(a.root)
    cl, ho = root / "CHANGELOG.md", root / "HANDOFF.md"
    if a.cmd == "changelog":
        entries = {cat: getattr(a, cat.lower()) for cat in CATEGORIES}
        if not any(entries.values()):
            ap.error("give at least one of --added/--changed/--deprecated/--removed/--fixed/--security")
        old = cl.read_text(encoding="utf-8") if cl.exists() else ""
        _emit(cl, old, changelog_add(old, entries, a.version, a.date), a.dry_run)
    elif a.cmd == "release":
        old = cl.read_text(encoding="utf-8")
        _emit(cl, old, changelog_release(old, a.version, a.date), a.dry_run)
        if not a.no_bump:
            print("version bumped in:", ", ".join(bump_package_version(root, a.version, a.dry_run)) or "(already current)")
    else:
        old = ho.read_text(encoding="utf-8")
        _emit(ho, old, handoff_apply(old, a.date, a.decision, a.limitation, a.patch, [tuple(s) for s in a.sub]), a.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''

PROMPT_ES = r'''<objetivo>
Resuelve {{TAREA}} como un grafo de nodos acotados, no como una sola sesión larga. Deja un resultado usable, un informe de verificación y un graph.md para que otra sesión pueda repetirlo o ampliarlo. Define qué es «terminado» antes de empezar. Para cuando todos los nodos pasen sus checks o se llegue al límite pactado.
</objetivo>

<rol>
Eres quien diseña, ejecuta y mantiene el grafo. Lee primero las instrucciones del proyecto y revisa el trabajo existente antes de tocar nada. Planifica e integra tú; delega en subagentes trabajo con límites claros. Anota cada decisión que cambie el grafo.
</rol>

<principios>
Ideas tomadas del autoresearch de Karpathy:
- Mide una línea base antes de cambiar el sistema.
- Cada nodo: un alcance claro y un evaluador fijo.
- Cambia una cosa, midela y quédate con lo que mejore. Registra también los intentos fallidos.
- Mejor pocos nodos si así los resultados se pueden comparar.
</principios>

<entradas>
Tarea: {{TAREA}}
Entregable y ruta: {{SALIDA}}
Criterios de aceptación: {{CHECKS}}
Material de partida: {{FUENTES}}
Cambios permitidos: {{ALCANCE}}
Límite de ejecución: {{LIMITE}}
Rellénalas antes de empezar. Si falta un dato que cambia el resultado, haz una sola pregunta concreta.
</entradas>

<capa_1_division>
Parte {{TAREA}} en nodos antes de trabajar. Un nodo = un trabajo acotado: una entrada, una salida, un check.
- Divide por lo que cada nodo necesita leer, no por carpetas.
- Solo hay arista si un nodo usa la salida de otro.
- Los nodos sin arista entre sí van en paralelo.
Escribe nodos, aristas y checks en graph.md y espera aprobación.
</capa_1_division>

<capa_2_nodos>
Cada nodo corre en su propio subagente, solo con el contexto que necesita:
1. Recibe su especificación, entradas y check.
2. Construye únicamente su artefacto.
3. Pasa su check contra el archivo guardado.
4. Devuelve ruta, veredicto y evidencia.
Que las especificaciones sirvan para otros datos de entrada.
</capa_2_nodos>

<capa_3_nodos_de_codigo>
Si un paso tiene una única respuesta correcta (unir, ordenar, deduplicar, contar), hazlo con código, no con el modelo. El modelo es solo para juzgar.
- Lista cada nodo de código en graph.md.
- Nada determinista pasa por un subagente.
Si falta una herramienta, nombra el bloqueo y conserva los nodos que sí se pueden completar.
</capa_3_nodos_de_codigo>

<capa_4_permisos>
Comprueba los permisos activos antes de lanzar el grafo. Las ediciones, dentro de {{ALCANCE}}. Usa reglas de herramientas o sandbox cuando haga falta imponerlo; ejecutar en solitario no es un límite.
- Pregunta antes de publicar, enviar o gastar.
- Nunca dos sesiones editando el mismo archivo.
- Guarda una versión recuperable antes de fusiones arriesgadas.
</capa_4_permisos>

<capa_5_puertas>
Pon una puerta en cada arista con trabajo arriesgado. Solo se abre con evidencia: primero checks deterministas, luego el informe del nodo y, en último lugar, la confianza del modelo.
Guarda checks.md con una fila por requisito:
nodo | requisito | veredicto | evidencia
Usa pasa, falla o sin resolver. Incluye rutas o la salida real del check. Que la evidencia que falte se vea.
</capa_5_puertas>

<capa_6_vueltas>
Dos caminos de vuelta.
Corrección: una puerta fallida devuelve el trabajo al nodo que lo hizo, con motivo, evidencia y el alcance «arregla solo este nodo». Máximo tres intentos.
Aprendizaje: tras un resultado aceptado, apunta en graph.md la regla que confirma, para que la siguiente ejecución parta de ahí.
</capa_6_vueltas>

<capa_7_cierre>
Antes de ejecutar, crea una checklist de cierre a partir de {{CHECKS}}, con evidencia observable en cada punto:
- La salida de cada nodo existe y se puede abrir.
- Cada puerta se pasó sobre la versión guardada.
- Los fallos están arreglados o declarados.
- CLAUDE.md recoge las reglas de esta ejecución.
Si un límite o bloqueo corta la ejecución, devuelve un estado parcial con los pasos exactos pendientes.
</capa_7_cierre>

<bucle_de_ejecucion>
1. Lee graph.md y elige los nodos listos.
2. Lanza en paralelo los independientes.
3. Pasa cada salida por su puerta.
4. Devuelve los nodos fallidos, nunca el lote entero.
5. Integra lo aceptado y corre los checks completos.
6. Sigue hasta terminar, bloquearte o llegar a {{LIMITE}}.
Nunca rebajes una puerta para conseguir un aprobado.
</bucle_de_ejecucion>

<relevo>
Tras cada fase, actualiza progress.md:
Grafo: nodos hechos, en curso y bloqueados.
Salidas: rutas exactas en los archivos guardados.
Decisiones: qué cambió en graph.md y por qué.
Pendientes: fallos, dudas y bloqueos.
Siguiente acción: el próximo nodo listo.
Al retomar, lee graph.md y progress.md y sigue desde ahí.
</relevo>

<entrega>
Devuelve {{SALIDA}}, graph.md, checks.md y progress.md. Di qué se comprobó, qué pasó y qué queda abierto. Guarda el grafo como plantilla reutilizable. Informa del consumo medido solo si lo tienes; no deduzcas ahorros a partir del prompt.
</entrega>'''

NEW_FILES: dict[str, str] = {
    ".editorconfig": """root = true

[*]
charset = utf-8
end_of_line = lf
indent_style = space
indent_size = 2
insert_final_newline = true
trim_trailing_whitespace = true

[*.md]
trim_trailing_whitespace = false

[*.py]
indent_size = 4
""",
    ".gitattributes": """* text=auto eol=lf
*.woff binary
*.woff2 binary
*.png binary
*.jpg binary
*.ico binary
*.zip binary
*.db binary
package-lock.json linguist-generated=true
""",
    ".nvmrc": "24\n",
    ".devcontainer/devcontainer.json": """{
  "name": "promptolog",
  "image": "mcr.microsoft.com/devcontainers/base:ubuntu",
  "features": {
    "ghcr.io/devcontainers/features/node:1": { "version": "24" },
    "ghcr.io/devcontainers/features/python:1": { "version": "3.12" },
    "ghcr.io/devcontainers/features/github-cli:1": {}
  },
  "forwardPorts": [3000, 5173],
  "postCreateCommand": "npm ci || npm install",
  "customizations": {
    "vscode": {
      "extensions": ["editorconfig.editorconfig", "bradlc.vscode-tailwindcss", "vitest.explorer"]
    }
  }
}
""",
    ".github/workflows/ci.yml": """name: CI

on:
  push:
  pull_request:
  workflow_dispatch:

permissions:
  contents: read

concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true

jobs:
  build-test:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        node: [22, 24]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: ${{ matrix.node }}
          cache: npm
      - run: npm ci
      - run: npm run build
      - run: npm test
""",
    "repomix.config.json": """{
  "output": {
    "filePath": "repomix-output.xml",
    "style": "xml"
  },
  "ignore": {
    "useGitignore": true,
    "useDefaultPatterns": true,
    "customPatterns": ["deliverables/**", "patches/**", "*.zip"]
  }
}
""",
    "scripts/docs_update.py": DOCS_UPDATE_SRC,
}
OVERWRITE = {"scripts/docs_update.py"}

GITIGNORE_BLOCK = """# --- hygiene (patch 2026-11-20) ---
.env.*
!.env.example
/data/
coverage/
.vite/
*.tsbuildinfo
job_secret
.DS_Store
Thumbs.db
.idea/
.vscode/
*.swp
*.orig
*.rej
repomix-output.*
.patch-backup/
"""

SEED_TESTS = """

describe('seed templates', () => {
  it('have unique titles, valid variables and fit the template limits', () => {
    const titles = SEED_TEMPLATES.map((t) => t.title);
    expect(new Set(titles).size).toBe(titles.length);
    for (const t of SEED_TEMPLATES) {
      expect(validateTemplateVariables(t.body).ok, t.title).toBe(true);
      expect(t.body.length, t.title).toBeLessThanOrEqual(LIMITS.template);
      expect(t.description.length, t.title).toBeLessThanOrEqual(400);
      expect(t.tags.length, t.title).toBeLessThanOrEqual(8);
    }
  });
  it('agent-graph template keeps its six variables and every layer of the prompt', () => {
    const t = SEED_TEMPLATES.find((x) => x.tags.includes('karpathy'))!;
    expect(t).toBeDefined();
    expect(extractVariables(t.body).sort()).toEqual(['alcance', 'checks', 'fuentes', 'limite', 'salida', 'tarea']);
    for (const tag of ['objetivo', 'rol', 'principios', 'entradas', 'capa_1_division', 'capa_2_nodos', 'capa_3_nodos_de_codigo', 'capa_4_permisos', 'capa_5_puertas', 'capa_6_vueltas', 'capa_7_cierre', 'bucle_de_ejecucion', 'relevo', 'entrega']) {
      expect(t.body, tag).toContain(`<${tag}>`);
      expect(t.body, tag).toContain(`</${tag}>`);
    }
    expect(substituteVariables(t.body, { tarea: 'X' })).toContain('Resuelve X como');
  });
});
"""

CHANGELOG_ENTRIES = {
    "Added": [
        "Seed template «" + TEMPLATE_TITLE + "»: Spanish agent-graph prompt inspired by Andrej Karpathy's autoresearch (bounded nodes, deterministic code nodes, evidence gates, graph.md / checks.md / progress.md handoff) with variables `{{tarea}}`, `{{salida}}`, `{{checks}}`, `{{fuentes}}`, `{{alcance}}`, `{{limite}}`; flagged EN because template language supports only ru/en.",
        "Tests: seed-template invariants (unique titles, valid variables, size limits) and a structure test for the agent-graph template.",
        "Repository hygiene: `.editorconfig`, `.gitattributes`, `.nvmrc`, `.devcontainer/devcontainer.json` (Node 24, Python 3), `.github/workflows/ci.yml` (build and test on Node 22 and 24), `repomix.config.json`.",
        "`scripts/docs_update.py` and `docs:*` npm scripts: idempotent scripted updates of CHANGELOG.md and HANDOFF.md; applied patch scripts are archived in `patches/`.",
    ],
    "Changed": [
        ".gitignore extended (env variants, data dir, coverage, tsbuildinfo, job_secret, OS/IDE files, repomix output, patch backups).",
        "Seed template count 8 -> 9 in tests (now derived from `SEED_TEMPLATES.length`), smoke script, README and OPERATIONS.",
    ],
}
HANDOFF_SUBS = [
    ("8 seed templates (Russian/English)", "9 seed templates (Russian/English/Spanish body)"),
    (
        "scripts/deploy.mjs smoke.mjs pack-source.mjs\ntests/core.test.ts pipeline.test.ts helpers.ts",
        "scripts/deploy.mjs smoke.mjs pack-source.mjs docs_update.py   (docs_update.py = scripted CHANGELOG/HANDOFF maintenance)\n"
        "tests/core.test.ts pipeline.test.ts helpers.ts\n"
        "patches/                            applied patch scripts (see section 16)\n"
        ".github/workflows/ci.yml, .devcontainer/devcontainer.json, .editorconfig, .gitattributes, .nvmrc, repomix.config.json   repo hygiene",
    ),
]
HANDOFF_DECISIONS = [
    "The Karpathy-inspired agent-graph prompt (Opus 5.5) ships as a seed TEMPLATE, not as skill content: skills are fed only from whitelisted official vendor sources and are rewritten by the refresh agent, so third-party guidance would be lost or rejected. Seed templates are inserted by title at start (`seedAll`), so existing databases receive it automatically.",
    "The template body is kept in Spanish verbatim (only the `<prompt>` wrapper of the source note is dropped). Variables are lower-cased (`{{tarea}}`, ...) because `VAR_RE` accepts only `[a-z0-9_]`; `language` is `'en'` because templates support only ru/en.",
    "CHANGELOG.md and HANDOFF.md are updated only through `scripts/docs_update.py` (owner's standing rule); patch scripts import the same logic and are archived in `patches/`.",
]
HANDOFF_LIMITATIONS = [
    "Template `language` supports only ru|en: the Spanish agent-graph template is flagged EN, so sending it to the generator selects English output. Spanish output is not a supported language.",
    "Repomix excludes `package-lock.json` by default, so repomix packs do not show the lockfile; it must stay committed (`npm ci` needs it).",
]
HANDOFF_PATCHES = [PATCH_ID + ": agent-graph seed template, 9 seed templates in tests/smoke/docs, repo hygiene files, scripted docs tool"]


class Plan:
    def __init__(self, root: pathlib.Path):
        self.root, self.files, self.errors = root, {}, []

    def disk(self, rel: str):
        p = self.root / rel
        return p.read_text(encoding="utf-8") if p.is_file() else None

    def read(self, rel: str):
        return self.files[rel] if rel in self.files else self.disk(rel)

    def set(self, rel: str, text: str):
        self.files[rel] = text

    def err(self, msg: str):
        self.errors.append(msg)

    def replace_once(self, rel: str, old: str, new: str, marker: str | None = None):
        t = self.read(rel)
        if t is None:
            return self.err(f"{rel}: file not found")
        if (marker or new) in t:
            return
        n = t.count(old)
        if n != 1:
            return self.err(f"{rel}: anchor found {n}x (expected 1): {old[:70]!r}")
        self.set(rel, t.replace(old, new, 1))


def find_root(start: pathlib.Path) -> pathlib.Path:
    for d in [start, *start.parents]:
        pj = d / "package.json"
        if pj.is_file():
            try:
                if json.loads(pj.read_text(encoding="utf-8")).get("name") == "promptolog":
                    return d
            except ValueError:
                pass
    raise SystemExit("error: run this from inside the promptolog repo (package.json with name 'promptolog' not found)")


def js_str(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)


def build_template_entry(plan: Plan) -> str:
    body = re.sub(r"\{\{([A-Z0-9_]+)\}\}", lambda m: "{{" + m.group(1).lower() + "}}", PROMPT_ES.strip())
    found = sorted(set(re.findall(r"\{\{([a-z0-9_]+)\}\}", body)))
    if found != TEMPLATE_VARS:
        plan.err(f"template variables {found} != {TEMPLATE_VARS}")
    if len(body) > 16000 or len(TEMPLATE_DESC) > 400 or len(TEMPLATE_TAGS) > 8:
        plan.err("template exceeds LIMITS (body 16000 / description 400 / tags 8)")
    tags = "[" + ", ".join(f"'{x}'" for x in TEMPLATE_TAGS) + "]"
    return (
        f"  {{ title: {js_str(TEMPLATE_TITLE)}, description: {js_str(TEMPLATE_DESC)}, language: 'en', default_systems: ['claude'], tags: {tags},\n"
        f"    body: {js_str(body)} }},\n"
    )


def build_plan(root: pathlib.Path) -> Plan:
    plan = Plan(root)
    du = types.ModuleType("docs_update")
    exec(compile(DOCS_UPDATE_SRC, "docs_update.py", "exec"), du.__dict__)

    # 1) new files (never overwrite existing ones except the docs tool)
    for rel, content in NEW_FILES.items():
        cur = plan.disk(rel)
        if cur is None or (rel in OVERWRITE and cur != content):
            plan.set(rel, content)

    # 2) .gitignore: keep everything, append what is missing
    gi = plan.disk(".gitignore") or ""
    have = {ln.strip() for ln in gi.splitlines()}
    missing = [ln for ln in GITIGNORE_BLOCK.splitlines() if ln.strip() and not ln.startswith("#") and ln.strip() not in have]
    if missing:
        block = ["# --- hygiene (patch 2026-11-20) ---"] + missing
        plan.set(".gitignore", gi.rstrip("\n") + ("\n\n" if gi.strip() else "") + "\n".join(block) + "\n")

    # 3) seed template
    rel = "apps/server/src/seed/templates.ts"
    t = plan.read(rel)
    if t is None:
        plan.err(f"{rel}: file not found")
    elif js_str(TEMPLATE_TITLE) not in t:
        i = t.rfind("\n];")
        if i < 0:
            plan.err(f"{rel}: closing '];' of SEED_TEMPLATES not found")
        else:
            plan.set(rel, t[: i + 1] + build_template_entry(plan) + t[i + 1:])

    # 4) tests
    plan.replace_once("tests/pipeline.test.ts",
        "import { SYSTEM_IDS, type GenOptions } from '../shared/src/index.ts';",
        "import { SYSTEM_IDS, type GenOptions } from '../shared/src/index.ts';\nimport { SEED_TEMPLATES } from '../apps/server/src/seed/templates.ts';",
        marker="import { SEED_TEMPLATES }")
    plan.replace_once("tests/pipeline.test.ts", "it('lists 5 skills and 8 seed templates'", "it('lists 5 skills and every seed template'")
    plan.replace_once("tests/pipeline.test.ts", "expect(t).toHaveLength(8);", "expect(t).toHaveLength(SEED_TEMPLATES.length);")
    plan.replace_once("tests/core.test.ts",
        "import { DAY_MS, HOUR_MS } from '../apps/server/src/util.ts';",
        "import { DAY_MS, HOUR_MS } from '../apps/server/src/util.ts';\nimport { SEED_TEMPLATES } from '../apps/server/src/seed/templates.ts';\nimport { LIMITS } from '../shared/src/index.ts';",
        marker="import { SEED_TEMPLATES }")
    ct = plan.read("tests/core.test.ts")
    if ct is not None and "describe('seed templates'" not in ct:
        plan.set("tests/core.test.ts", ct.rstrip("\n") + "\n" + SEED_TESTS)

    # 5) smoke script, README, OPERATIONS
    plan.replace_once("scripts/smoke.mjs",
        "await check('8 seed templates present', async () => { const b = await j('/api/templates'); const n = b.items.filter((t) => t.is_seed).length; if (n !== 8) throw new Error(`got ${n}`); });",
        "const EXPECTED_SEED_TEMPLATES = 9; // keep in sync with SEED_TEMPLATES.length\n"
        "await check(`${EXPECTED_SEED_TEMPLATES} seed templates present`, async () => { const b = await j('/api/templates'); const n = b.items.filter((t) => t.is_seed).length; if (n !== EXPECTED_SEED_TEMPLATES) throw new Error(`got ${n}`); });",
        marker="EXPECTED_SEED_TEMPLATES = 9")
    plan.replace_once("README.md", "8 seed templates, JSON export and template import", "9 seed templates, JSON export and template import")
    plan.replace_once("README.md",
        "| `npm run pack:source` | create `deliverables/promptolog-source-v<version>.zip` |",
        "| `npm run pack:source` | create `deliverables/promptolog-source-v<version>.zip` |\n"
        "| `npm run pack:repomix` | pack the repo into `repomix-output.xml` (`repomix.config.json`) |\n"
        "| `npm run docs:changelog -- --added \"...\"` | scripted CHANGELOG.md update (`scripts/docs_update.py`); CHANGELOG/HANDOFF are never edited by hand |\n"
        "| `npm run docs:handoff -- --decision \"...\"` | scripted HANDOFF.md update (decisions, limitations, patch log) |\n"
        "| `npm run docs:release -- X.Y.Z` | turn `[Unreleased]` into a release and bump `package.json` / lockfile version |",
        marker="docs_update.py")
    plan.replace_once("OPERATIONS.md", "5 skills, 8 seed templates", "5 skills, 9 seed templates")

    # 6) package.json scripts (formatting-preserving)
    plan.replace_once("package.json",
        '    "pack:source": "node scripts/pack-source.mjs"\n  },',
        '    "pack:source": "node scripts/pack-source.mjs",\n'
        '    "pack:repomix": "npx --yes repomix",\n'
        '    "docs:changelog": "python3 scripts/docs_update.py changelog",\n'
        '    "docs:handoff": "python3 scripts/docs_update.py handoff",\n'
        '    "docs:release": "python3 scripts/docs_update.py release"\n  },',
        marker='"docs:changelog"')
    pj = plan.read("package.json")
    if pj is not None:
        try:
            json.loads(pj)
        except ValueError as e:
            plan.err(f"package.json would be invalid JSON: {e}")

    # 7) CHANGELOG / HANDOFF through the docs tool
    cl = plan.read("CHANGELOG.md")
    if cl is None:
        plan.err("CHANGELOG.md: file not found")
    else:
        plan.set("CHANGELOG.md", du.changelog_add(cl, CHANGELOG_ENTRIES, "Unreleased", PATCH_DATE))
    ho = plan.read("HANDOFF.md")
    if ho is None:
        plan.err("HANDOFF.md: file not found")
    else:
        try:
            plan.set("HANDOFF.md", du.handoff_apply(ho, PATCH_DATE, HANDOFF_DECISIONS, HANDOFF_LIMITATIONS, HANDOFF_PATCHES, HANDOFF_SUBS))
        except SystemExit as e:
            plan.err(f"HANDOFF.md: {e}")
    return plan


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="validate and list changes, write nothing")
    ap.add_argument("--diff", action="store_true", help="with --dry-run: print unified diffs of existing files")
    ap.add_argument("--commit", action="store_true", help="git add -A && git commit after applying")
    ap.add_argument("--no-backup", action="store_true", help="skip .patch-backup/ copies")
    ap.add_argument("--root", default=None)
    a = ap.parse_args()

    root = find_root(pathlib.Path(a.root).resolve() if a.root else pathlib.Path.cwd())
    plan = build_plan(root)
    if plan.errors:
        print("PATCH ABORTED, nothing written:")
        for e in plan.errors:
            print("  -", e)
        return 1

    changes = [(rel, plan.disk(rel), new) for rel, new in sorted(plan.files.items()) if plan.disk(rel) != new]
    if not changes:
        print("Nothing to do: patch already applied.")
        return 0
    for rel, old, new in changes:
        print(f"{'create' if old is None else 'update'}  {rel}")
        if a.dry_run and a.diff and old is not None:
            sys.stdout.writelines(list(difflib.unified_diff(old.splitlines(True), new.splitlines(True), f"a/{rel}", f"b/{rel}"))[:60])
    if a.dry_run:
        print("\n--dry-run: nothing written.")
        return 0

    if not a.no_backup:
        for rel, old, _ in changes:
            if old is not None:
                dst = root / ".patch-backup" / PATCH_ID / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(root / rel, dst)
    for rel, _, new in changes:
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(new, encoding="utf-8", newline="\n")
    me = pathlib.Path(__file__).resolve()
    archive = root / "patches" / me.name
    if me != archive and not archive.exists():
        archive.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(me, archive)
        print(f"archive  patches/{me.name}")
    print(f"\nApplied {len(changes)} file change(s). Next: npm ci && npm run build && npm test")

    if a.commit:
        try:
            subprocess.run(["git", "add", "-A"], cwd=root, check=True)
            subprocess.run(["git", "commit", "-m", "chore: agent-graph seed template, repo hygiene, scripted docs"], cwd=root, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            print("git commit failed:", e)
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
