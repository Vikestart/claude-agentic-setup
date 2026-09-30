# Walkthrough — phase leads and the 400k cap (2026-09-30)

> **Rolled back the same evening (owner's decision).** Spawn depth is 1 again and the lead rules are
> gone. The lead definitions stay, dormant. Kept: the 400k cap, the traps entries, the executors'
> foreground-shell note and the tightened agent-definition test. Why, and how to revive it:
> `reference/setup-architecture.md`, "Phase leads".

## What was built

- **Cap:** `autoCompactWindow` 400000 is back in `settings/shared-settings.json`. A session started
  after it compacts at ~368k (400000 × 92%).
- **Depth 2 and two lead definitions:** `agents/opus-medium-lead.md` and `agents/opus-high-lead.md`
  are the only definitions that keep the Agent tool. `install/test_setup.py` guards that, including
  the legacy `Task` name. `share_bundle.py` reads the depth from the shared settings.
- **Rules:** CLAUDE.md §1/§6 (phase leads, the approval exception, integration, the budget and the
  cap), orchestrator "Multi-phase runs", the planner's roster question and plan template, executor
  long-run text for foreground roster agents, and the handover chip note. AGENTS.md regenerated.
- **Docs:** `traps.md` (the cap obeyed, nested agents, foreground shells, new definitions in a
  running session, chip side sessions), `setup-architecture.md` (definitions, the lead decision),
  roadmap items 1 and "Re-measure".

## How it was verified

- **Cap:** `get_usage` in a new session: `contextWindow` 400000, `autoCompactsAtPercent` 92.
- **Probe, depth 2:**
  - A background lead's background leaf never reported to the lead. The harness made the lead hand
    back, and the leaf's result arrived at the main session.
  - Foreground spawns returned inline. Nonces matched the leaf transcripts (`eb063f2a4b11`,
    `ab29fa63657c`, `c80ed9ec7ad1`, `1b5ec8af273b`).
  - Nested transcripts are flat under the root session's `subagents/`, and `agent_audit.py` read
    them.
  - A second probe, a foreground agent with a 75-second background command, got no completion
    notice. The harness kills a foreground agent's background commands at its final response.
- **Efficiency trial:** two scratch repos, the same two-phase task.
  - Lead start-up is ~53k. A small-phase lead cost ~94k weighted. Each hand-back grew the main
    session by ~4k.
  - The baseline, 2026-09-30 main sessions: ~100k residue per phase over ~95 turns (Tilspire 88k →
    504k over four or five phases; Framvis 99k → 193k for one).
  - Break-even is under two phases for phases of that size. Leads are the default from two phases
    that each need a roster.
- **Detached review:** `opus-xhigh-reviewer` returned six should-fix findings and five nits. All
  were taken except the share-bundle README wording, which is correct by depth.
- **Checks:** `install/verify.py --gate .` 16/16; `install.py --check` in place; `falsify.py` on
  `falsify/setup-repo.json` 16/16.

## Agent spend (`agent_audit.py`, price-weighted)

| agent | definition | turns | peak | weighted |
|---|---|---|---|---|
| arm A lead (both phases) | opus-medium-lead | 12 | 74k | 226k |
| arm A leaves ×2 | opus-low-executor | 5 + 6 | 61k | 295k |
| arm B leads ×2 | opus-medium-lead | 10 + 6 | 64k | 281k |
| arm B leaves ×2 | opus-low-executor | 6 + 5 | 62k | 163k |
| detached review | opus-xhigh-reviewer | 27 | 123k | 443k |
| foreground-shell probe | opus-low-executor | 4 | 59k | 68k |

Ten agents in total, including the plan review, which is the 10-agent cap. The probe was the tenth.

## Where to look

`skills/asdev-orchestrator/SKILL.md` ("Multi-phase runs"), `agents/*-lead.md`,
`.docs/reference/traps.md` ("Nested agents"), `install/test_setup.py` (`AgentDefinitions`).
