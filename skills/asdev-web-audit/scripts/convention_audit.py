"""High-confidence checks derived from the shared webdev conventions.

Only rules that are objective and cheap live here. Contextual choices such as
API architecture, auth design, responsive intent, and native-select exceptions
remain review work rather than regex policy.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _common import (  # noqa: E402
    Report, ReadError, cli, iter_files, read_text, scope_active,
    scope_contains_prefix,
)


CODE_EXTS = (".php", ".phtml", ".html", ".htm", ".js", ".mjs", ".ts", ".css")
BASE64_IMAGE = re.compile(r"data:image/(?:svg\+xml|png|jpe?g|gif|webp);base64", re.I)
INLINE_SVG = re.compile(r"<svg\b", re.I)
# An <svg> that only points into an icon file (`<svg ...><use href="sprite.svg#name">`) is how a
# sprite is used, not a drawing in code; a drawn shape on the same line still counts as inline.
SPRITE_REF = re.compile(r"<svg\b[^>]*>\s*<use\b[^>]*\bhref\s*=", re.I)
SVG_SHAPE = re.compile(r"<(?:path|circle|rect|line|polyline|polygon|ellipse|g)\b", re.I)
JQUERY_DEPENDENCY = re.compile(
    r"<script\b[^>]*\bsrc\s*=\s*['\"][^'\"]*jquery"
    r"|\b(?:import\s+.*?\s+from\s+|require\s*\()\s*['\"]jquery(?:/[^'\"]*)?['\"]",
    re.I,
)
RANDOM_CACHE_BUST = re.compile(
    # The gap must not cross a tag or statement boundary. With a bare `.{0,100}?` it bridged out of
    # a URL, past `">x</a><?php $started = `, into an unrelated `time()` — flagging a stable `?v=2`.
    r"[?&](?:v|ver|version|cb|_)=[^>;]{0,100}?\b(?:time|microtime|rand|mt_rand|uniqid|random_int|"
    r"Date\.now|Math\.random)\s*\(",
    re.I,
)
# Project-specific rules are DATA, not code: they name one author's projects, so they live in the
# optional `local/project-rules.json` overlay. Absent — the normal state on any other machine — this
# scanner runs its generic rules only and reports nothing project-specific.
_RULES_PATH = Path(__file__).resolve().parent.parent / "local" / "project-rules.json"


def _load_project_rules() -> list:
    if not _RULES_PATH.is_file():
        return []
    try:
        data = json.loads(_RULES_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"convention_audit: ignoring unreadable {_RULES_PATH.name}: {exc}", file=sys.stderr)
        return []
    rules = data.get("rules")
    return [r for r in rules if isinstance(r, dict)] if isinstance(rules, list) else []


def _project(root: str, rules: list) -> str:
    """Which configured project this checkout is, matched on a path component."""
    names = {str(r.get("project", "")).casefold() for r in rules if r.get("project")}
    parts = {part.casefold() for part in Path(root).resolve().parts}
    for name in sorted(names):
        if name in parts:
            return name
    return ""


def run(args) -> Report:
    report = Report("convention_audit")
    root = args.path
    project_rules = _load_project_rules()
    project = _project(root, project_rules)
    active = [r for r in project_rules if str(r.get("project", "")).casefold() == project] if project else []
    line_rules = [(r, re.compile(r["pattern"], re.I)) for r in active
                  if r.get("kind") == "line_pattern" and r.get("pattern")]

    for rel in iter_files(CODE_EXTS, root):
        path = os.path.join(root, rel)
        try:
            text = read_text(path)
        except ReadError as exc:
            report.unread(rel, str(exc))
            continue
        report.scanned += 1

        for number, line in enumerate(text.splitlines(), 1):
            if BASE64_IMAGE.search(line):
                report.add(rel, number, "BASE64_IMAGE",
                           "embedded base64 image; store it under the asset directory")
            if INLINE_SVG.search(line) and not (SPRITE_REF.search(line) and not SVG_SHAPE.search(line)):
                report.add(rel, number, "INLINE_SVG",
                           "raw inline SVG; store SVG assets under the asset directory")
            if JQUERY_DEPENDENCY.search(line):
                report.add(rel, number, "JQUERY_DEPENDENCY",
                           "jQuery dependency introduced into a vanilla project")
            if RANDOM_CACHE_BUST.search(line):
                report.add(rel, number, "RANDOM_CACHE_BUST",
                           "per-request random cache bust; use a stable version or filemtime()")
            for rule, pattern in line_rules:
                if pattern.search(line):
                    report.add(rel, number, rule["code"], rule["message"])

        for rule in active:
            if (rule.get("kind") == "filename_case"
                    and rel.casefold().startswith(str(rule.get("path_prefix", "")).casefold())
                    and rel.casefold().endswith(str(rule.get("suffix", "")).casefold())
                    and os.path.basename(rel) != os.path.basename(rel).casefold()):
                report.add(rel, None, rule["code"], rule["message"])

    if scope_active():
        for rule in active:
            if rule.get("kind") != "lockstep":
                continue
            paths = [p for p in rule.get("paths", []) if p]
            changed = [p for p in paths if scope_contains_prefix(p)]
            if changed and len(changed) != len(paths):
                missing = next(p for p in paths if p not in changed)
                report.add(missing, None, rule["code"], rule["message"])

    return report


if __name__ == "__main__":
    cli(run, "Check high-confidence shared and project-specific conventions.")
