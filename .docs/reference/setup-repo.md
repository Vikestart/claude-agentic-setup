# The shared setup repo

Since 2026-09-30 the global setup lives in the private repo `Vikestart/claude-agentic-setup`, cloned at
`~/.claude/claude-agentic-setup` and co-maintained by the owner and their partner (Windows). How to set
up a machine and the daily routine are in the repo's `README.md`; this file records how it works and
why. Traps it produced are in [`traps.md`](traps.md) (Windows and shell).

## What is shared, and how a session reaches it

| Repo | Seen by sessions as | How |
|---|---|---|
| `CLAUDE.shared.md` | `~/.claude/CLAUDE.md` | a one-line stub, `@claude-agentic-setup/CLAUDE.shared.md` |
| — | `~/.claude/CLAUDE.personal.md` | private; imported by the shared file's §2 (`@~/.claude/CLAUDE.personal.md`) |
| `agents/`, `hooks/`, `.docs/` | the same names in `~/.claude` | one junction each |
| `skills/asdev-*` | `~/.claude/skills/<name>` | one junction per skill; third-party skills stay real folders |
| `settings/shared-settings.json` | entries in `~/.claude/settings.json` | merged by the installer |
| `githooks/` | — | `core.hooksPath`, set by the installer |

- **Why the shared file is not named `CLAUDE.md`:** a session opened inside the repo would load it
  twice — once as that folder's project file, once through the stub.
- **Why links, not copies:** every edit a session makes through `~/.claude/...` is already a change in
  the repo, and nothing can drift between two copies. **Why junctions:** unlike file symlinks they need
  neither admin rights nor Developer Mode. **Why the repo is a subfolder**, not `~/.claude` itself: the
  login tokens, memory and transcripts are then outside any git working tree, so no ignore rule has to
  hold for them to stay private.
- **Private, never committed:** `CLAUDE.personal.md`, `settings.json`, `setup-state.json`, memory and
  transcripts (`projects/`), `backups/`, `proposals/`, each skill's `local/` and `.sandbox/`. A person's
  own agents and hooks sit inside the linked folders, kept untracked by `.gitignore`'s allowlist
  (`agents/opus-*`, `agents/fable-*`, and the four hook files by name).

## CLAUDE.md and AGENTS.md

`expand_imports` in `sync_agents_md.py` inlines every whole-line `@path` import (relative, `~/` or
absolute; five levels; never inside a code fence or mid-sentence) and fails loudly on a missing one.
`harness_parity.py` checks the expanded text. Generating `~/.codex/AGENTS.md` is paused since
2026-10-01 (Codex decoupled). The share bundle
expands with `CLAUDE.personal.example.md` standing in for the personal file, and renders its AGENTS.md
from that same text, so one person's machine never ships.

## The installer (`install/install.py`)

- **Plans before it touches anything:** every link and CLAUDE.md is surveyed first. A folder holding
  a file the repo lacks (outside the adoptable places) or a file that differs from the repo stops the
  whole run with a list; `--force-backup` moves such files to the backup instead.
- **Swaps safely:** the link is made under a temporary name, the original renamed into
  `backups/pre-install-<time>/`, then the link renamed into place; any failure renames the original
  back. `hooks/` matters most: a missing hook script blocks every tool call.
- **Adopts** a person's own agents, hooks and skill `local/`/`.sandbox/` files into the linked folders.
- **CLAUDE.md:** identical to the shared file → stub. Different and no personal file yet → it becomes
  the personal file. The example fills a missing personal file.
- **Settings merge:** `set` values are written when absent, or when they still equal what
  `setup-state.json` says was last applied — so a change to the fragment lands, and a deliberate
  personal override is kept and reported. `add` entries are appended when missing; `retire` entries are
  removed. A shared hook whose script does not exist is refused.
- **Afterwards:** runs `harness_parity.py`, and runs the credentials guard
  through Git Bash exactly as Claude Code would, requiring a refusal.
- **`--check`** reports drift; **`--uninstall`** replaces every link with a real copy of what it
  shows (so no edit since install is lost) and CLAUDE.md with the shared text.

## Changes travel by pull

`post-merge`, `post-rewrite` (rebasing pull) and `post-checkout` (a fast-forward in rebase mode, which
runs neither of the others) all run the installer, so a pull applies the other person's links,
settings and AGENTS.md at once. `pre-commit` (`install/precommit.py`) refuses paths outside the shared
layout and credential-shaped text — full token shapes, so docs may name the prefixes; `--all` sweeps
every tracked file. There is only `main`: pull with `--rebase`, then push.

## Checks

- `install/verify.py` — every check the setup has, one line each, through the linked paths.
- `install/test_setup.py` — import expansion, settings merge, pre-commit, Git Bash lookup, and the
  installer in scratch homes (fresh install, re-run, `--check`, uninstall, a failed swap, a foreign
  file), and that only `agents/*-lead.md` keeps the Agent tool. Its guards are falsified by
  `skills/asdev-web-audit/scripts/falsify/setup-repo.json`, from the repo root:
  `falsify.py --suite "python install/test_setup.py" --mutations <that file>`.
- The partner's first install was rehearsed from a clone in a scratch home, including a merge pull and
  a rebasing pull that each applied a shared settings change (2026-09-30).

## The share bundle

`share_bundle.py` still packages the in-house skills, the in-house agents and the expanded config for
one-off sharing with people outside the repo (decided 2026-09-30).
