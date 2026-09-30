# Handover — `~/.claude` global setup — 2026-09-30

## State
- Not a git repository; backups are OneDrive, `~/.claude/backups/` (latest: `CLAUDE-pre-context-2026-09-30.md`
  and `context-rules-2026-09-30/`) and the share bundles in `~/Downloads/`.
- Checks, run 2026-09-30 after the last change: `asdev-web-audit` self-test 24 OK · `asdev-blueprints`
  self-test 98 GREEN · `harness_parity.py` clean · `sync_agents_md.py --check` in sync (76 lines) ·
  `hooks/test_guard_credentials.py` 25/25 · `hooks/test_context_guard.py` 10/10 · `settings.json` valid.
  18 new guards falsified, all RED for the right reason.
- Deployment: n/a (tooling; live on write). No project repository was changed this session.

## Since the last handover (2026-09-29)
- **CLAUDE.md trimmed** (release steps → new `asdev-release` skill; setup maintenance → `asdev-web-audit`
  "Maintaining the setup"); `asdev-handover` and `asdev-release` fleshed out.
- **Context-cost phase**, from the Nebulingo, Framvis and Tilspire spend reports: ~250k context ceiling for
  agents and the main chat, fresh agents for corrections, one role per agent, split builds, quiet tools,
  main chat at `medium`/`high` never `max`, trimmed skill descriptions. New: `hooks/context_guard.py`
  (PostToolUse notice past the ceiling), `quiet.py`, context and weighted-cost figures in `agent_audit.py`,
  a warnings count on `falsify.py`'s last line. `"subagentPromptCacheTtl": "1h"` in `settings.json`
  (owner's pointer; subagents cached for 5 minutes before).
- A detached `opus-xhigh-reviewer` review found 8 real defects (release proof over-reach, `quiet.py` under
  cmd.exe and orphaned children on timeout, the hook going silent after compaction and repeating "ask
  once", the approval path for fresh agents, a review rule lost from CLAUDE.md); all fixed and falsified.

## Decisions
- All of them, with reasons → [`reference/setup-architecture.md`](reference/setup-architecture.md) (see
  "Context is the main cost, not effort"). Traps → [`reference/traps.md`](reference/traps.md), new today:
  the 5-minute agent cache, cmd.exe under `shell=True`, backslashes halved in Bash-tool heredocs.

## Next
1. **Shared setup under git** with the owner's partner (Windows, co-maintainer) — roadmap item 1. Planning
   Gate: rewrite `../proposals/setup-repo-migration.md` into `implementation_plan.md` first.
2. **Automation mining** — roadmap item 2: a transcript-mining script, then the scripts it justifies
   (`patch.py` first).
3. Watch the first sessions: does the context hook fire and get acted on (agents especially — not yet seen
   live in a subagent), and do the `asdev-*` skills load at the right moments.

## Open questions for the owner
- astole's local commit `97dac17` — moot if the repo is deleted, as the owner intends.
- The terminal `claude` CLI login is expired (`claude /login`); only headless probes need it.
- Disable connectors a project never uses (owner action; the base context was ~82k per turn).

## Read first
- [`roadmap.md`](roadmap.md), [`reference/setup-architecture.md`](reference/setup-architecture.md),
  [`reference/traps.md`](reference/traps.md), `../proposals/setup-repo-migration.md`
