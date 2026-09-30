"""Answer "what did I introduce?" instead of "what exists?".

WHY THIS EXISTS. `audit_all.py --changed` reports every finding in every file you
touched, including ones that predate you. On 2026-08-21 it reported 93 blocking
findings for a change that introduced none: all 93 were old-style declarations in
a stylesheet the work happened to touch. Establishing that by hand took six steps
and still ended in `git commit --no-verify`, which is the outcome the pre-commit
hook exists to prevent. Once bypassing is reflexive, a real finding rides along.

WHAT IT DOES. Audits the working tree, audits the same project at `--since` (HEAD
by default), and reports the difference for the files you changed:

    NEW        introduced by your work    -> exit 1 if any are blocking
    FIXED      present at the ref, gone now
    UNCHANGED  pre-existing, not yours    -> never fails the gate

TWO DESIGN DECISIONS, both learned by getting them wrong first:

1. THE REF SIDE IS A REAL `git worktree`, NOT A DIRECTORY OF COPIED FILES.
   `unused_css_detector` and `link_checker` cross-reference the WHOLE project. Give
   them a temp dir holding only the changed CSS file and every class reads as
   unused: an isolated dir scored 95 blocking / 116 advisory where the project
   scores a fraction of that. A worktree gives every scanner real context.

2. FINDINGS ARE COMPARED AS A MULTISET, NOT A SET, AND NOT BY LINE NUMBER.
   Line numbers shift when you add a line above, so a line-keyed diff reports one
   defect as both FIXED and NEW. But keying on (tool, rule, file, message) ALONE
   collapses every occurrence into one — the 76 identical `CSS_SPACE_COLON`
   findings in one file share a message verbatim, so a 77th would register as
   nothing at all. Counting occurrences per key catches both cases.

LIMITS, STATED RATHER THAN HIDDEN. A file with no version at the ref (newly added)
has every finding counted NEW, which is correct. Renames are seen as add+delete,
so a moved file's pre-existing findings read as NEW — compare `--since` a
merge-base for a release sweep if that matters. The ref-side scan is a full-project
audit (~19s on a 594-file project) and is SKIPPED ENTIRELY when the working tree
has no findings in the changed files, which is the common case.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import shutil
import subprocess
import sys
import tempfile

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
AUDIT_ALL = os.path.join(SCRIPTS, "audit_all.py")

# This script prints PATHS and SCANNER MESSAGES, neither of which it controls, so a
# non-ASCII byte can reach a legacy cp1252 console and raise UnicodeEncodeError mid-report.
# Setting PYTHONIOENCODING for the CHILD is not enough -- the crash happens in OUR print.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):  # pragma: no cover - non-reconfigurable stream
        pass


def _git(args: list[str], root: str, binary: bool = False):
    return subprocess.run(["git"] + args, cwd=root, capture_output=True,
                          text=not binary,
                          encoding=None if binary else "utf-8",
                          errors=None if binary else "replace")


def _repo_root(start: str) -> str | None:
    proc = _git(["rev-parse", "--show-toplevel"], start)
    return proc.stdout.strip() or None if proc.returncode == 0 else None


def changed_files(root: str, ref: str) -> set[str]:
    """⚠️ -z IS LOAD-BEARING, NOT TIDINESS.

    With `core.quotepath` at its default, plain `git diff --name-only` renders a
    non-ASCII path as an escaped, double-quoted C string: `nørsk.css` comes back as
    `"n\\303\\270rsk.css"`. That mangled name then matches nothing in the findings,
    the file drops out of scope, and the delta reports a CLEAN GATE while real new
    blocking findings sit in it -- a false green, which is the worst failure a gate
    has. `-z` emits raw NUL-separated paths and never quotes.
    """
    proc = _git(["diff", "--name-only", "--diff-filter=d", "-z", ref], root)
    if proc.returncode != 0:
        raise SystemExit(f"audit_delta: `git diff` against {ref!r} failed — is that ref valid?")
    tracked = {p.replace("\\", "/") for p in proc.stdout.split("\0") if p}
    proc = _git(["ls-files", "--others", "--exclude-standard", "-z"], root)
    untracked = {p.replace("\\", "/") for p in proc.stdout.split("\0") if p}
    return tracked | untracked


def audit(path: str, scope: list[str] | None = None) -> dict:
    cmd = [sys.executable, AUDIT_ALL, "--path", path, "--json", "--max", "0"]
    if scope:
        cmd += scope
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    proc = subprocess.run(cmd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", env=env)
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        raise SystemExit("audit_delta: audit_all.py did not return JSON.\n"
                         f"stdout: {proc.stdout[:400]}\nstderr: {proc.stderr[:400]}")


def _norm_path(value: str) -> str:
    value = str(value or "").replace("\\", "/")
    while value.startswith("./"):
        value = value[2:]
    return value.lstrip("/")


def tally(report: dict, only: set[str]) -> tuple[collections.Counter, dict]:
    """(count per (tool, rule, file, message), one representative finding per key)."""
    counts: collections.Counter = collections.Counter()
    sample: dict = {}
    for tool in report.get("tools", []):
        name = tool.get("tool", "")
        blocking = bool(tool.get("blocking", False))
        for finding in tool.get("findings", []):
            rel = _norm_path(finding.get("file", ""))
            if rel not in only:
                continue
            key = (name, finding.get("rule", ""), rel,
                   " ".join(str(finding.get("message", "")).split()))
            counts[key] += 1
            sample.setdefault(key, {**finding, "tool": name, "blocking": blocking})
    return counts, sample


def blind_spots(report: dict, only: set[str]) -> list[str]:
    """Files an auditor could not read, and auditors that failed outright.

    ⚠️ FAIL CLOSED HERE. `tally()` reads only `tools[].findings`, so a file the
    scanners could not open (permissions, encoding) and a scanner that threw both
    contribute ZERO findings -- and a delta computed from zero looks CLEAN. audit_all
    counts both in its own exit code; ignoring them turns a broken scan into a green
    gate, and worse, an auditor crashing on the working-tree side would make the delta
    *greener* rather than redder.
    """
    problems: list[str] = []
    for message in report.get("errors", []) or []:
        problems.append(f"scanner error: {message}")
    for tool in report.get("tools", []):
        for entry in tool.get("unreadable", []) or []:
            # ⚠️ audit_all emits these as {"file": ..., "reason": ...}, NOT as plain
            # strings. Treating the dict as a path stringifies it, matches nothing in
            # scope, and silently restores the fail-open this function exists to close.
            # Both shapes are accepted so a future format change cannot re-open it.
            if isinstance(entry, dict):
                rel, reason = entry.get("file", ""), entry.get("reason", "")
            else:
                rel, reason = entry, ""
            rel = _norm_path(rel)
            if rel and rel in only:
                detail = f" ({reason.split(':')[0]})" if reason else ""
                problems.append(f"{tool.get('tool', '?')} could not read {rel}{detail}")
    return problems


def _show(label: str, counts: collections.Counter, sample: dict, limit: int, with_line: bool) -> None:
    if not counts:
        return
    total = sum(counts.values())
    print(f"\n--- {label}: {total} ---")
    for key, count in counts.most_common(limit):
        tool, rule, rel, message = key
        finding = sample.get(key, {})
        mark = "!" if finding.get("blocking") else " "
        line = finding.get("line")
        where = f"{rel}:{line}" if with_line and line else rel
        times = f" (x{count})" if count > 1 else ""
        print(f" {mark} [{tool}/{rule}] {where}{times}  {message[:92]}")
    if len(counts) > limit:
        print(f"   ... +{len(counts) - limit} more kind(s)")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Report only the audit findings your work introduced.")
    parser.add_argument("--since", default="HEAD", metavar="REF",
                        help="compare against this ref instead of HEAD (e.g. main)")
    parser.add_argument("--path", default=".", help="project root (default: cwd)")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("-q", "--quiet", action="store_true", help="counts only")
    parser.add_argument("--max", type=int, default=25, metavar="N",
                        help="finding kinds shown per section (default 25)")
    args = parser.parse_args()

    root = _repo_root(os.path.abspath(args.path))
    if not root:
        raise SystemExit("audit_delta: not inside a git repository.")

    scope = changed_files(root, args.since)
    if not scope:
        print(f"=== audit delta vs {args.since}: no changed files ===")
        return 0

    now_report = audit(root, ["--changed"] if args.since == "HEAD"
                       else ["--since", args.since])
    now_counts, now_sample = tally(now_report, scope)

    # Fail closed BEFORE the clean-exit shortcut: an unreadable file or a crashed
    # scanner yields no findings, and "no findings" must never be read as "clean".
    blind = blind_spots(now_report, scope)
    if blind:
        print(f"=== audit delta vs {args.since}: CANNOT ATTRIBUTE - the scan is incomplete ===")
        for problem in blind[:20]:
            print(f"  ! {problem}")
        print("\nThese files or scanners produced no findings because they FAILED, not because "
              "they are clean.\nFix the access or encoding problem and re-run; refusing is the "
              "only honest verdict here.")
        return 1

    # The expensive half is skipped when there is nothing to attribute.
    if not now_counts:
        print(f"=== audit delta vs {args.since}: clean - no findings at all in "
              f"{len(scope)} changed file(s) ===")
        return 0

    tmp = tempfile.mkdtemp(prefix="audit-delta-")
    worktree = os.path.join(tmp, "ref")
    try:
        proc = _git(["worktree", "add", "--detach", "--quiet", worktree, args.since], root)
        if proc.returncode != 0:
            raise SystemExit("audit_delta: could not create a worktree at "
                             f"{args.since!r}:\n{proc.stderr[:400]}")
        before_counts, before_sample = tally(audit(worktree), scope)
    finally:
        _git(["worktree", "remove", "--force", worktree], root)
        _git(["worktree", "prune"], root)
        shutil.rmtree(tmp, ignore_errors=True)

    new = now_counts - before_counts
    fixed = before_counts - now_counts
    unchanged = now_counts & before_counts
    new_blocking = sum(c for k, c in new.items() if now_sample[k].get("blocking"))

    if args.json:
        print(json.dumps({
            "ref": args.since,
            "changed_files": len(scope),
            "new_blocking": new_blocking,
            "new_advisory": sum(new.values()) - new_blocking,
            "fixed": sum(fixed.values()),
            "unchanged_preexisting": sum(unchanged.values()),
            "new": [{"tool": k[0], "rule": k[1], "file": k[2], "message": k[3], "count": c}
                    for k, c in new.most_common()],
        }, indent=2))
        return 1 if new_blocking else 0

    print(f"=== audit delta vs {args.since}: {new_blocking} new blocking, "
          f"{sum(new.values()) - new_blocking} new advisory, "
          f"{sum(unchanged.values())} pre-existing, {sum(fixed.values())} fixed "
          f"({len(scope)} changed file(s)) ===")

    if not args.quiet:
        _show("NEW (introduced by this change)", new, now_sample, args.max, True)
        _show(f"FIXED (gone since {args.since})", fixed, before_sample, min(args.max, 10), False)
        if unchanged:
            by_file: collections.Counter = collections.Counter()
            for (_, _, rel, _), count in unchanged.items():
                by_file[rel] += count
            print("\n--- PRE-EXISTING (not yours; the gate does not fail on these) ---")
            for rel, count in by_file.most_common(6):
                print(f"   {count:4d}  {rel}")

    if new_blocking:
        print("\nBlocking findings introduced by this change. Fix at the root cause.")
        return 1
    print("\nNo blocking findings introduced by this change.")
    if unchanged:
        print("Pre-existing findings remain — record them as residual risk, never as passing.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
