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
| `hooks/context_guard.py` | `PostToolUse` hook: past ~250k context, tells a subagent to hand back (finds its own transcript from `agent_id`); again every +50k. Silent for the main chat since 2026-09-30 (see Decisions, "Compaction, not fresh chats"). `CONTEXT_GUARD_LIMIT` / `_STEP` tune it; tests in `hooks/test_context_guard.py`. |
| `hooks/after_compact.py` | `SessionStart` hook, matcher `compact`: after a compaction, names the working docs present in the session's `.docs/` and tells it to re-read them; a general reminder in a folder without `.docs/` (sessions started at the htdocs root); silent on any other start. Since 2026-10-01 it also restores the session's last message before the compaction, verbatim (from the transcript; capped at 6,000 characters), because the summary paraphrases it and it is usually what the owner is replying to. Tests in `hooks/test_after_compact.py`, falsified by `falsify/compact-hook.spec` and `falsify/compact-reply.spec`. |
| `settings.json` | Private. The installer merges into it what the setup owns (`settings/shared-settings.json` in the repo): subagent caps, the 1-hour agent cache (`subagentPromptCacheTtl`), `workflowSizeGuideline`, the scanner allow rules, the credentials deny rule, and both hooks. `setup-state.json` records what it last applied. |
| `~/.codex/AGENTS.md` | **Decoupled** (owner, 2026-10-01): no longer generated or checked; the file was deleted the same day. |
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

- **Compaction, not fresh chats** (owner, 2026-09-30). Sessions never propose a handover or ask the
  owner to `/compact`: the owner wants no manual steps, and a session cannot start its successor
  (`traps.md`, "A cleared session wakes only on a message"; the relay was tried and rolled back).
  Automatic compaction at 92% of the 400k window costs about the same per turn as handing over at
  ~250k once the handover's own turns are counted; what it loses is fidelity, so the docs carry the
  state (updated at every phase boundary), CLAUDE.md §1 tells the summary what to keep, and
  `after_compact.py` sends the session back to the docs. Owner-requested handovers remain (another
  machine, the partner, a long break). Revisit when `start_session` ships.

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
  back; the main chat compacts instead since 2026-09-30, see "Compaction, not fresh chats"), fresh agents for corrections, one role per agent, split
  builds, quiet tools, and the 1-hour agent cache (`subagentPromptCacheTtl`; re-measured 2026-10-01
  over 75 agents: 96.16M with it, 95.93M as if 5-minute — the 2× write premium and the re-caches it
  avoids cancel out; kept, because the background-run rule creates those pauses and the 1-hour
  cache caps a long wait's cost). Rules in
  `asdev-orchestrator`; how the figures were measured is below.
- **Executors and reviewers carry an explicit `tools:` list** (2026-10-01). Start-up context is
  re-read on every turn, and tool definitions were most of it: 46.3k with every tool, 26.8k for an
  executor and 26.0k for a reviewer after (CLI, `claude -p --agent`); desktop agents started at
  52–55k before. Kept by 30 days of use: core tools, the built-in browser (1,039 agent uses, reviewers
  too), Chrome DevTools (131; ~1k), WebFetch/WebSearch (~0.1k). Dropped: computer use, Claude in
  Chrome, docs, visualize, Artifact (6 uses), workflows, scheduled tasks, session management.
  Reviewers have no Edit/Write. `test_setup.py` enforces both; the dormant leads are untouched.
  An agent that needs a dropped group says so, and the group goes back into that definition.
  Large files are read through `code_map.py` / `code_show.py` (audit suite) rather than dumps.
- **Working files have size budgets, enforced, not only stated** (2026-10-01). The lifecycle rules
  already said to prune, yet Tilspire's roadmap reached 101 kB and Nebulingo's changelog 112 kB,
  re-read again and again by every agent; the old 15 kB check was advisory and unread. Now one
  table in `doc_hygiene.py` (`BUDGET_KB`, `BUDGET_LINES`), a Trim step that ends every phase
  completion and handover until it is clean, and the after-compact hook naming over-budget files.
- **The main chat runs at `medium`, `high` for sensitive work, never `max`** (2026-09-30); the owner
  sets it in the app.
- **Reviews:** Opus between rounds; one Fable review for sensitive material, after all planned work
  is built and **before production release**, so its findings never land on live code. A plan review
  only for a genuinely intricate, sensitive or complex plan.
- **One scanner copy, never one per harness.** Codex and Claude call the same suite;
  `harness_parity.py` asserts it.
- **Codex is decoupled** (owner, 2026-10-01: "We won't use it"). `~/.codex/AGENTS.md` was generated
  from CLAUDE.md by `sync_agents_md.py` and checked by the installer and the gate; both calls are
  gone. The script stays (its import expander is still used, and the model mapping is there to resume
  from). Project `AGENTS.md` files are unaffected: they remain each project's canonical instructions.
- **Shareable by default:** all in-house skills go in the bundle; private content stays in `local/`.
- **A shared private repo, reached through links** (2026-09-30). The owner and their partner
  co-maintain the setup; links rather than copies mean every edit a session makes is already a git
  change, and the repo sits in its own folder so the login tokens, memory and transcripts are never
  inside a git working tree at all. Junctions and a CLAUDE.md import stub need no admin rights or
  Developer Mode on Windows. Details in [`setup-repo.md`](setup-repo.md).

## Agent policy — the owner's reasons (2026-09-25 to 09-30)

The roster is in CLAUDE.md §6 and `agents/`; these are the reasons behind it, so no session drifts back.

- **Nothing below Opus, except Sonnet for trivial work.** Sonnet and Haiku were retired on 2026-09-25
  (Opus 5.5 better and cheaper). On 2026-10-01 the owner brought Sonnet back for one role:
  `sonnet-medium-executor` takes the trivial work `opus-low-executor` did (suite runs, doc edits,
  well-specified mechanical fixes). The Opus `low` file stays but is no longer proposed. Haiku stays
  retired; nothing sensitive or needing judgement goes below Opus.
- **`medium` is the default effort:** on the benchmarks Opus at `medium` keeps very high intelligence at
  low cost. `high` for very complex work; trivial work goes to Sonnet at `medium` (above).
- **Effort by role, not by phase** (owner, 2026-10-01): "Opus 5.5 is now really powerful even on
  Medium and High, so xHigh is overkill in most cases." In a Tilspire session 12 of 13 agents ran
  at `high`/`xhigh` because the phase was sensitive, and hidden reasoning (output, then re-read every
  turn) was ~30% of 26.5M. Now: `medium` for implementation, plans, tests and fixes even in a
  sensitive phase; `high` only for the agent writing the sensitive code, stubborn debugging and real
  design decisions; every review at `high`; `xhigh` only as a fallback (an executor after `high`
  failed, the final sensitive review when Fable is unavailable). Sonnet at `medium` takes mechanical
  work: suite and gate runs, fact collection, doc updates from given facts, exact-spec changes.
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
