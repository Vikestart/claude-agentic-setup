# Global setup — architecture and decisions

How `~/.claude` is put together, and why. Traps that cost real time are in [`traps.md`](traps.md);
the owner's reasons for the agent model and effort policy are also in the htdocs memory
`agent-model-effort-policy`.

## Layout

| Path | What it is |
|---|---|
| `CLAUDE.md` | The global instructions — a ~15 kB **core** of rules that must apply before any skill loads. Everything procedural lives in a skill, named by path. |
| `skills/asdev-*` | The seven in-house skills (below). Every other folder in `skills/` is third-party. |
| `agents/*.md` | Twelve subagent definitions, each fixing model AND effort in its frontmatter. |
| `hooks/guard_credentials.py` | `PreToolUse` guard for Bash and PowerShell (see Credentials); tests in `hooks/test_guard_credentials.py`. |
| `hooks/context_guard.py` | `PostToolUse` hook: past ~250k context, adds one notice telling the main chat to propose a handover or a subagent to hand back (finds an agent's own transcript from `agent_id`). `CONTEXT_GUARD_LIMIT` / `_STEP` tune it; tests in `hooks/test_context_guard.py`. |
| `settings.json` | Subagent caps, the 1-hour agent cache (`subagentPromptCacheTtl`), the scanner allow rules, the credentials deny rule, and both hooks. |
| `~/.codex/AGENTS.md` | **Generated** from `CLAUDE.md` by `sync_agents_md.py`; never edited directly. |
| `.docs/` | This setup's own working documents. `~/.claude` is **not a git repository**; backups are OneDrive, `backups/`, and the share bundles in `~/Downloads/`. |
| `proposals/` | Drafted plans not yet approved, e.g. `setup-repo-migration.md`. |

## The in-house skills

| Skill | Holds | CLAUDE.md sends a session there when… |
|---|---|---|
| `asdev-planner` | Plan template, roster question, plan review, roadmap/plan/task rules, phase completion | a change reaches the Planning Gate, or a planned phase completes |
| `asdev-handover` | The handover steps, the memory-vs-reference rule, the paste-ready message and FYI, failures seen before | the owner approves a handover |
| `asdev-orchestrator` | Agent definitions table, rosters, spawning, briefs, verification, reviewers | before spawning an agent, proposing a roster, or a detached review |
| `asdev-release` | Release shape per project, pre-flight, branch sync, staging and production validation, rollback, when to pause | a merge into `staging` or `main`, a deploy, or a PR merged on GitHub |
| `asdev-web-audit` | The one scanner suite, falsification, archiving, the setup's own tooling scripts | the audit gate, and any guard or tooling work |
| `asdev-conventions` | House style, and the size budget for a project's CLAUDE.md / AGENTS.md | web work, or editing a project's instruction file |
| `asdev-blueprints` | The capability inventory and reference implementations | scaffolding, gap audits, adding a platform capability |

Each skill's private material lives in its `local/` overlay, which the share bundle excludes; every
skill must still work without it.

## Decisions, with their reasons

- **CLAUDE.md is a core; procedures are skills** (2026-09-29). CLAUDE.md is re-read every turn, so
  every line costs in every session. It went from 30 kB to 15 kB. Skills are named **by path**,
  because Codex cannot see `~/.claude/skills` but can open a file.
- **In-house skills are `asdev-*`** (2026-09-29), to separate them from third-party skills. A skill's
  identity is its folder name, so the rename moved folders (see `traps.md`).
- **Project files never repeat a path into `~/.claude`.** Only the local, uncommitted
  `.git/hooks/pre-commit` holds the scanner path; committed files name the tool and point at the
  global instructions. Repeated paths had already rotted in two projects.
- **`xhigh` is the highest effort proposed, for Opus and Fable** (2026-09-28). `max` spent more than
  twice the tokens of `xhigh` for next to no gain; the four `max` agents stay for owner overrides.
- **Effort is fixed by the agent definition**, because the Agent tool takes no effort and built-in
  types inherit the session's. The floor for a significant sensitive change is `high` (it was `max`
  until 2026-09-25).
- **Context is the main cost, not effort** (2026-09-30). Measured in Nebulingo, Framvis and Tilspire:
  cost ≈ context size × turns plus re-caches after pauses. Hence a ~250k context ceiling (agents hand
  back, the main chat proposes a handover), fresh agents for corrections, one role per agent, split
  builds, quiet tools, and the 1-hour agent cache (`subagentPromptCacheTtl`). Rules in
  `asdev-orchestrator`; evidence in the htdocs memory `measuring-agent-cost`.
- **The main chat runs at `medium`, `high` for sensitive work, never `max`** (2026-09-30); the owner
  sets it in the app.
- **Reviews:** Opus between rounds; one Fable review for sensitive material, after all planned work
  is built and **before production release**, so its findings never land on live code. A plan review
  only for a genuinely intricate, sensitive or complex plan.
- **One scanner copy, never one per harness.** Codex and Claude call the same suite;
  `harness_parity.py` asserts it.
- **`AGENTS.md` is generated.** `CANONICAL` in `sync_agents_md.py` is the single source for the model
  mapping and the banner; model names stay version-free so a `.1` release cannot make them stale.
- **Shareable by default:** all in-house skills go in the bundle; private content stays in `local/`.

## Credentials

`.credentials.json` in `~/.claude` holds the Claude login tokens. A `Read(...)` deny rule covers the
Read, Grep and Glob tools; the guard hook covers shells. Both, and their limits, are in `traps.md`
(Windows and shell). The guard is a heuristic against accidents; the sandbox's `credentials.files`
deny would be the airtight option, at the cost of sandboxing every shell command.

## Deferred by decision

- **Astra remap:** when Astra ships, `CANONICAL` re-ranks to `Fable→Astra, Opus→Sol` — a re-ranking,
  not an append, since Sol moves from Fable to Opus. Recorded in `sync_agents_md.py`.
- **No further coordination tooling:** the remaining output-token levers are already rules (effort;
  emit only what changes), and each new tool costs a review round.
- **Setup under git:** no longer deferred — queued 2026-09-30 as the next phase, shared with the
  owner's partner as co-maintainer (see the roadmap).
