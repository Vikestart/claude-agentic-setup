"""Byte-accurate line-ending check and repair.

WHY THIS EXISTS. On a `core.autocrlf=true` Windows checkout the working tree is
CRLF, and a scripted edit that writes LF leaves the file mixed. The usual shell
idioms for detecting that are BROKEN in this Git Bash:

  * `grep -c $'\\r$'` returns the LINE COUNT, not the CR count — a tautology that
    "passes" on a pure-LF file, so every check made that way was vacuous.
  * `sed 's/$/\\r/'` is a no-op here, so the usual normalise-then-verify pair
    silently does nothing.

`sed -i` is the common way to cause the damage: it rewrites the whole file LF-only.
Reading bytes and counting them is the only check that stays honest, so that is all
this script does.

    crlf.py <paths...>            report only (the default); exit 1 if any file is dirty
    crlf.py --check <paths...>    same thing, spelled explicitly
    crlf.py --fix   <paths...>    rewrite to uniform CRLF, report what changed
    crlf.py --changed [--fix]     every git-changed and untracked file (the usual use),
                                  resolved against the REPO ROOT so it works from anywhere
    crlf.py --fix --lf <paths...> normalise to LF instead; --lf alone only changes the
                                  convention being CHECKED, it never writes

Only files whose extension is declared textual are ever REWRITTEN. Anything else is
reported and left alone, because NUL-detection is a heuristic and a NUL-free binary
would otherwise have its 0x0D/0x0A data bytes rewritten as line endings.

A file is CLEAN when it is uniformly one convention. MIXED (CRLF != CR, or both
CRLF and bare LF present) is the corruption worth catching: AGENTS.md's rule is
that one stray `\\r\\r\\n` makes git treat the whole file as irregular, turning a
26-line change into a 1200-line diff.

"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys

TEXT_SUFFIXES = {
    ".php", ".js", ".mjs", ".cjs", ".css", ".html", ".htm", ".json", ".md", ".txt",
    ".xml", ".svg", ".yml", ".yaml", ".sh", ".ps1", ".py", ".sql", ".ini", ".conf",
    ".htaccess", ".env", ".example", ".gitignore", ".auditignore",
}


def ascii_path(value: str) -> str:
    """Paths are printed but not controlled by us; a cp1252 console raises on a non-ASCII
    one AFTER a fix has already been written -- the exact mid-operation failure this
    script's own design note claims to avoid. Escape rather than crash."""
    return value.encode("ascii", "backslashreplace").decode("ascii")


def counts(data: bytes) -> tuple[int, int, int]:
    """(CRLF pairs, total LF, total CR)."""
    return data.count(b"\r\n"), data.count(b"\n"), data.count(b"\r")


def classify(data: bytes) -> str:
    if b"\x00" in data:
        return "binary"
    crlf, lf, cr = counts(data)
    if lf == 0 and cr == 0:
        return "no-newlines"
    if crlf == lf and crlf == cr:
        return "crlf"
    if crlf == 0 and cr == 0:
        return "lf"
    return "mixed"


def repo_root(start: str) -> str | None:
    proc = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=start,
                          capture_output=True, text=True, encoding="utf-8", errors="replace")
    return proc.stdout.strip() or None if proc.returncode == 0 else None


def git_changed(start: str) -> list[str]:
    """ABSOLUTE paths of changed and untracked files.

    ⚠️ TWO BUGS LIVE HERE IF YOU SIMPLIFY THIS.
    1. Git prints paths relative to the REPO ROOT. Resolving them against the CURRENT
       directory means that running `--changed` from a subdirectory silently matches
       nothing: every path misses, the summary says "0 need work", and `--fix` reports
       success while leaving every corrupted file untouched. Worse, a same-named nested
       path would be "fixed" INSTEAD of the real one. Root-relative, always.
    2. `-z` plus `core.quotepath=false`: without them a non-ASCII path comes back as an
       escaped C string, misses `isfile`, and is dropped without being counted.
    """
    root = repo_root(start)
    if not root:
        return []
    out: list[str] = []
    for args in (["diff", "--name-only", "--diff-filter=d", "-z", "HEAD"],
                 ["ls-files", "--others", "--exclude-standard", "-z"]):
        proc = subprocess.run(["git", "-c", "core.quotepath=false"] + args, cwd=root,
                              capture_output=True, text=True,
                              encoding="utf-8", errors="surrogateescape")
        if proc.returncode == 0:
            out += [os.path.join(root, p.replace("/", os.sep))
                    for p in proc.stdout.split("\0") if p]
    return sorted(set(out))


def looks_textual(path: str) -> bool:
    name = os.path.basename(path)
    _, ext = os.path.splitext(name)
    return ext.lower() in TEXT_SUFFIXES or name.lower() in TEXT_SUFFIXES


def main() -> int:
    parser = argparse.ArgumentParser(description="Byte-accurate line-ending check and repair.")
    parser.add_argument("paths", nargs="*", help="files to inspect")
    parser.add_argument("--check", action="store_true",
                        help="report only (the default; accepted because the docs name it)")
    parser.add_argument("--changed", action="store_true",
                        help="use every git-changed and untracked file instead of PATHS")
    parser.add_argument("--fix", action="store_true", help="rewrite to uniform CRLF")
    parser.add_argument("--lf", action="store_true", help="with --fix, normalise to LF instead")
    parser.add_argument("-q", "--quiet", action="store_true", help="only report files needing work")
    args = parser.parse_args()

    paths = list(args.paths)
    if args.changed:
        paths += git_changed(os.getcwd())
    if not paths:
        parser.error("name some files, or pass --changed")

    target = "lf" if args.lf else "crlf"
    dirty = changed = skipped = missing = 0

    for rel in paths:
        if not os.path.isfile(rel):
            missing += 1
            print(f"  MISS   {ascii_path(rel)}  (not a file - not inspected)")
            continue
        with open(rel, "rb") as handle:
            data = handle.read()
        kind = classify(data)
        # ⚠️ NUL DETECTION IS NOT A BINARY TEST, IT IS A HEURISTIC. The earlier condition
        # routed any MIXED-looking file with an unknown extension into the fixer, so a
        # NUL-free binary blob got rewritten: its 0x0D/0x0A data bytes became \r\n and the
        # file grew. Extension is now the gate for WRITING -- an unknown extension is
        # reported, never rewritten -- so the only files this script can modify are ones
        # whose type is declared textual.
        if kind == "binary":
            skipped += 1
            continue
        if not looks_textual(rel):
            if kind not in (target, "no-newlines"):
                dirty += 1
                crlf, lf, cr = counts(data)
                print(f"  {kind.upper():5} {ascii_path(rel)}  (CRLF={crlf} LF={lf} CR={cr}; "
                      f"unknown extension - NOT rewritten, fix it explicitly if it is text)")
            else:
                skipped += 1
            continue
        ok = kind in (target, "no-newlines")
        if not ok:
            dirty += 1
        if args.fix and not ok:
            # ⚠️ ORDER MATTERS, and the naive pair gets `\r\r\n` WRONG.
            # `.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")` round-trips a stray
            # `\r\r\n` straight back to itself — verified — leaving the exact corruption
            # AGENTS.md warns about (one of these makes git treat the whole file as
            # irregular, turning a 26-line change into a 1200-line diff). Collapse any RUN
            # of CRs before a LF into one line break first, then any surviving lone CR.
            normal = re.sub(rb"\r+\n", b"\n", data)
            normal = normal.replace(b"\r", b"\n")
            if target == "crlf":
                normal = normal.replace(b"\n", b"\r\n")
            with open(rel, "wb") as handle:
                handle.write(normal)
            changed += 1
            crlf, lf, cr = counts(normal)
            print(f"  FIXED  {ascii_path(rel)}  ({kind} -> {target}; CRLF={crlf} LF={lf} CR={cr})")
        elif not ok:
            crlf, lf, cr = counts(data)
            print(f"  {kind.upper():5} {ascii_path(rel)}  (CRLF={crlf} LF={lf} CR={cr}; want {target})")
        elif not args.quiet:
            print(f"  ok     {ascii_path(rel)}")

    # Report what was actually WRITTEN when fixing, not what needed work: a file refused
    # for an unknown extension is counted dirty but was deliberately left alone, and
    # calling it "fixed" would be the tool reporting work it declined to do.
    tally_n, verb = (changed, "fixed") if args.fix else (dirty, "need work")
    if args.fix and dirty != changed:
        verb = f"fixed, {dirty - changed} refused (unknown type)"
    print(f"=== crlf: {len(paths)} path(s), {tally_n} {verb}, {skipped} skipped "
          f"(binary/unknown type), {missing} not found ===")
    if args.fix and changed:
        # ASCII only in PRINTED strings: this script is often run directly, without the
        # launcher's PYTHONUTF8=1, and a cp1252 console raises UnicodeEncodeError AFTER the
        # fix has already been written to disk. Docstrings and comments are never printed.
        print("Now check magnitude: `git diff --numstat`. A line-ending rewrite that touches "
              "more lines than you edited means the file was irregular - that is the tripwire.")
    return 1 if dirty and not args.fix else 0


if __name__ == "__main__":
    sys.exit(main())
