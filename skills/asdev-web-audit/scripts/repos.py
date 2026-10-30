"""One-call status across the projects' git repos (from the work setup, 2026-10-30).

    python repos.py [extra_repo ...] [--remote] [--quiet]

One table instead of four or five git commands per repo: branch, uncommitted and untracked
counts, ahead/behind the upstream as of the last fetch, and any local branch other than `main`
and `staging` carrying commits the default branch lacks (CLAUDE.md §2 allows no other branch, and
those commits are what make deleting it unsafe). `staging` ahead of the default branch is shown as
unreleased work but not counted: between releases that is normal.

The repos are every git repo directly under the projects root (`PROJECTS_ROOT`, found as
harness_parity.py finds it) plus the setup repo this script lives in. `--remote` adds, via gh:
archived / private / PUBLIC, open PR count, and each branch ruleset's enforcement and bypass mode,
because `bypass_actors` decides whether a ruleset binds: `always` lets an admin bypass everything,
`pull_request` blocks direct pushes but lets an admin merge with `gh pr merge --admin`.

Exit: 0 everything clean and synced · 1 something needs attention · 2 operational.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

from harness_parity import projects_root

GH = shutil.which("gh") or r"C:\Program Files\GitHub CLI\gh.exe"


def git(repo: Path, *args: str) -> tuple[int, str]:
    # bytes + explicit UTF-8: text=True decodes as cp1252 on Windows and crashes on real UTF-8
    proc = subprocess.run(["git", "-C", str(repo), *args], capture_output=True)
    return proc.returncode, proc.stdout.decode("utf-8", "replace").strip()


def default_branch(repo: Path) -> str:
    rc, out = git(repo, "symbolic-ref", "--short", "refs/remotes/origin/HEAD")
    if rc == 0 and "/" in out:
        return out.split("/", 1)[1]
    for cand in ("main", "master"):
        if git(repo, "rev-parse", "--verify", f"refs/heads/{cand}")[0] == 0:
            return cand
    return "?"


def owner_repo(repo: Path) -> tuple[str, str] | None:
    rc, url = git(repo, "remote", "get-url", "origin")
    m = re.search(r"github\.com[:/]+([^/]+)/([^/]+?)(?:\.git)?$", url) if rc == 0 else None
    return (m.group(1), m.group(2)) if m else None


def gh_json(*args: str):
    if not Path(GH).is_file():
        return None
    proc = subprocess.run([GH, *args], capture_output=True)
    if proc.returncode:
        return None
    try:
        return json.loads(proc.stdout.decode("utf-8", "replace"))
    except json.JSONDecodeError:
        return None


def remote_summary(repo: Path) -> str:
    orp = owner_repo(repo)
    if orp is None:
        return "no github remote"
    if not Path(GH).is_file():
        return "gh not installed"
    o, r = orp
    meta = gh_json("api", f"repos/{o}/{r}")
    if meta is None:
        return "gh api failed"
    parts = ["private" if meta.get("private") else "PUBLIC"]
    if meta.get("archived"):
        parts.append("archived")
    pulls = gh_json("api", f"repos/{o}/{r}/pulls?state=open")
    if isinstance(pulls, list):
        parts.append(f"open PRs: {len(pulls)}")
    rules = gh_json("api", f"repos/{o}/{r}/rulesets")
    if isinstance(rules, list):
        for rs in [x for x in rules if x.get("target") == "branch"][:3]:
            detail = gh_json("api", f"repos/{o}/{r}/rulesets/{rs['id']}") or {}
            actors = detail.get("bypass_actors") or []
            bp = ",".join(f"{x.get('actor_type', '?')}:{x.get('bypass_mode', '?')}" for x in actors) or "none"
            parts.append(f"ruleset '{rs.get('name')}': {rs.get('enforcement')} (bypass {bp})")
    return " · ".join(parts)


def discover() -> list[tuple[str, Path]]:
    found = []
    root = projects_root()
    if root is not None:
        found = [(p.name, p) for p in sorted(root.iterdir()) if (p / ".git").exists()]
    rc, setup = git(Path(__file__).resolve().parent, "rev-parse", "--show-toplevel")
    if rc == 0 and setup:
        found.append(("(setup) " + Path(setup).name, Path(setup)))
    return found


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Status across the projects' git repos in one table.")
    ap.add_argument("extra", nargs="*", help="additional repo paths")
    ap.add_argument("--remote", action="store_true", help="add gh: visibility, PRs, rulesets")
    ap.add_argument("--quiet", action="store_true", help="only the repos that need attention, and the total")
    a = ap.parse_args()

    targets = discover() + [(Path(p).name, Path(p).expanduser().resolve()) for p in a.extra]
    if not targets:
        print("error: no repos found (set PROJECTS_ROOT or pass paths)", file=sys.stderr)
        return 2
    width = max(len(label) for label, _ in targets) + 2
    attention = 0
    for label, repo in targets:
        if not repo.is_dir() or git(repo, "rev-parse", "--git-dir")[0]:
            print(f"  {label:<{width}} MISSING or not a git repo: {repo}")
            attention += 1
            continue
        flagged = False
        rc, branch = git(repo, "rev-parse", "--abbrev-ref", "HEAD")
        dflt = default_branch(repo)
        rc, porcelain = git(repo, "status", "--porcelain")
        lines = [ln for ln in porcelain.splitlines() if ln]
        untracked = sum(1 for ln in lines if ln.startswith("??"))
        dirty = len(lines) - untracked
        rc, ab = git(repo, "rev-list", "--left-right", "--count", "HEAD...@{u}")
        ahead_behind = "-"                      # ASCII: a cp1252 console cannot print every dash
        if rc == 0 and ab:
            ahead, behind = ab.split()
            ahead_behind = f"+{ahead}/-{behind}"
            flagged |= ahead != "0" or behind != "0"
        unmerged, unreleased = [], ""
        rc, heads = git(repo, "for-each-ref", "--format=%(refname:short)", "refs/heads")
        heads = [b for b in heads.splitlines() if b]
        # Another branch is only unsafe to delete for commits that are in neither main nor staging.
        kept = [dflt] + (["staging"] if "staging" in heads and dflt != "staging" else [])
        for b in heads:
            if b in kept:
                if b == "staging":
                    rc2, n = git(repo, "rev-list", "--count", f"{dflt}..staging")
                    unreleased = f"unreleased: staging({n})" if rc2 == 0 and n != "0" else ""
                continue
            rc2, n = git(repo, "rev-list", "--count", b, "--not", *kept)
            if rc2 == 0 and n != "0":
                unmerged.append(f"{b}({n})")
        if len(unmerged) > 3:
            unmerged = unmerged[:3] + [f"+{len(unmerged) - 3} more"]
        flagged |= bool(dirty or untracked or unmerged)
        attention += flagged
        if a.quiet and not flagged:
            continue
        state = f"dirty={dirty} untracked={untracked}" if (dirty or untracked) else "clean"
        notes = " ".join(x for x in ("unmerged: " + ", ".join(unmerged) if unmerged else "", unreleased) if x)
        print(f"  {label:<{width}} {branch:<20} {state:<26} {ahead_behind:<8} {notes}".rstrip())
        if a.remote:
            print(f"  {'':<{width}} remote: {remote_summary(repo)}")
    print(f"\n{len(targets)} repos, {'all clean and synced' if not attention else f'{attention} need attention'}"
          " (ahead/behind as of the last fetch)")
    return 1 if attention else 0


if __name__ == "__main__":
    sys.exit(main())
