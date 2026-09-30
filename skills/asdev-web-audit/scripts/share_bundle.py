#!/usr/bin/env python3
"""Package the shareable half of this setup for someone else's machine.

There is ONE instance of everything here — no staging fork to maintain. What makes that safe is a
convention: anything under a skill's `local/` directory is the author's own inventory (per-project
cheat sheets, project-specific scanner rules) and is never bundled. Every skill works without its
overlay; that is asserted by each skill's own self-test.

    python $HOME/.claude/skills/asdev-web-audit/scripts/share_bundle.py                      # default set
    python $HOME/.claude/skills/asdev-web-audit/scripts/share_bundle.py --skills asdev-web-audit   # a subset
    python $HOME/.claude/skills/asdev-web-audit/scripts/share_bundle.py --out D:/share.zip

Writes a zip and prints what went in and what was withheld. Every entry is verified byte-identical
against its source before the archive is announced — and the archive is built with Python's zipfile,
never PowerShell's Compress-Archive, which silently drops every dot-path.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path

from sync_agents_md import PERSONAL, PERSONAL_EXAMPLE, expand_imports, render

CLAUDE_HOME = Path.home() / ".claude"
SKILLS = CLAUDE_HOME / "skills"
DEFAULT_SKILLS = ["asdev-conventions", "asdev-web-audit", "asdev-blueprints", "asdev-handover", "asdev-planner", "asdev-orchestrator", "asdev-release"]

# Never bundled, wherever they appear.
EXCLUDED_DIRS = {"local", "__pycache__", ".sandbox", ".git", "evals", "node_modules"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}

# Subagent definitions ride with the config: CLAUDE.md §6 routes every spawn through them. Only the
# in-house ones: a person's own agents live untracked in the same linked folder and stay private.
AGENT_DEFS = CLAUDE_HOME / "agents"
AGENT_PATTERNS = ("opus-*.md", "fable-*.md")
# The README quotes the depth the setup itself applies, so the two cannot drift apart.
SHARED_SETTINGS = Path(__file__).resolve().parents[3] / "settings" / "shared-settings.json"


def spawn_depth() -> str:
    return json.loads(SHARED_SETTINGS.read_text(encoding="utf-8"))["set"]["env.CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH"]

README = """# Shared agent setup

Seven skills, the global instruction files and a subagent roster from one developer's Claude Code /
Codex setup.

## Install

Copy each skill folder into your agent's skills directory:

* Claude Code: `~/.claude/skills/<name>/`
* Codex: `~/.codex/skills/<name>/`

Both read the same `SKILL.md` + YAML-frontmatter format, so the same folder works in either.

Copy the files in `agents/` into `~/.claude/agents/` (Claude Code only), then start a new session: one
that is already running cannot see agent definitions added after it started.

Then look at `config/CLAUDE.md`. It is one person's working agreement with their agent — proportionality,
planning gates, git and deploy topology, verification discipline, multi-agent orchestration. **Section 2's
machine and hosting bullets (local dev, browser, production) are example placeholders**; replace those
with yours. `config/AGENTS.md` is
the Codex copy: it is GENERATED from `CLAUDE.md` and differs only in model names, which is how the two are
kept from drifting apart (`asdev-web-audit/scripts/sync_agents_md.py`, `--check` reports drift).

When it reads right for you, install it: copy `config/CLAUDE.md` to `~/.claude/CLAUDE.md`, where Claude
Code loads it into every session. If you already have one there, merge the two rather than overwriting
yours. For Codex, regenerate `~/.codex/AGENTS.md` from your edited copy with
`python ~/.claude/skills/asdev-web-audit/scripts/sync_agents_md.py` instead of copying `config/AGENTS.md`, so
your edits carry over. Start a new session afterwards: a running one keeps the instructions it started
with.

`config/CLAUDE.md` §6 allows at most 10 subagents per piece of work without approval. To have Claude Code
enforce the parts it can, add these to `~/.claude/settings.json` (a new session picks them up):

```json
"env": {
  "CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS": "10",
  "CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH": "@@SPAWN_DEPTH@@"
},
"workflowSizeGuideline": "medium"
```

The first refuses an eleventh subagent running at once, the second stops subagents spawning their own,
and the third tells Claude to keep workflows under 10 agents and warns you when one goes past that.

## What is here

* **`asdev-conventions`** — house style for dependency-free vanilla PHP/JS/CSS: endpoint skeletons,
  router and fetch patterns, CSS formatting and token architecture, security invariants.
* **`asdev-web-audit`** — 17 Python scanners (security, house-style lint, accessibility, broken assets, unused
  CSS, line endings, image optimisation) plus an aggregate gate, a delta gate that reports only what YOUR
  change introduced, and a falsification harness for new test guards. Run `scripts/self_test.py` first.
* **`asdev-blueprints`** — the capability inventory a web project needs before it has real users:
  environments and a locked-down staging, migrations and backups, auth and MFA, an admin panel with RBAC,
  GDPR export and deletion, legal pages, notifications, a support portal, a machine/LLM API, billing.
  67 capabilities in four tiers, each with a contract (what to build), invariants (why, and what went
  wrong for the people who learned it) and a definition of done. Three modes: scaffold a new project,
  audit an existing one against the standard, or build one capability. It ships templates for the
  Tier-0 files — env example, deny rules, CI workflow, docs skeleton, the manifest that records where
  a project stands.

* **`agents/`** — Claude Code subagent definitions, each fixing a model AND an effort level, because
  the Agent tool itself can set a model but not an effort: Opus executors from low to max effort, a
  Fable executor, and read-only reviewers. `config/CLAUDE.md` §6 says which to use when. The `fable-*`
  ones need access to Fable models; without it, use their Opus equivalents.

## What is not here

The author's `settings.json` (permissions, hooks) and memory files are not included.

Each skill may have a `local/` directory on the author's machine holding their per-project cheat sheet
and project-specific scanner rules. Those are deliberately excluded: they name projects you do not have.
Everything ships working without them — the scanners simply run their generic rules, and the conventions
stand on their own.

## Requirements

Python 3.10+. `php` and `node` on PATH for the syntax checks (or set `AUDIT_PHP` / `AUDIT_NODE`).
`audit_delta.py` needs a git repository. No other dependencies — that is rather the point.
"""


CONFIG_NOTE = """<!-- NOTE FOR THIS COPY: {names} referenced below {verb} NOT included in this bundle.
{reason}
Those references are the author's own setup; ignore or delete the sentences naming them. Everything
else in this file stands on its own.
-->

"""


def dangling_skills(text: str, bundled: list) -> list:
    """Skills this config tells the reader to use that the bundle does not ship.

    A shared instruction file that points at a skill the recipient does not have is a small but real
    papercut: they cannot tell whether they are missing an install step or reading someone else's
    note. Detected here rather than by editing the source, so there stays exactly one instance.
    """
    installed = sorted(p.name for p in SKILLS.iterdir() if p.is_dir()) if SKILLS.is_dir() else []
    return [name for name in installed if name not in bundled and f"`{name}`" in text]


def collect(root: Path, prefix: str) -> list[tuple[Path, str]]:
    out: list[tuple[Path, str]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if any(part in EXCLUDED_DIRS for part in rel.parts):
            continue
        if path.suffix in EXCLUDED_SUFFIXES:
            continue
        out.append((path, f"{prefix}/{rel.as_posix()}"))
    return out


def withheld(root: Path) -> list[str]:
    names = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and any(part in EXCLUDED_DIRS for part in path.relative_to(root).parts):
            names.append(path.relative_to(root).as_posix())
    return names


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--skills", nargs="+", default=DEFAULT_SKILLS)
    ap.add_argument("--out", default=str(Path.home() / "Downloads" / "agent-setup-share.zip"))
    ap.add_argument("--no-config", action="store_true", help="skip CLAUDE.md / AGENTS.md and the agent definitions")
    args = ap.parse_args()

    entries: list[tuple[Path, str]] = []
    held: list[str] = []
    for name in args.skills:
        root = SKILLS / name
        if not root.is_dir():
            print(f"FAIL: no such skill: {root}")
            return 1
        entries += collect(root, name)
        held += [f"{name}/{p}" for p in withheld(root)]
    agent_defs = [] if args.no_config else [
        (p, f"agents/{p.name}") for p in sorted({q for pat in AGENT_PATTERNS for q in AGENT_DEFS.glob(pat)})]
    entries += agent_defs

    # Config files are copied with a note prepended when they reference an unbundled skill, so they
    # are held separately from the byte-identical set.
    configs: list[tuple[str, str]] = []
    dangling: list = []
    if not args.no_config:
        # Built from CLAUDE.md and its imports with the example standing in for the personal file,
        # so the author's machine and hosting never ship; AGENTS.md is rendered from that same text
        # rather than copied, because the author's own AGENTS.md inlines their personal file.
        shared = expand_imports(CLAUDE_HOME / "CLAUDE.md", substitute={PERSONAL: PERSONAL_EXAMPLE})
        for text, arc in ((shared, "config/CLAUDE.md"), (render(shared), "config/AGENTS.md")):
            missing = dangling_skills(text, args.skills)
            if missing:
                dangling = sorted(set(dangling) | set(missing))
                names = ", ".join(f"`{m}`" for m in missing)
                text = CONFIG_NOTE.format(
                    names=names,
                    verb="is" if len(missing) == 1 else "are",
                    reason="It is specific to the author's own projects and is not part of this share.",
                ) + text
            configs.append((text, arc))

    out = Path(args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for src, arc in entries:
            z.write(src, arc)
        for text, arc in configs:
            z.writestr(arc, text)
        z.writestr("README.md", README.replace("@@SPAWN_DEPTH@@", spawn_depth()))

    # Prove the copy before announcing it.
    bad = []
    with zipfile.ZipFile(out) as z:
        names = set(z.namelist())
        for src, arc in entries:
            if arc not in names:
                bad.append(f"missing from archive: {arc}")
            elif hashlib.sha256(z.read(arc)).hexdigest() != hashlib.sha256(src.read_bytes()).hexdigest():
                bad.append(f"content mismatch: {arc}")
        for text, arc in configs:
            if arc not in names:
                bad.append(f"missing from archive: {arc}")
            elif z.read(arc).decode("utf-8") != text:
                bad.append(f"content mismatch: {arc}")
    if bad:
        for b in bad:
            print(f"FAIL: {b}")
        return 1

    print(f"wrote {out} ({out.stat().st_size / 1024:.0f} KB)")
    print(f"  {len(entries) + len(configs)} files bundled + README.md")
    for name in args.skills:
        print(f"    {name}: {sum(1 for _, a in entries if a.startswith(name + '/'))} files")
    if agent_defs:
        print(f"    agents: {len(agent_defs)} files")
    if configs:
        print(f"    config: {len(configs)} files")
    print(f"  {len(held)} file(s) withheld as local/private:")
    for h in held:
        print(f"    - {h}")
    if dangling:
        print(f"  {len(dangling)} skill(s) referenced by the config but NOT bundled: {', '.join(dangling)}")
        print("    -> a note naming them was prepended to the bundled config copies")
    print("  verified: skill files byte-identical to source (sha256); config copies match their annotated text")
    return 0


if __name__ == "__main__":
    sys.exit(main())
