# Implementation plan — phase leads and the 400k cap

**Goal:** a session that runs several approved phases stays small. For each phase it spawns one
*phase lead* agent, which briefs and runs that phase's own roster, integrates the work and hands back
a short report. The main session keeps scope across phases, owner questions, verification and
release. With the 400k auto-compaction cap back, a main session that still grows gets compacted
instead of reaching 1M. This is the stand-in for self-started sessions, which are waiting on the
vendor's rollout (roadmap item 1).

**Decided (owner, 2026-09-30):** two levels of orchestration; bring back the 400k cap; a plan gives
each phase a lead and an agent budget, and the lead picks its roster within it.

**Revised after the detached plan review (2026-09-30):** all nine findings taken; see "Review" below.

**Progress:** steps 1–3 done 2026-09-30, committed locally, not pushed. Settings applied here
(cap 400000, depth 2). The setup test is falsified 3/3 and its mutations are stored in
`falsify/setup-repo.json`. **Next session starts at "Verification": the cap check, then the
efficiency trial, which carries the probe.**

## Facts this rests on (checked 2026-09-30)
- Nesting is a setting, not a platform limit. The binary refuses a spawn when the depth reaches
  `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH`, which is global, not per definition. Today it is `"1"` in
  `settings/shared-settings.json`, and every in-house definition also has `disallowedTools: Agent`.
- At depth 2, `general-purpose` (tools `*`) and forks can nest too. Only rules and the definitions'
  frontmatter keep other agents from spawning, so a setup test must guard the frontmatter.
- `autoCompactWindow` was only shown to be ignored by a session **already running** when it was set.
- A session cannot spawn a definition written after it started. So the probe runs in a new session.
- The concurrency cap looks session-wide: nested agents share the parent's task registry.

## Session split
- **This session:** steps 1–3, committed locally, **not pushed**. Everything is live on the owner's
  machine on write; nothing reaches the partner until the push.
- **Next new session (the first after step 1):** the cap check and the probe, then steps 4–5, the
  detached review, and the push. If that session is not this plan's continuation, the handover says so.

## Steps
1. **Cap.** In `settings/shared-settings.json`, move `autoCompactWindow: 400000` from `unset` to
   `set`; apply with `install.py`. Correct the text that says there is no cap: orchestrator
   SKILL.md ~80-82, the `context_guard.py` docstring, `traps.md` ~55-64, `setup-architecture.md`
   row 16. The hook's `/compact` question stays, for sessions that started before the cap.
2. **Depth.** `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH` `"1"` → `"2"` in the same file.
   `share_bundle.py` reads the value from `shared-settings.json` instead of hardcoding it, and its
   comment stops saying the setting stops nesting.
3. **Leads, with their guard.**
   - Add `agents/opus-medium-lead.md` and `agents/opus-high-lead.md`, with the Agent tool allowed.
     `high` is for any phase that touches something sensitive (the effort floor).
   - A setup test: every `agents/*.md` other than `*-lead.md` disallows `Agent`. Falsify it.
   - The lead contract, written in both definitions:
     - the phase section of the approved plan is the brief;
     - **approving a lead with a budget is the owner's request to spawn within it** (the exception to
       CLAUDE.md "a plan that names subagents" and "delegation needs my explicit request");
     - roster from Opus executors and reviewers only; never a `max` or Fable definition, never
       `general-purpose` or a fork;
     - roster agents start in the background, and the lead ends its turn (the probe may change this
       to foreground);
     - every agent it or an earlier lead of the phase spawned counts against the phase budget;
       the report states "agents spawned so far";
     - integrate, run the gate, falsify new guards, commit on the working branch; **never push,
       merge or release**;
     - hand back only once its roster has finished or been stopped; list any still running;
     - a question for the owner ends the phase in the report;
     - the report is at most ~40 lines: outcome, commits, checks and their verdicts, open questions,
       agents spawned so far, notes for the next phase.
4. **Rules — written after the probe passes.**
   - CLAUDE.md §6 and :20/:57: the lead exception for approval, delegation and integration; the
     10-agent cap counts a lead, its roster and its continuations per phase; leads run one at a
     time; `general-purpose` and forks never spawn.
   - Orchestrator skill: "Subagents … never spawn further agents" and "In a planned phase you stay
     the orchestrator" gain the exception. A new "Multi-phase runs" section says:
     - leads run one at a time, spawned in the background;
     - the main session re-runs `audit_all.py --since <phase base>` and reads `git log` itself;
       it does not take the lead's reported verdict;
     - a lead that hands back at ~250k gets a continuation lead, briefed with the hand-back and the
       count of agents spawned so far;
     - an owner's answer goes to a fresh continuation lead, unless the resume conditions hold
       (under ~150k and inside the cache hour);
     - the main session owns the phase-completion routine and release.
   - Planner skill: the roster question for a multi-phase plan names each phase's lead and budget.
   - Regenerate `AGENTS.md` ("Maintaining the setup").
5. **Docs.** `traps.md` (depth, nesting, probe results), `setup-architecture.md` (agents,
   settings), roadmap item 1, the changelog and walkthrough.

## Verification
- **Setup test** for the frontmatter (step 3), falsified.
- **Cap (next session).** `get_usage` on that session: `contextWindow` × `autoCompactsAtPercent`
  lands near 400k, not ~970k. If not, move the key back to `unset`, record it in `traps.md`, and
  correct the step-1 text back.
- **Probe (next session).**
  - The lead is spawned in the background. It starts one `opus-low-executor` in the background
    whose only job is to run a background command printing a nonce, e.g.
    `python -c "import secrets;print(secrets.token_hex(6))"`, then return it.
  - It passes only if all of these hold:
    - the lead's transcript shows `run_in_background: true` on its spawn;
    - the lead ended a turn before the leaf finished;
    - the returned nonce matches the one in the leaf's transcript;
    - the leaf's transcript is at the flat `subagents/agent-<id>.jsonl` path that
      `context_guard.py` and `agent_audit.py` read, and `agent_audit.py --agent <leaf>` reports it.
  - If background waking fails, rerun with foreground spawns and set that mode in the definitions.
  - If both modes fail, revert steps 2–3, keep the cap per its own check, and push nothing of the
    lead work.
- **Efficiency trial (next session; owner request 2026-09-30).** Leads do not cut the total work,
  they move it. Each lead costs a fixed start-up (system prompt, CLAUDE.md, skills, the brief), and
  saves the main session from re-reading each finished phase on every later turn. Whether that nets
  out is measured, not assumed:
  - Two scratch git repos, one identical two-phase task (a small module with tests; phase 2 builds on
    phase 1). Each phase's roster is one `opus-low-executor`.
  - **Arm A (one long orchestrator):** one `opus-medium-lead` runs both phases in a row, as a main
    session does today.
  - **Arm B (leads):** the main session spawns one lead per phase, in turn, passing only the
    hand-back. Arm B's leaves also carry the probe's nonce, so the probe rides on it.
  - Measure with `agent_audit.py` (turns, peak context, price-weighted total, per agent) and
    `get_usage` on the main session before and after each lead:
    - L, one lead's fixed start-up;
    - R, the context each finished phase leaves in the orchestrator (arm A: its context at phase 2's
      start minus at phase 1's start; arm B: main-session growth per lead report);
    - T, each arm's total weighted cost.
  - **Decision rule, fixed now:** from R, L and the main session's turns per phase (read from the
    2026-09-30 Nebulingo, Framvis and Tilspire sessions with `agent_audit.py`), compute the phase
    count at which leads break even. Leads become the default for multi-phase runs only if that
    break-even is at or below the phase count those plans typically hold. Otherwise they are an
    option for long runs, starting at the break-even count. Either result goes in the orchestrator
    skill with its numbers.
  - A two-phase toy understates the saving, which grows with phases and residue. So the rule
    extrapolates from measured L and R instead of reading T directly. The first real multi-phase run
    with leads is then compared against the 2026-09-30 figures (roadmap: "Re-measure").
- `install/verify.py --gate .` passes (count as `verify.py` derives it), and so does `install.py --check`.
  It does not exercise depth, leads or the cap; the checks above do.

## Subagents
| role | definition | model | owns | checks |
|---|---|---|---|---|
| arm A lead | `opus-medium-lead` (new) | Opus 5.5 | scratch repo A | runs both phases |
| arm A leaves ×2 | `opus-low-executor` | Opus 5.5 | scratch repo A, one phase each | the phase's tests |
| arm B leads ×2 | `opus-medium-lead` (new) | Opus 5.5 | scratch repo B, one phase each | spawn the leaf in the background |
| arm B leaves ×2 | `opus-low-executor` | Opus 5.5 | scratch repo B, one phase each | the phase's tests + the probe nonce |
| detached review | `opus-xhigh-reviewer` | Opus 5.5 | read-only | rule text, definitions, setup test against CLAUDE.md §6 |

Plan review already run: 1 agent. Next session: 8. Total: 9, within the cap.

## Release
Setup repo: `main` only. Push only after the cap check, the probe and the detached review. The
partner gets it at their next pull through the post-merge installer. Rollback: the installer takes
depth back to `"1"` and removes a cap moved back to `unset`, since both still equal the last
applied value.

## Residual risks
- A lead's context grows like a main session's used to. The ~250k hook tells it to hand back.
- The main session sees less of each diff. It re-runs the gate and reads the log itself, and the
  detached review at the end of sensitive work stays.
- One lead can fill all 10 concurrent slots, leaving the main session none alongside it.

## Review (2026-09-30, `opus-xhigh-reviewer`)
Taken: the approval exception (1), the frontmatter test and the ban on `general-purpose`/fork nesting
(2), the probe in a new session with a nonce (3), the transcript-path check (4), the hand-back
order and fresh continuations (5), budgets over continuations, no `max`/Fable, one lead at a time (6),
the stale cap text (7), push after checks and the both-modes-fail branch (8), and "never push", the
completion owner, the main session's own gate, the derived check count and the cap arithmetic (9).
Not taken: an `Agent(type)` allowlist on leads, because its syntax for subagents is unverified. The
frontmatter test and the rules cover the same ground.
