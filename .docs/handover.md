# Handover — `~/.claude` global setup — 2026-09-30 (late)

> **Done since (2026-09-30, the verification session):** the plan's verification, steps 4–5 and the
> detached review are complete and pushed; see [`walkthrough.md`](walkthrough.md). "State" and "Next" item 1
> below are history. The open owner questions still stand, and the phase leads were then rolled back (see `walkthrough.md`).

## State
- Repo `~/.claude/claude-agentic-setup`, branch `main`, **ahead of origin on purpose**: `0454fc9`
  (phase leads steps 1–3) and this handover are held back until the next session's checks pass.
  Pushed earlier today: `7224c55` (handover starts its successor), `440a9d9` (falsify reads a block spec).
- Checks after the last change: `install/verify.py --gate .` 16/16, `install.py --check` in place,
  the new agent-definition test falsified 3/3.
- Applied on this machine: `autoCompactWindow` 400000, `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH` 2,
  and the two lead definitions (live through the junctions). The partner gets nothing until the push.
- Setup backups moved to the Recycle Bin (owner's word). Claude Code's own `.claude.json.backup.*`
  files stay.

## Since the last handover
- Roadmap item 1: `start_session` / `hand_off_to_session` sit behind a vendor rollout gate
  (→ `reference/traps.md`). The handover skill now starts its successor once that tool appears, and
  meanwhile offers a `spawn_task` chip outside git repositories.
- Roadmap item 2: `falsify.py --mutations` takes `patch.py`'s unescaped block spec.
- The owner's alternative to item 1: **phase leads**, i.e. two-level orchestration, plus the 400k cap
  back. Planned, reviewed, and half built: [`implementation_plan.md`](implementation_plan.md).

## Decisions
- A plan gives each phase a lead and an agent budget, and the lead picks its roster within it
  (owner, 2026-09-30).
- Leads must be **shown to be efficient**, not only to work (owner, 2026-09-30). The plan's
  "Efficiency trial" fixes the decision rule before the numbers come in.

## Next
1. `implementation_plan.md`, from "Verification":
   - the cap check (`get_usage` on this new session);
   - the efficiency trial, which carries the nesting probe;
   - then steps 4–5 and the detached review;
   - push only once all of that passes.
   The rule text in step 4 is core architecture: at `high` effort, or hand it to `opus-high-executor`.
2. After that, roadmap "Later" items. The remaining mined scripts are Nebulingo's (its own roadmap).

## Open questions for the owner
- Add the partner as a collaborator on GitHub (owner action).
- The terminal `claude` CLI login is still expired (`claude /login`); headless probes need it.
- Disable connectors a project never uses (owner action; ~16k of MCP tool text per turn here).

## Read first
- [`implementation_plan.md`](implementation_plan.md), [`roadmap.md`](roadmap.md),
  [`reference/traps.md`](reference/traps.md), [`reference/setup-architecture.md`](reference/setup-architecture.md),
  [`reference/setup-repo.md`](reference/setup-repo.md)
