#!/usr/bin/env python3
"""Print exactly the named functions, methods, blocks or banner sections of a PHP, JS or Python
file, or the named sections and bold list items of a Markdown file, with line numbers — several in
one call.

WHY THIS EXISTS. Agents paged through huge files with `sed -n X,Yp` and ranged reads, guessing
ranges and re-reading to find an end (tilspire `tests/run.php`, 27k lines, 80+ slices in one
night). `code_map.py` finds the item; this prints it whole and nothing else.

A target is:
  * a name — `func`, `Class::method` or `Class.method` (either separator, any language), or a bare
    method or closure name when only one item has it;
  * a block or banner label substring, or the name given to a check()/test()/it() call inside a
    block (case-insensitive); in Markdown, a heading or bold list-item substring;
  * `@LINE` — the innermost item containing that line.

    python $HOME/.claude/skills/asdev-web-audit/scripts/code_show.py includes/lesson_authoring.php saveLesson Course::load
    python $HOME/.claude/skills/asdev-web-audit/scripts/code_show.py tests/run.php "store audit: two packages" @3012
    python $HOME/.claude/skills/asdev-web-audit/scripts/code_show.py app.js render --all --context 3
    python $HOME/.claude/skills/asdev-web-audit/scripts/code_show.py .docs/implementation_plan.md "Phase 15" Verification

An unknown target lists the 5 closest names; an ambiguous one lists its candidates (or prints them
all with --all). Either exits 1 after printing the targets that did resolve. Exit 2 for a missing
file or an unsupported extension. Read-only.
"""
from __future__ import annotations

import argparse
import difflib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from code_map import LABEL_KINDS, MapError, describe, load  # noqa: E402

SUGGEST = 5
CANDIDATES_SHOWN = 20


def _norm(name: str) -> str:
    return name.replace("::", ".")


def _short(name: str) -> str:
    return _norm(name).rsplit(".", 1)[-1].lstrip("$").lower()


def resolve(items: list, target: str) -> list:
    """Every item the target can mean, best stage first: exact name, short name, label or tag."""
    if target.startswith("@") and target[1:].isdigit():
        line = int(target[1:])
        hits = [it for it in items if it.start <= line <= it.end]
        return [min(hits, key=lambda it: (it.size, -it.depth))] if hits else []
    exact = [it for it in items if _norm(it.name) == _norm(target)]
    if exact:
        return exact
    short = target.lstrip("$").lower()
    by_short = [it for it in items if it.kind not in LABEL_KINDS and
                (_short(it.name) == short or _norm(it.name).lower() == _norm(target).lower())]
    if by_short:
        return by_short
    t = target.lower()
    return [it for it in items if it.kind in LABEL_KINDS and
            (t in it.name.lower() or any(t in tag.lower() for tag in it.tags))]


def suggestions(items: list, target: str) -> list:
    pool: dict = {}
    for it in items:
        pool.setdefault(it.name.lower(), it)
    close = difflib.get_close_matches(target.lower(), list(pool), n=SUGGEST, cutoff=0.0)
    return [pool[c] for c in close]


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file")
    ap.add_argument("targets", nargs="+", metavar="target")
    ap.add_argument("--context", type=int, default=0, metavar="N", help="extra lines before and after")
    ap.add_argument("--all", action="store_true", help="print every candidate of an ambiguous target")
    a = ap.parse_args()
    try:
        fm = load(a.file)
    except MapError as e:
        print(f"code_show: {e}", file=sys.stderr)
        return 2
    n = len(fm.lines)
    width = len(str(n))
    failed = 0
    for target in a.targets:
        hits = resolve(fm.items, target)
        if not hits:
            failed += 1
            if target.startswith("@") and target[1:].isdigit():
                print(f"code_show: line {target[1:]} is not inside any item of {fm.path.name} "
                      f"({n} lines)")
                continue
            print(f"code_show: unknown target {target!r} in {fm.path.name}; closest:")
            for it in suggestions(fm.items, target):
                print(f"  {describe(it)}  {it.kind}  {it.start}-{it.end}")
            continue
        if len(hits) > 1 and not a.all:
            failed += 1
            print(f"code_show: ambiguous target {target!r} - {len(hits)} candidates "
                  f"(use a qualified name, @LINE, or --all):")
            for it in hits[:CANDIDATES_SHOWN]:
                print(f"  {describe(it)}  {it.kind}  {it.start}-{it.end}")
            if len(hits) > CANDIDATES_SHOWN:
                print(f"  ... {len(hits) - CANDIDATES_SHOWN} more")
            continue
        for it in hits:
            lo, hi = max(1, it.start - a.context), min(n, it.end + a.context)
            print(f"=== {describe(it)} ({it.kind}) {fm.path.name}:{it.start}-{it.end}, "
                  f"{it.size} lines ===")
            for ln in range(lo, hi + 1):
                print(f"{ln:>{width}}  {fm.lines[ln - 1].rstrip(chr(13))}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
