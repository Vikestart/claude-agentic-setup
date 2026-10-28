#!/usr/bin/env python3
"""Move finished tasks out of .docs/task.md, verbatim, into a dated archive file.

The rule says finished tasks leave task.md, yet a task list re-read after every compaction kept
fifteen ticked items in the work setup (2026-10-21): pruning by hand is the step that gets
skipped. This does it: each `- [x]` item, with its indented continuation and sub-items, moves to
.docs/reference/archive/<YYYY-MM>/tasks-done.md under a heading for today, so the record survives
in a folder that has no git history. An item that still holds an open `- [ ]` sub-item stays.
The changelog stays one line per completed phase, which is a summary - so that line is yours to
write; the tool only reminds you.

    python $HOME/.claude/skills/asdev-web-audit/scripts/tasks_done.py --path .            move them
    python $HOME/.claude/skills/asdev-web-audit/scripts/tasks_done.py --path . --check    report only

Exit 0 nothing (left) to move, 1 `--check` found finished tasks, 2 operational.
"""

from __future__ import annotations

import argparse
import datetime
import re
import sys
from pathlib import Path

ITEM = re.compile(r"^(\s*)[-*] \[([ xX])\] ")


def split(lines: list[str]) -> tuple[list[str], list[str]]:
    """(lines to keep, finished items' lines); an item runs on over the non-blank lines indented deeper."""
    keep: list[str] = []
    done: list[str] = []
    i = 0
    while i < len(lines):
        m = ITEM.match(lines[i])
        if not m:
            keep.append(lines[i])
            i += 1
            continue
        indent = len(m.group(1))
        j = i + 1
        while j < len(lines) and lines[j].strip() and len(lines[j]) - len(lines[j].lstrip()) > indent:
            j += 1
        block = lines[i:j]
        finished = m.group(2) in "xX" and not any(
            (s := ITEM.match(ln)) and s.group(2) == " " for ln in block[1:])
        if finished:
            done.extend(block)
        else:
            keep.append(block[0])
            # The children of an open item are judged one by one.
            sub_keep, sub_done = split(block[1:])
            keep.extend(sub_keep)
            done.extend(sub_done)
        i = j
    return keep, done


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Move finished tasks from .docs/task.md into a dated archive.")
    ap.add_argument("--path", default=".", help="project root (default: .)")
    ap.add_argument("--check", action="store_true", help="report only; exit 1 if finished tasks remain")
    args = ap.parse_args(argv)
    root = Path(args.path)
    task = root / ".docs" / "task.md"
    if not task.is_file():
        print(f"error: {task} not found", file=sys.stderr)
        return 2
    raw = task.read_bytes()
    text = raw.decode("utf-8")
    newline = "\r\n" if "\r\n" in text else "\n"
    keep, done = split(text.splitlines())
    items = sum(1 for ln in done if ITEM.match(ln))
    if args.check:
        print(f"tasks_done: {items} finished task(s) still in .docs/task.md" if items
              else "tasks_done: ok - none finished")
        return 1 if items else 0
    if not items:
        print("tasks_done: ok - none finished")
        return 0
    today = datetime.date.today()
    archive = root / ".docs" / "reference" / "archive" / today.strftime("%Y-%m") / "tasks-done.md"
    try:
        archive.parent.mkdir(parents=True, exist_ok=True)
        head = "" if archive.is_file() else f"# Finished tasks, {today:%Y-%m}{newline}"
        # Item lines are moved at their own indent less the shallowest, so sub-items read as items.
        cut = min(len(ln) - len(ln.lstrip()) for ln in done if ITEM.match(ln))
        body = newline.join(ln[cut:] if ln[:cut].isspace() else ln for ln in done)
        with archive.open("a", encoding="utf-8", newline="") as fh:
            fh.write(f"{head}{newline}## {today.isoformat()}{newline}{newline}{body}{newline}")
        task.write_bytes((newline.join(keep) + (newline if text.endswith(("\n", "\r")) else "")).encode("utf-8"))
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"moved {items} finished task(s) to {archive.relative_to(root).as_posix()}")
    print("tasks_done: ok - if a phase finished, write its one line in .docs/changelog.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
