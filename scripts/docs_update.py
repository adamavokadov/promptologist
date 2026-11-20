#!/usr/bin/env python3
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
