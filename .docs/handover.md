# Handover — `~/.claude` global setup — 2026-09-30 (night)

## State
- Repo `~/.claude/claude-agentic-setup`, branch `main`, in sync with origin (`git fetch` just before
  this handover); tree clean apart from this handover's docs, committed and pushed at its end.
- Checks after the last code change: `install/verify.py --gate .` 16/16 (web-audit self-test 31/31,
  context guard 15/15, credentials guard 25/25, setup tests incl. the new `unset`, parity, AGENTS.md in
  sync, audit gate 0 blocking) · `install.py --check` in place · every guard added today falsified.
- Deployment: n/a (tooling; live on write here, on the partner's machine at their next pull, where
  the post-merge installer also retires the removed hooks and the `autoCompactWindow` key).
- No project repository under htdocs was changed.

## Since the last handover
- Agents start a long run once in the background and end the turn; the completion notice wakes
  them (orchestrator skill + all executor definitions). Only background agents are woken.
- `automation_mine.py` (audit suite): ranks throwaway scripts and repeated command sequences from the
  transcripts by the tokens spent writing them. September baseline in `roadmap.md` item 2.
- `patch.py` (audit suite): exact, all-or-nothing replacements from an unescaped spec; CLAUDE.md §0
  points at it. Built because patch scripts topped the ranking (~4,300 runs, ~2.4M tokens).
- Context: no automatic compaction cap. Past ~400k the context hook tells the main chat to ask the
  owner once whether to `/compact` (again every +100k). A cap and a self-raising script were built,
  proven inert in a running desktop session, and removed. → `reference/traps.md`,
  `reference/setup-architecture.md` (context_guard row).
- Installer: `unset` section in `settings/shared-settings.json` removes a key only while it holds the
  value the setup wrote (`reference/setup-repo.md`, settings merge).

## Decisions
- No compaction cap; the owner's word on the hook's question is the override — a running app
  session ignores `autoCompactWindow`, and a model cannot compact itself (→ `traps.md`).
- The owner wants self-managing mechanisms, not admin tasks; owner input shrinks to one word asked
  once (memory `self-managing-not-admin`).

## Next
1. **Self-started fresh sessions** — roadmap item 1, with today's findings in it. Start with
   `ToolSearch` for `start_session` / `hand_off_to_session`; if still absent, find what enables them,
   then weigh the fallbacks listed there. Goal: this handover skill ends by starting its successor.
2. **The next mined script** — roadmap item 2: falsify runs without a hand-written mutation file.

## Open questions for the owner
- Add the partner as a collaborator on GitHub (owner action).
- Whether the backups can go: `~/.claude/backups/pre-install-20260930-*` (four folders now, one per
  settings apply today) and the older dated files beside them.
- The terminal `claude` CLI login is still expired (`claude /login`); headless probes need it.
- Disable connectors a project never uses (owner action; ~16k of MCP tool text per turn here).

## Read first
- [`roadmap.md`](roadmap.md), [`reference/setup-architecture.md`](reference/setup-architecture.md),
  [`reference/traps.md`](reference/traps.md), [`reference/setup-repo.md`](reference/setup-repo.md)
