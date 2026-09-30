#!/usr/bin/env python3
"""Scaffold the mechanical half of `.docs/handover.md`.

A handover is state, decisions, files, checks, deployment state and next steps. Four of those six
are facts the repository already knows, and writing them from memory costs output tokens — which
are priced well above input — while risking a confidently wrong branch name or check result. This
gathers those four and leaves DECISIONS and NEXT STEPS blank, because those are the half that
actually needs a person or a model who was there.

    python $HOME/.claude/skills/asdev-web-audit/scripts/handover.py --path C:/xampp/htdocs/my-project
    python $HOME/.claude/skills/asdev-web-audit/scripts/handover.py --path . --since main --run-checks
    python $HOME/.claude/skills/asdev-web-audit/scripts/handover.py --path . --stdout

Writes `.docs/handover.md` and REFUSES to overwrite an existing one without `--force`: a previous
tool in this suite destroyed hand-adjudicated content by regenerating over it, and a handover is
exactly the file someone has just finished editing by hand.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
TODO = "<!-- TODO: only you can write this — the script deliberately leaves it blank. -->"


def git(root: Path, *args: str) -> str:
    """Run a read-only git command; empty string when git or the repo is unavailable."""
    try:
        # encoding is explicit: text=True alone decodes with the locale codec, which turned every
        # em-dash in a commit subject into mojibake on this box.
        proc = subprocess.run(["git", "-C", str(root), *args], capture_output=True,
                              text=True, encoding="utf-8", errors="replace", timeout=30)
    except (OSError, subprocess.SubprocessError):
        return ""
    return proc.stdout.strip() if proc.returncode == 0 else ""


def fence(body: str, lang: str = "") -> str:
    return f"```{lang}\n{body.strip()}\n```" if body.strip() else "_(none)_"


def docs_state(root: Path) -> str:
    """What the working documents currently claim, so the handover cannot contradict them."""
    docs = root / ".docs"
    if not docs.is_dir():
        return "_No `.docs/` directory._"
    out: list[str] = []
    for name in ("implementation_plan.md", "task.md", "roadmap.md"):
        path = docs / name
        if not path.is_file():
            out.append(f"- `{name}` — missing")
            continue
        try:
            # errors="replace": a cp1252 en-dash in a working doc raised UnicodeDecodeError, which
            # is a ValueError and so escaped an `except OSError` entirely.
            lines = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
        except (OSError, ValueError):
            out.append(f"- `{name}` — unreadable")
            continue
        heading = next((l.strip() for l in lines if l.startswith("#")), "(no heading)")
        open_items = sum(1 for l in lines if l.strip().startswith(("- [ ]", "* [ ]")))
        done_items = sum(1 for l in lines if l.strip().lower().startswith(("- [x]", "* [x]")))
        extra = f", {open_items} open / {done_items} done" if (open_items or done_items) else ""
        out.append(f"- `{name}` — {len(lines)} lines{extra} — {heading[:80]}")
    changelog = docs / "changelog.md"
    if changelog.is_file():
        tail = [l for l in changelog.read_text(encoding="utf-8-sig",
                                               errors="replace").splitlines() if l.strip()][-3:]
        out.append("- `changelog.md` last entries:")
        out += [f"    {l.strip()[:110]}" for l in tail]
    return "\n".join(out)


def reference_sweep(root: Path, since: str | None) -> str:
    """Show the `.docs/reference/` shelf and which of it this stretch of work touched.

    A handover spans several phases and a fresh chat keeps only what was written down, so the sweep
    is the last chance to move durable knowledge out of the transcript. This prints the shelf and the
    prompt, never a verdict: no script can know which lesson deserves to be permanent.
    """
    ref = root / ".docs" / "reference"
    out: list[str] = []
    if not ref.is_dir():
        out.append("⚠️ **No `.docs/reference/` directory.** Durable material has nowhere to go, so it "
                   "is living in the handover — and the handover is replaced, not archived.")
    else:
        # No git means no diff, and every doc would then read "not touched" — which is a missing
        # comparison, not a finding. Say which it is.
        is_repo = bool(git(root, "rev-parse", "--git-dir"))
        rng = f"{since}...HEAD" if since else "HEAD~8...HEAD"
        touched = {l.strip().replace("\\", "/")
                   for l in git(root, "diff", "--name-only", rng).splitlines() if l.strip()}
        every = [p for p in ref.rglob("*.md") if p.is_file()]
        # archive/ is dated evidence — stamped, never rewritten — so it is not part of the sweep and
        # listing it buries the handful of docs that actually moved.
        archived = [p for p in every if "archive" in p.relative_to(ref).parts]
        files = [p for p in every if p not in archived]
        if not files:
            out.append("_`.docs/reference/` holds no current `.md` files._")
        rows = []
        for path in files:
            rel = path.relative_to(root).as_posix()
            try:
                n = len(path.read_text(encoding="utf-8-sig", errors="replace").splitlines())
            except (OSError, ValueError):
                rows.append((True, rel, f"- `{rel}` — unreadable"))
                continue
            hit = rel in touched
            if not is_repo:
                mark = "_no git here, so this work's changes cannot be compared_"
            else:
                mark = "updated by this work" if hit else "**not touched**"
            rows.append((not hit, rel, f"- `{rel}` — {n} lines — {mark}"))
        out += [r[2] for r in sorted(rows)]          # updated docs first: those are the sweep's start
        if archived:
            out.append(f"- _plus {len(archived)} file(s) under `archive/` — dated evidence, stamped "
                       "and never rewritten; outside the sweep._")
    out += [
        "",
        "**The list above is not the sweep.** Before writing Decisions and Next steps, decide what "
        "from this stretch of work is durable — architecture, decisions, invariants, caveats, traps "
        "that cost real time — and move it into `.docs/reference/`. Sort by what a new session would "
        "otherwise rediscover the hard way. The handover then LINKS it. Anything left only in the "
        "handover is lost at the next rotation.",
    ]
    return "\n".join(out)


def run_checks(root: Path) -> str:
    """The aggregate gate, counts only. Opt-in: it is the slowest thing here."""
    audit = SCRIPTS / "audit_all.py"
    if not audit.is_file():
        return "_`audit_all.py` not found._"
    try:
        proc = subprocess.run([sys.executable, str(audit), "--path", str(root), "--changed", "-q"],
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=900)
    except (OSError, subprocess.SubprocessError) as exc:
        return f"_Could not run the gate: {exc}_"
    body = (proc.stdout or proc.stderr).strip()
    return f"{fence(body)}\n\nExit code **{proc.returncode}** (1 = blocking findings)."


def build(root: Path, since: str | None, checks: bool) -> str:
    branch = git(root, "rev-parse", "--abbrev-ref", "HEAD") or "(not a git repo)"
    ref = since or f"origin/{branch}"
    tracking = git(root, "rev-list", "--left-right", "--count", f"{ref}...HEAD")
    if tracking and len(tracking.split()) == 2:
        behind, ahead = tracking.split()
        sync = f"{ahead} ahead / {behind} behind `{ref}`"
    else:
        sync = f"could not compare against `{ref}`"
    dirty = git(root, "status", "--short")
    # A bad --since otherwise renders "Files changed since `no-such-ref`" over "_(none)_", which
    # reads as "nothing changed" rather than "the command failed".
    bad_ref = bool(since) and not git(root, "rev-parse", "--verify", "--quiet", f"{since}^{{commit}}")
    diffstat = ("" if bad_ref else
                (git(root, "diff", "--stat", ref) if since else git(root, "diff", "--stat")))

    parts = [
        f"# Handover — {root.name}",
        "",
        "> Mechanical sections generated by `asdev-web-audit/scripts/handover.py`; the two marked TODO are not.",
        "",
        "## State",
        "",
        f"- Branch **`{branch}`** — {sync}",
        f"- Uncommitted: **{len(dirty.splitlines())} file(s)**",
        "",
        fence(dirty),
        "",
        "## Recent commits",
        "",
        fence(git(root, "log", "-8", "--pretty=format:%h %ad %s", "--date=short")),
        "",
        f"## Files changed{f' since `{since}`' if since else ' (working tree)'}",
        "",
        (f"⚠️ **`{since}` is not a valid ref in this repository** — this section is not 'no changes', "
         "it is 'the comparison never ran'." if bad_ref else fence(diffstat)),
        "",
        "## Working documents",
        "",
        docs_state(root),
        "",
        "## Reference sweep",
        "",
        reference_sweep(root, since),
        "",
        "## Checks",
        "",
        run_checks(root) if checks else "_Not run. Re-run with `--run-checks`, or paste the last result._",
        "",
        "## Deployment state",
        "",
        f"- Local: branch `{branch}`, {len(dirty.splitlines())} uncommitted file(s)",
        "- Staging: " + TODO,
        "- Production: " + TODO,
        "",
        "## Decisions taken",
        "",
        TODO,
        "",
        "## Next steps",
        "",
        TODO,
        "",
    ]
    return "\n".join(parts)


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--path", default=".", help="project root (default: cwd)")
    ap.add_argument("--since", default=None, help="git ref to diff against, e.g. main")
    ap.add_argument("--out", default=None, help="output path (default: <path>/.docs/handover.md)")
    ap.add_argument("--stdout", action="store_true", help="print instead of writing")
    ap.add_argument("--run-checks", action="store_true", help="run the aggregate gate and embed counts")
    ap.add_argument("--force", action="store_true", help="overwrite an existing handover")
    args = ap.parse_args()

    root = Path(args.path).resolve()
    if not root.is_dir():
        print(f"FAIL: no such directory: {root}")
        return 1
    text = build(root, args.since, args.run_checks)

    if args.stdout:
        print(text)
        return 0
    out = Path(args.out).resolve() if args.out else root / ".docs" / "handover.md"
    if out.exists() and not args.force:
        print(f"FAIL: {out} already exists. Read it first, then re-run with --force to replace it.")
        print("      (--stdout prints the generated version without touching the file.)")
        return 1
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8", newline="\n")
    todos = text.count(TODO)
    print(f"wrote {out} ({len(text.splitlines())} lines, {todos} section(s) left for you)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
