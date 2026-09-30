# Handover — `~/.claude` global setup — 2026-09-30 (night)

## State
- Repo `~/.claude/claude-agentic-setup`, branch `main`, in sync with origin at `e5f3986` (before this
  docs commit); uncommitted: none. The partner gets it at their next pull.
- Applied on this machine: `autoCompactWindow` 400000, spawn depth 1 (back from 2).
- Checks at the last commit: `install/verify.py --gate .` 16/16, `install.py --check` in place,
  `self_test.py` OK, falsify 16/16 (`setup-repo.json`) and 5/5 (`context-override.spec`).
- Next session's context limit: shared cap (no override; `context_override.py status` → none).

## Since the last handover
- The 400k cap is proven for new sessions: they compact ~30k below the limit.
- Phase leads (two-level orchestration): built, trialled, reviewed, then **rolled back** at the
  owner's decision. Why, and when to revive → `reference/setup-architecture.md` ("Phase leads");
  the mechanics → `reference/traps.md` ("Nested agents"); the trial → `walkthrough.md`.
- New: the handover can raise the next session's limit for one project, on request or by its own
  judgement, and the next handover clears it (`context_override.py`, handover skill step 4b; a
  project-level override reaches a new session, `traps.md`).
- Traps added: foreground agents lose background commands at their final response; a running
  session may be offered new agent definitions; a `spawn_task` chip session is a side session.

## Decisions
- Phase leads rolled back; the cap stays (owner, 2026-09-30) — the saving rested on a pre-rule
  baseline, the cap and handover cadence already bound sessions, and depth 2 removed a hard guard
  (→ `reference/setup-architecture.md`).
- Context-limit overrides are per project, set at handover, cleared by the next one; a hand-set
  value is never touched (→ `reference/traps.md`, the `asdev-web-audit` skill).

## Next
1. Roadmap "Later" items; the remaining mined scripts are Nebulingo's (its own roadmap).
2. The re-measure (roadmap) also records main-session growth per phase: the trigger for reviving
   phase leads.

## Open questions for the owner
- Add the partner as a collaborator on GitHub (owner action).
- The terminal `claude` CLI login is still expired (`claude /login`); headless probes need it.
- Disable connectors a project never uses (owner action; ~17k of MCP tool text per turn here).

## Read first
- [`roadmap.md`](roadmap.md), [`reference/setup-architecture.md`](reference/setup-architecture.md),
  [`reference/traps.md`](reference/traps.md), [`reference/setup-repo.md`](reference/setup-repo.md)
