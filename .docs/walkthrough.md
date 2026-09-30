# Walkthrough — the global setup in a shared private repo (2026-09-30)

## What was built

- The private repo `Vikestart/claude-agentic-setup`, cloned at `~/.claude/claude-agentic-setup` and
  pushed (`main`, 4 commits). `~/.claude/agents`, `hooks`, `.docs` and each `skills/asdev-*` are
  junctions into it; `~/.claude/CLAUDE.md` is a stub importing `CLAUDE.shared.md`; the owner's machine
  bullets are in the private `~/.claude/CLAUDE.personal.md`.
- `install/install.py` (install, `--check`, `--force-backup`, `--uninstall`), `install/precommit.py`
  and four tracked git hooks (pre-commit scan; apply-on-pull), `settings/shared-settings.json`,
  `install/verify.py` (every check, one line each), `install/test_setup.py` (16 tests).
- `sync_agents_md.py` expands imports; `harness_parity.py` and `security_audit.py` work through
  junctions; `share_bundle.py` never ships the personal file.
- Docs: [`reference/setup-repo.md`](reference/setup-repo.md), new traps, the agent-policy reasons and
  cost-measurement method moved out of private memory into `setup-architecture.md`.

## How it was verified

- All 102 moved files hash identically through the links; `verify.py` 16/16 (both self-tests, parity,
  AGENTS.md, both hook suites, setup tests, the gate on every skill and the repo: 0 blocking).
- AGENTS.md differs from before only by its header, the §2 note and the moved "never push to `main`".
- 12 guards falsified RED for the right reason (`skills/asdev-web-audit/scripts/falsify/setup-repo.json`).
- The partner's first install rehearsed from a clone in a scratch home, 18/18, including a merge pull
  and a rebasing pull that applied a shared settings change by themselves. It caught a real bug: in a
  git hook, Git Bash was not found, so no pull would have applied anything.
- A fresh session (owner's probe) quoted the personal and the shared rule and listed 12 agents and
  7 `asdev-*` skills: nested imports and discovery through junctions both work.
- `precommit.py --all` clean; the Fable review scanned the full history: nothing private.

## Reviews and agent spend (`agent_audit.py`)

| Agent | Model · effort | Turns | Peak context | Weighted |
|---|---|---|---|---|
| Plan review | Opus 5.5 · xhigh | 26 | 134k | 0.45M |
| Final review | Fable 5.1 · xhigh | 11 | 145k | 0.38M |

The plan review found 11 real defects (fixed before building); the final review 5 (fixed before the
push). The build ran in the main chat at `high`.

## Where to look

`~/.claude/claude-agentic-setup/README.md` (setting up a machine), `reference/setup-repo.md` (how it
works), `reference/traps.md` (Windows and shell).
