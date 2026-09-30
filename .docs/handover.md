# Handover — `~/.claude` global setup — 2026-09-30 (evening)

## State
- **Under git since today:** the shared parts live in the private repo `Vikestart/claude-agentic-setup`,
  cloned at `~/.claude/claude-agentic-setup`; `~/.claude/agents`, `hooks`, `.docs` and each
  `skills/asdev-*` are junctions into it, `~/.claude/CLAUDE.md` is an import stub. Branch `main`, in
  sync with origin (checked with `git fetch` just before this handover); this handover's docs are
  committed and pushed at the end of it.
- Checks, last run after the final code change: `install/verify.py` 16/16 (both self-tests, parity,
  AGENTS.md in sync at 78 lines, guard tests 25/25, context-guard tests 10/10, setup tests, audit gate
  0 blocking on every skill and the repo) · `install.py --check` in place · 12/12 guards falsified.
- A fresh session (owner's probe) loads both import levels and sees 12 agents and 7 `asdev-*` skills.
- Deployment: n/a (tooling; live on write, and on the other machine at its next pull). No project
  repository under htdocs was changed.

## Since the last handover
- **Shared setup repo** — plan, build, install, reviews, push →
  [`walkthrough.md`](walkthrough.md), [`changelog.md`](changelog.md),
  [`reference/setup-repo.md`](reference/setup-repo.md).
- Fable confirmed running at `xhigh` (roadmap item closed; `reference/setup-architecture.md`).

## Decisions
- Links (junctions) into a repo in its own subfolder, not `~/.claude` as the repo — tokens, memory and
  transcripts are then outside any working tree (→ `reference/setup-repo.md`, `setup-architecture.md`).
- `--uninstall` copies the current repo content back instead of restoring backups, so no edit is lost.
- A pull applies the other maintainer's changes by itself (post-merge / post-rewrite / post-checkout).
- The setup repo has only `main`; CLAUDE.md's Branches bullet names it as the exception.

## Next
1. **Agents stop polling long runs** — roadmap item 1: a small edit to the `asdev-orchestrator` skill
   (and possibly the executor definitions), from the owner's Tilspire report.
2. **Automation mining** — roadmap item 2: the transcript-mining script, then `patch.py` first. This
   session improvised all-or-nothing patch scripts ~6 more times and hit the heredoc-backslash trap
   twice more — more evidence for `patch.py`.
3. **Self-started fresh sessions** — roadmap item 3.

## Open questions for the owner
- Add the partner as a collaborator on GitHub (owner action); they follow the repo's `README.md`.
- Whether `~/.claude/backups/pre-install-20260930-180134` (originals before the install) can go.
- The terminal `claude` CLI login is still expired (`claude /login`); headless probes need it.
- Disable connectors a project never uses (owner action; the base context was ~82k per turn).
- astole's local commit `97dac17` — moot if the repo is deleted, as the owner intends.

## Read first
- [`roadmap.md`](roadmap.md), [`reference/setup-repo.md`](reference/setup-repo.md),
  [`reference/setup-architecture.md`](reference/setup-architecture.md), [`reference/traps.md`](reference/traps.md)
