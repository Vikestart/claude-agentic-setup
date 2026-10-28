#!/usr/bin/env python3
"""Lay down a repository's document skeleton: AGENTS.md, CLAUDE.md importing it, .docs/.

The rule is that every repository a session works in carries its own rules in AGENTS.md (read by
other harnesses and, through a one-line `@AGENTS.md` import in CLAUDE.md, by Claude Code), its working
documents in .docs/ and its permanent knowledge in .docs/reference/. Without them a session keeps
its plan in its head, the next session rediscovers the repository from the code, and the two
harnesses drift onto different rules. Creating the files by hand each time is mechanical, so this
does it from templates/docs/ and leaves only the judgement - what the project is for - to fill in.

    python $HOME/.claude/skills/asdev-web-audit/scripts/docs_init.py --path .            create whatever is missing
    python $HOME/.claude/skills/asdev-web-audit/scripts/docs_init.py --path . --check    report only
    python $HOME/.claude/skills/asdev-web-audit/scripts/docs_init.py --path . --link     also prepend the import

Never overwrites a file. A CLAUDE.md without the import is reported, not edited, unless `--link`.
A CLAUDE.md holding its own rules gets no AGENTS.md skeleton next to it: which of those rules move
is a judgement, and a blank AGENTS.md beside them would read as done.
`missing(root)` is the importable check.
Exit 0 complete, 1 something still missing or wrong, 2 operational.
"""

from __future__ import annotations

import argparse
import datetime
import sys
from pathlib import Path

TEMPLATES = Path(__file__).resolve().parent.parent / "templates" / "docs"
IMPORT = "@AGENTS.md"
BOM = b"\xef\xbb\xbf"
# handover.md is written only when the user asks for a handover (handover.py), so it has no stub.
DOCS = ("implementation_plan.md", "task.md", "roadmap.md", "changelog.md")
# (target relative to the repository, template relative to TEMPLATES)
FILES = (("AGENTS.md", "AGENTS.md"), ("CLAUDE.md", "CLAUDE.md"),
         *((f".docs/{name}", name) for name in DOCS))


def _claude_lines(root: Path) -> list[str] | None:
    """CLAUDE.md's non-blank lines, stripped; None when there is no CLAUDE.md."""
    path = root / "CLAUDE.md"
    if not path.is_file():
        return None
    try:
        text = path.read_bytes().decode("utf-8-sig", "replace")
    except OSError:
        return []
    return [line.strip() for line in text.splitlines() if line.strip()]


def _own_rules(lines: list[str] | None) -> bool:
    return bool(lines) and any(line != IMPORT for line in lines)


def missing(root) -> list[str]:
    """Human-readable list of what the repository at `root` lacks; empty when complete."""
    root = Path(root)
    lines = _claude_lines(root)
    out: list[str] = []
    if not (root / "AGENTS.md").is_file():
        out.append("AGENTS.md (move CLAUDE.md's rules into it)" if _own_rules(lines) else "AGENTS.md")
    if lines is None:
        out.append("CLAUDE.md")
    elif IMPORT not in lines:
        out.append(f"the {IMPORT} import in CLAUDE.md")
    if not (root / ".docs").is_dir():
        out.append(".docs/ (working documents and reference/)")
    else:
        out += [target for target, _ in FILES[2:] if not (root / target).is_file()]
    return out


def _render(template: str, root: Path) -> bytes:
    text = (TEMPLATES / template).read_text(encoding="utf-8")
    text = text.replace("<Project>", root.resolve().name)
    return text.replace("<YYYY-MM-DD>", datetime.date.today().isoformat()).encode("utf-8")


def _link(path: Path) -> None:
    """Prepend the import in the file's own line endings, after any BOM."""
    raw = path.read_bytes()
    bom = BOM if raw.startswith(BOM) else b""
    eol = b"\r\n" if b"\r\n" in raw else b"\n"
    # Rewritten in place rather than temp-plus-rename, which would decouple a hard-linked CLAUDE.md.
    path.write_bytes(bom + IMPORT.encode() + eol + eol + raw[len(bom):])


def init(root: Path, link: bool) -> list[str]:
    """Create what is missing; return one line per item created, linked or still wrong."""
    report: list[str] = []
    own_rules = _own_rules(_claude_lines(root))
    for target, template in FILES:
        path = root / target
        if path.exists():
            continue
        if target == "AGENTS.md" and own_rules:
            report.append("TODO    AGENTS.md - CLAUDE.md holds its own rules: move them into AGENTS.md "
                          "and leave CLAUDE.md as the import (not created)")
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as fh:  # "x": never overwrite, even one created since the check
            fh.write(_render(template, root))
        report.append(f"created {target}")
    lines = _claude_lines(root)
    if lines is not None and IMPORT not in lines:
        if link:
            _link(root / "CLAUDE.md")
            report.append(f"linked  CLAUDE.md - prepended {IMPORT}")
        else:
            report.append(f"WRONG   CLAUDE.md has no {IMPORT} line - re-run with --link to prepend it")
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Create a repository's AGENTS.md, CLAUDE.md and .docs/ "
                                             "skeleton from templates; never overwrites.")
    ap.add_argument("--path", default=".", help="repository root (default: .)")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="report only; exit 1 if anything is missing")
    mode.add_argument("--link", action="store_true", help=f"prepend {IMPORT} to a CLAUDE.md lacking it")
    args = ap.parse_args(argv)
    root = Path(args.path)
    if not root.is_dir():
        print(f"error: {root} is not a directory", file=sys.stderr)
        return 2
    if args.check:
        gaps = missing(root)
        for gap in gaps:
            print(f"MISSING {gap}")
        print(f"docs_init: {len(gaps)} missing or wrong" if gaps else "docs_init: ok - complete")
        return 1 if gaps else 0
    if not all((TEMPLATES / template).is_file() for _, template in FILES):
        print(f"error: templates incomplete under {TEMPLATES}", file=sys.stderr)
        return 2
    try:
        report = init(root, args.link)
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    for line in report:
        print(line)
    gaps = missing(root)
    print(f"docs_init: {len(gaps)} still missing or wrong: {', '.join(gaps)}" if gaps
          else "docs_init: ok - complete")
    return 1 if gaps else 0


if __name__ == "__main__":
    sys.exit(main())
