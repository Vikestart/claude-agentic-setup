# Global setup — architecture and decisions

How `~/.claude` is put together, and why. Traps that cost real time are in [`traps.md`](traps.md);
how the shared repo, its installer and the links work is in [`setup-repo.md`](setup-repo.md).

## Layout

| Path | What it is |
|---|---|
| `claude-agentic-setup/` | The private shared repo (`Vikestart/claude-agentic-setup`). Everything below marked *linked* is a junction into it; see [`setup-repo.md`](setup-repo.md). |
| `CLAUDE.md` | A one-line stub importing `claude-agentic-setup/CLAUDE.shared.md`: the global instructions, a ~15 kB **core** of rules that must apply before any skill loads. Everything procedural lives in a skill, named by path. |
| `CLAUDE.personal.md` | Each person's machine and hosting bullets (local dev, browser, production), imported by the shared rules in §2. Private; never in the repo. |
| `skills/asdev-*` | The seven in-house skills (below), *linked* one junction each. Every other folder in `skills/` is third-party and stays outside the repo. |
| `agents/*.md` | *Linked.* Fourteen subagent definitions (`opus-*`, `fable-*`), each fixing model AND effort in its frontmatter; the two `*-lead` definitions are dormant (see the decision below) and are the only ones that keep the Agent tool, which a setup test guards. A person's own agents sit in the same folder, untracked. |
| `hooks/guard_credentials.py` | `PreToolUse` guard for Bash and PowerShell (see Credentials); tests in `hooks/test_guard_credentials.py`. |
| `hooks/context_guard.py` | `PostToolUse` hook: past ~250k context, adds one notice telling the main chat to propose a handover or a subagent to hand back (finds an agent's own transcript from `agent_id`). Past ~400k it tells the main chat instead to ask the owner once whether to `/compact`, again every +100k; agents never get that question. The settings also cap sessions at `autoCompactWindow` 400k (restored 2026-09-30 at the owner's request); a session already running when it was set ignores it (`traps.md`), and for that case the owner's word on this question is the override. `CONTEXT_GUARD_LIMIT` / `_STEP` / `_COMPACT` / `_COMPACT_STEP` tune it; tests in `hooks/test_context_guard.py`. |
| `settings.json` | Private. The installer merges into it what the setup owns (`settings/shared-settings.json` in the repo): subagent caps, the 1-hour agent cache (`subagentPromptCacheTtl`), `workflowSizeGuideline`, the scanner allow rules, the credentials deny rule, and both hooks. `setup-state.json` records what it last applied. |
| `~/.codex/AGENTS.md` | **Generated** from `CLAUDE.md` and its imports by `sync_agents_md.py`; never edited directly. |
| `.docs/` | *Linked.* This setup's own working documents, shared by both maintainers. `backups/` (private) holds what each install replaced. |
| `proposals/` | Private drafts not yet approved. |

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
- **Fable runs at `xhigh`** (confirmed 2026-09-30 with `agent_audit.py`: the first `fable-xhigh-reviewer` recorded `xhigh`), so the `fable-xhigh-*` definitions are labelled truthfully.
- **Effort is fixed by the agent definition**, because the Agent tool takes no effort and built-in
  types inherit the session's. The floor for a significant sensitive change is `high` (it was `max`
  until 2026-09-25).
- **Context is the main cost, not effort** (2026-09-30). Measured in Nebulingo, Framvis and Tilspire:
  cost ≈ context size × turns plus re-caches after pauses. Hence a ~250k context ceiling (agents hand
  back, the main chat proposes a handover), fresh agents for corrections, one role per agent, split
  builds, quiet tools, and the 1-hour agent cache (`subagentPromptCacheTtl`). Rules in
  `asdev-orchestrator`; how the figures were measured is below.
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
- **A shared private repo, reached through links** (2026-09-30). The owner and their partner
  co-maintain the setup; links rather than copies mean every edit a session makes is already a git
  change, and the repo sits in its own folder so the login tokens, memory and transcripts are never
  inside a git working tree at all. Junctions and a CLAUDE.md import stub need no admin rights or
  Developer Mode on Windows. Details in [`setup-repo.md`](setup-repo.md).

## Agent policy — the owner's reasons (2026-09-25 to 09-30)

The roster is in CLAUDE.md §6 and `agents/`; these are the reasons behind it, so no session drifts back.

- **Nothing below Opus.** Sonnet and Haiku are retired: Opus 5.5 is better and cheaper, so Opus at `low`
  is the bottom tier.
- **`medium` is the default effort:** on the benchmarks Opus at `medium` keeps very high intelligence at
  low cost. `low` only for obviously easy work, `high` for very complex work.
- **The sensitive floor is `high`, not `max`:** the models are strong enough, and sessions kept stopping
  to ask the owner to raise the effort. Interruptions are a cost to the owner — which is also why a
  session below the floor hands the change to `opus-high-executor` without asking.
- **At most 10 subagents in total per task, phase or workflow run.** A queue was rejected: the point
  is not spawning many agents, and asking first when more seem needed.
- **Phase leads: built, trialled, rolled back (owner, 2026-09-30).** Each phase of a multi-phase run
  would go to a lead, so the main session keeps ~4k per phase instead of ~100k. The trial measured a
  lead's start-up at ~53k and ~4k per hand-back, with break-even under two phases, but only against
  a ~100k-per-phase baseline recorded before that day's context rules. Rolled back because the 400k
  cap and the handover cadence already bound a long session, and most sessions run one phase. Depth
  2 also removed the harness's own stop on nesting for every agent, and the nested mechanics are
  undocumented and fragile (`traps.md`, Nested agents). The definitions stay, dormant. Revive them
  only if the re-measure (roadmap) shows main sessions still keeping ~100k per phase. Revert the
  rollback commit and set the depth to 2.

## How the cost figures were measured

Regenerate rather than trusting old numbers: `agent_audit.py --summary` (it dedupes transcript `usage`
by `requestId`; see `traps.md`, Measurement). On 2026-09-01, of one main session's ~1M output tokens,
~65% was reasoning (only effort moves it), ~29% tool-call JSON (`Write` ~1,283 tokens a call against
`Edit` ~236 — hence "emit only what changes") and ~6% prose. Output is the small part of the bill:
context size × turns dominates, as measured on 2026-09-30 (figures in `asdev-orchestrator`).

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
