#!/usr/bin/env python3
"""Exact, all-or-nothing text replacements across files, from a spec that needs no escaping.

WHY THIS EXISTS. `automation_mine.py` found ~4,300 hand-written patch scripts in one month
(~2.4M output tokens, ~120 failed runs), each re-implementing the same thing: read a file, assert
an anchor occurs once, replace, write. They failed the same ways every time — backslashes halved
inside a heredoc, CRLF files matched against LF anchors, text mode silently rewriting line
endings, and a batch half-applied when the third anchor missed. This does it once, correctly.

USAGE
    patch.py SPEC [--root DIR] [--check]

Write SPEC with the Write tool, never a heredoc (a heredoc can halve backslashes). Nothing in it
is escaped: every character between the markers is taken literally.

    @@@ includes/lesson.php
    <<<<<<< OLD
    $x = foo('a\\b');
    ======= NEW
    $x = bar('a\\b');
    >>>>>>> END

    @@@ assets/app.css
    <<<<<<< OLD x2
    color:red
    ======= NEW
    >>>>>>> END

  * `@@@ PATH` starts a file (relative to --root, default the current directory); any number of
    OLD/NEW blocks follow, applied in order, each seeing the previous one's result.
  * `OLD` must occur exactly once; `OLD xN` exactly N times, all replaced. An empty NEW deletes.
  * A block is its lines joined by newlines, with no trailing newline added, so an anchor can
    end mid-line. Text outside blocks is ignored and may be used for notes.
  * Marker lines are exactly `<<<<<<< OLD`, `======= NEW`, `>>>>>>> END`; content may not
    contain a line that is exactly one of them.

GUARANTEES
  * All or nothing: every block is checked against the files in memory first; if any fails,
    no file is written and each failure is reported with where its first line does occur.
  * Line endings: blocks are matched in the file's own style (CRLF files get CRLF anchors and
    CRLF replacements); bytes outside the replaced spans are untouched, a BOM included.
  * `--check` validates and reports without writing.

Exit 0 applied (or would apply), 1 an anchor or file failed (nothing written), 2 a bad spec.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

OPEN, MID, END, FILE = "<<<<<<< OLD", "======= NEW", ">>>>>>> END", "@@@ "
BOM = "﻿"


class SpecError(Exception):
    pass


def parse(text: str) -> list[tuple[str, list[tuple[str, str, int, int]]]]:
    """[(path, [(old, new, count, spec_line), ...]), ...] in spec order."""
    files: list[tuple[str, list[tuple[str, str, int, int]]]] = []
    lines = text.lstrip(BOM).replace("\r\n", "\n").split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith(FILE):
            path = line[len(FILE):].strip()
            if not path:
                raise SpecError(f"line {i + 1}: '@@@' without a path")
            files.append((path, []))
        elif line == OPEN or line.startswith(OPEN + " x"):
            start = i + 1
            if not files:
                raise SpecError(f"line {start}: block before any '@@@ PATH'")
            tail = line[len(OPEN):].strip()
            try:
                count = int(tail[1:]) if tail else 1
            except ValueError:
                raise SpecError(f"line {start}: bad count {tail!r}; use 'OLD xN'") from None
            if count < 1:
                raise SpecError(f"line {start}: count must be at least 1")
            try:
                mid = lines.index(MID, i + 1)
                end = lines.index(END, mid + 1)
            except ValueError:
                raise SpecError(f"line {start}: block has no '{MID}' / '{END}'") from None
            stray = next((k for k in range(i + 1, mid) if lines[k] in (OPEN, END)), None)
            if stray is not None:
                raise SpecError(f"line {start}: marker inside the OLD text at line {stray + 1}")
            old, new = "\n".join(lines[i + 1:mid]), "\n".join(lines[mid + 1:end])
            if not old:
                raise SpecError(f"line {start}: empty OLD text")
            files[-1][1].append((old, new, count, start))
            i = end
        elif line in (MID, END):
            raise SpecError(f"line {i + 1}: '{line}' outside a block")
        i += 1
    if not any(blocks for _, blocks in files):
        raise SpecError("no blocks")
    return files


def where(text: str, old: str) -> str:
    """Where the anchor's first non-blank line occurs — the usual cause of a miss is visible there."""
    first = next((ln.strip() for ln in old.split("\n") if ln.strip()), "")
    hits = [n for n, ln in enumerate(text.split("\n"), 1) if first and first in ln]
    if not hits:
        return f"its first line {first[:60]!r} occurs nowhere"
    shown = ", ".join(map(str, hits[:8])) + (" …" if len(hits) > 8 else "")
    return f"its first line occurs at line(s) {shown} — the difference is further down"


def apply(files, root: Path) -> tuple[dict[Path, bytes], list[str], list[str]]:
    out: dict[Path, bytes] = {}
    done: list[str] = []
    errors: list[str] = []
    for rel, blocks in files:
        path = (root / rel).resolve()
        if path in out:
            errors.append(f"{rel}: listed twice; put all its blocks under one '@@@'")
            continue
        try:
            raw = path.read_bytes().decode("utf-8")
        except FileNotFoundError:
            errors.append(f"{rel}: no such file")
            continue
        except UnicodeDecodeError:
            errors.append(f"{rel}: not UTF-8")
            continue
        crlf = "\r\n" in raw
        text = raw
        for old, new, count, line in blocks:
            # The file's own style first; a mixed file may hold the anchor in the other one.
            styles = ["\r\n", "\n"] if crlf else ["\n"]
            found, style = 0, styles[0]
            for nl in styles:
                found, style = text.count(old.replace("\n", nl)), nl
                if found == count:
                    break
            if found != count:
                hint = (where(text.replace("\r\n", "\n"), old) if not found
                        else "make the anchor longer" if found > count else "fewer than expected")
                errors.append(f"{rel} (spec line {line}): expected {count}x, found {found}x; {hint}")
                continue
            text = text.replace(old.replace("\n", style), new.replace("\n", style))
            label = " (CRLF)" if style == "\r\n" else ""
            done.append(f"{rel}: {count} replacement{'s' if count > 1 else ''}{label} (spec line {line})")
        out[path] = text.encode("utf-8")
    return out, done, errors


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec", type=Path)
    ap.add_argument("--root", type=Path, default=Path.cwd())
    ap.add_argument("--check", action="store_true", help="validate and report, write nothing")
    args = ap.parse_args()
    try:
        files = parse(args.spec.read_bytes().decode("utf-8"))
    except (OSError, UnicodeDecodeError, SpecError) as exc:
        print(f"patch: bad spec: {exc}", file=sys.stderr)
        return 2
    out, done, errors = apply(files, args.root)
    for e in errors:
        print(f"FAIL  {e}")
    if errors:
        print(f"patch: {len(errors)} failure(s); nothing written")
        return 1
    for d in done:
        print(f"ok    {d}")
    if not args.check:
        for path, data in out.items():
            path.write_bytes(data)
    verb = "would patch" if args.check else "patched"
    print(f"patch: {verb} {len(done)} block(s) in {len(out)} file(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
