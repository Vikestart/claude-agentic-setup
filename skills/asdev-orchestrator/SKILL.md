---
name: asdev-orchestrator
description: How to run subagents and reviews in the owner's setup — the agent definitions and what each is for, how to put a roster to the owner, spawn mechanics and effort checks, briefs, file ownership, supervision, verifying agent reports, and which reviewer runs when (including the one end-of-work Fable review). Read it before spawning any subagent, proposing a roster, or starting a detached review — including the detached review that ends sensitive work done directly.
---

# Orchestration

CLAUDE.md §6 holds the rules that always apply: work directly by default, get the owner's request
before delegating, the effort floor and ceiling, the 10-agent cap, falsification, and the meaning of
"sensitive". This skill is how to carry them out once agents or reviews are involved.

**You are the orchestrator.** Synthesis, scope, integration and release stay with you. Use the
smallest useful roster, and give each agent concrete work that can be checked on its own.

## Is it worth an agent?

Work directly unless the pieces need independent judgement or real parallelism: unrelated
subsystems, an exploratory read too wide for one pass, concurrent workstreams. One kind of change
across many files is still direct, and a mechanical sweep is a script (31 path fixes across 17 files:
exact, re-runnable, nothing to verify). Measured over 271 runs with `agent_audit.py`, an agent costs
~50k tokens to cold-start (~27k since the definitions carry explicit tool lists, 2026-10-01) and a median ~285k of fresh input before it can work, plus a ~1,250-token
brief, its result and your verification. Never spawn one for a single small task, at any effort —
the one exception is a significant sensitive change in a session below the effort floor.

## The agent definitions (`~/.claude/agents/`)

Effort comes from the definition, never from the Agent tool: the tool takes no effort, so a built-in
agent type inherits the session's (a roster approved at `max` and `medium` once spawned five agents,
all at `high`). Each definition fixes model and effort together.

| Definition | Use it for |
|---|---|
| `sonnet-medium-executor` | Mechanical work: running suites, gates and falsify batches and reporting the result; collecting facts (grep sweeps, inventories, screenshots across viewports); doc updates from facts you hand it (walkthrough, changelog, reference lines); changes from an exact spec. Never sensitive code, never judgement. Replaces `opus-low-executor` (2026-10-01; that file stays, unused). |
| `opus-medium-executor` | **The default executor:** implementation, discovery, writing plans, writing tests, fix rounds — inside a sensitive phase too, for everything but the sensitive code itself. |
| `opus-high-executor` | Writing significant sensitive code (auth, payments, deletion, schema, the machine API and integrations); debugging that resisted a `medium` attempt; a real design decision. |
| `opus-xhigh-executor` | Only after `opus-high-executor` has failed at the same work. |
| `fable-xhigh-executor` | Sensitive work that resists `opus-xhigh-executor`, or a genuinely novel sensitive design. |
| `opus-high-reviewer` | **Every review:** plan attacks, detached reviews between rounds and phases, the end of a sensitive, high-impact or cross-cutting wave. |
| `opus-xhigh-reviewer` | Only the final pre-release review of sensitive material, when Fable is unavailable. |
| `fable-xhigh-reviewer` | The one final review of sensitive material (see Reviews). |
| `opus-max-executor`, `opus-max-reviewer`, `fable-max-executor`, `fable-max-reviewer` | **Only when the owner names them.** `max` spent more than twice the tokens of `xhigh` for next to no gain (September 2026). |

**Models:** Opus for every executor except mechanical work, which goes to `sonnet-medium-executor`;
Fable only for the final sensitive review or the top of the escalation ladder. Nothing that needs
judgement runs below Opus, not even high-volume fan-out — volume is not triviality.

**Effort by role, not by phase** (owner, 2026-10-01). A sensitive phase used to put every agent at
`high` and every review at `xhigh`; in one Tilspire session that was 12 of 13 agents, and hidden
reasoning — output, then re-read on every later turn — was ~30% of the 26.5M spent. Opus 5.5 is
strong at `medium` and `high`. So the floor binds only the agent writing the sensitive code; its
planner, test writer, doc updates and fix rounds for non-sensitive findings run at `medium`, and
reviews at `high`.

## What an agent really costs

**Cost ≈ context size × turns, plus a full re-cache after every pause longer than the cache
lives.** Each turn re-reads the whole context from cache, so a long thread gets more expensive with
every step. An agent that pauses past its cache's lifetime — on a suite, a falsify run, or a resume
by message — writes its entire context again at the cache-write price.

**Cache lifetime:** by default subagents cache for **5 minutes**, the main chat for an hour.
Since 2026-09-30 `settings.json` sets `"subagentPromptCacheTtl": "1h"`: in 200 agent runs, 61% of
all agent cache writes (119M of 194M) came straight after a pause over 5 minutes, and the 1-hour
cache turns most of those into cheap reads, at 2× the input price per write instead of 1.25×. The
setting is ignored while the subscription is in overage — then agents are back to 5 minutes.

Measured 2026-09-30 (price-weighted: cache read 0.1, cache write 2, output 5):

- **Nebulingo:** one builder, 533 turns at an average 523k context, cost 31M of the session's 44M;
  ~90% of it was re-reading its own history. Its output and reasoning were ~0.1M.
- **Tilspire:** one builder, 265 steps growing to ~720k, cost 41M of 61.5M — ~30M of it cache
  writes during multi-minute waits (before the 1-hour agent cache). It had been resumed from the planning agent, so it started large.
- **Framvis:** main chats were ~72% of 292M. One ran 904 turns at an average 464k; its own file
  reads, gate runs and diffs, not the agents' reports, filled it. Builders cost 2–5M per phase.

Effort mainly moves the *output* share — ~65% of a session's output is reasoning, ~29% tool-call
JSON, ~6% prose (method in `~/.claude/.docs/reference/setup-architecture.md`) — so it still matters, but a
small, short-lived context matters more. The rules below keep it small.

## Keeping contexts small

- **One role per agent.** Planner, plan attacker and builder are separate fresh agents. A builder
  gets the plan's path and a compact brief, never the planner's thread.
- **Split long builds.** A build expected to exceed ~150 tool calls or ~2 hours runs as 2–3
  sequential builders with disjoint files, each starting from the previous one's hand-back. Split
  up front, too, when a brief spans more than ~2 steps across large files (over ~1,000 lines): a
  Nebulingo brief of six steps over ~13 such files used a whole agent on reading (2026-10-01).
- **Context ceiling ~250k.** An agent past it finishes its current step and hands back what is
  done, what is left, and the exact next step (the context hook tells it when). Start a fresh agent
  for the rest from that hand-back. The main session has no ceiling to report: `autoCompactWindow`
  compacts it at ~300k of 330k (~33k below the window; a session already running ignores the
  setting, `traps.md`), and `after_compact.py` points it back at its docs (CLAUDE.md §1). Agents
  obey the same window, so one that runs ~50k past its ceiling compacts mid-step: hand back at
  the notice instead.
- **Approval covers the continuations.** An approved roster covers fresh continuation and
  correction agents for its roles (same definition, same files); say one line when you start one.
  They count toward the 10-agent cap, so a roster for a large phase states how many it expects,
  and you ask before one would pass 10.
- **Corrections are fresh agents,** briefed with only the findings and the relevant diff — unless the
  fix is small enough to make and verify at a glance, which you make yourself. Resume an
  agent by message only for a tiny clarification, while its context is under ~150k and before its
  cache expires (an hour; 5 minutes in overage) — otherwise the resume re-caches everything it holds.
- **Keep an agent's waits short.** Agents run slices of a suite where the project has them; a full
  battery or long falsify run that could outlast the cache — anything near an hour, or over 5
  minutes in overage — is yours or a small fresh agent's, never a large builder's.
- **A long run is started once, then the turn ends.** Whoever runs it — you or an agent — starts it
  in the background and ends the turn; the completion notification wakes them. Never a wait, sleep
  or polling loop: each wake re-reads the whole context for nothing (a ~220k Tilspire builder woke
  every ~10 minutes through a 14-run falsify batch). Only a background agent — the default — is
  woken. A foreground agent's end of turn is its final report and kills its background commands,
  so never spawn one for a long run.
- **In a planned phase you stay the orchestrator.** Long build/test loops and large writes go to a
  builder in the approved roster, not into your thread. Write the brief from the plan and the
  reference docs — reading the code first means it is read twice. Code and test edits beyond a
  glance-sized correction go to a fresh `opus-medium-executor`; suite, gate and falsify runs, and
  sweeps that collect facts, go to `sonnet-medium-executor`. Your own checks stay small: the diff
  stat, one targeted read, the summary line of a run. Everything you read stays in a context that
  is re-read every turn — at ~230k, each added turn costs about what a small agent's whole start
  does (Nebulingo 2026-10-01: the main chat edited code and tests itself, 44% of the session).
  Outside a plan, "directly by default" still governs.

## Proposing a roster

- Outside a plan, when work clears the bar, ask once in one line: "this splits into 3 independent
  pieces — spawn 3?" At the Planning Gate the roster is part of the plan's approval.
- Name each agent's definition and the **exact model release, version included** (e.g. Opus 5.5),
  so the owner can see whether a `.1` has landed.
- Approving a roster IS the request to spawn it. The owner may override any model, effort or
  parallelism, even below the effort floor: apply it and say once what it changes.

## Spawning

- **Never pass a `model` override** to a definition; the name would then lie about the model.
- Each definition opens its result with the model and effort it ran at — check that line against
  the roster.
- **A `fork`** inherits the session's model, effort and whole conversation, so it never serves as a
  detached review and never satisfies an effort rule.
- **A session opened before a definition existed** may not be offered it, and still runs the old CLAUDE.md
  (on 2026-09-30 one running session was offered two new definitions; `traps.md`). Where the Agent
  tool does not offer the definition, spawn `general-purpose` (executor) or `Plan` (reviewer; no edit or spawn tools) with the
  definition's model and its rules in the brief. Both inherit the session's effort.
- **Wherever effort is inherited rather than set**, the floor is a precondition: before spawning for
  sensitive work, check the session's effort; below `high`, say so and wait — only the owner can
  change it in the app.

## Splitting the work

- **By domain, with a disjoint file list each.** Prefer one writer; parallelize only disjoint work
  with a real integration benefit. Shared files, live services and mutable databases stay
  single-writer.
- Where two workstreams reach one file, name an owner; the other **reports the change and you apply
  it**. A conflict found at merge time is worse than a slower brief.
- **The 10-agent cap counts in total** per task, phase or workflow run, workflow agents included;
  a queue, batching or ultracode does not lift it. `settings.json` enforces part of it
  (`CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS=10` refuses an eleventh concurrent spawn,
  `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH=1` stops subagents spawning their own). Nothing caps a
  workflow's total, and an approved wave above 10 at once also needs that setting raised first.
- **Never run suites that share a disposable database concurrently** — two agents resetting one
  instance corrupt both runs and produce failures that look like real regressions.

## The brief

A compact handoff: objective and acceptance criteria, mandatory pre-reading (the repo's reference
docs), database and environment constraints, files owned vs forbidden, invariants, "do not commit",
and the verification to run and quote.

- **Hand over what you already know** — exact paths, line numbers, excerpts, a diff or a hash —
  rather than setting a search: agents made 2.7× the primary's tool calls, re-finding what you had.
- **A reference several agents need is read ONCE by you** and excerpted into each brief (73% of
  agent reads repeated another agent's).
- **Paste the plan section and task lines the agent needs** into the brief; point at
  `implementation_plan.md` only when it needs the whole plan. Agents re-read the plan 20–39 times a
  night (2026-10-01), each copy staying in context for the rest of their run.
- **For large files, hand over names, not ranges:** the function, test or plan-section names the agent needs, and
  the instruction to use `code_map.py` / `code_show.py` (audit suite) rather than `sed` slices —
  file dumps were 39–47% of what agents read (2026-10-01).
- **Always include:** the project's quiet runner by name (or `quiet.py` from the audit suite), the
  context ceiling, a report cap (executors ~900 words, reviewers ~1,200), and for any run
  longer than a few minutes "start it in the background and end your turn" — never "keep working"
  unless the brief names the independent work to do meanwhile.
- Subagents inherit your authority, never spawn further agents, and return a concise result,
  blocker or correction request.

## While they work

- Supervise event by event, never by polling.
- A correction goes to a fresh agent (see "Keeping contexts small"), not a resumed one.

## Verifying what comes back

- **Don't trust the report.** Agents have reported vacuous assertions, order-dependence that did not
  exist, and clean audits that were not. Recheck the load-bearing claims against the code and the
  live system.
- **That includes an agent's account of its own effort,** which it cannot see — it guesses from its
  prompt (every agent in one session reported "low", "10" or "15" while running at the `medium`,
  `high` or `max` its definition set). Read model and effort from the transcript:
  `agent_audit.py --agent <id>` (in the `asdev-web-audit` suite).
- **Verify with the cheapest evidence that settles the claim:** `git diff --stat`, the gate's one
  summary line (output to a log, last line read back), and the load-bearing changed lines read in
  slices. Never whole files or full logs; anything deeper goes to a fresh reviewer returning a short
  verdict. Every file you read stays in your context for the rest of the session.
- **After a planned phase with agents,** record its agent spend in the walkthrough from
  `agent_audit.py` (turns, peak context, price-weighted total), so drift shows up.
- Checkpoints never replace final verification: recheck the actual diff and evidence yourself, and
  ask the owner only about material decisions or blockers.
- **You own** the `APP_VERSION`/`CACHE_NAME` bump, the commit, the docs, and any cross-cutting fix
  an agent reported but did not own.

## Reviews

- **Small work:** check it yourself.
- **Challenging work:** `opus-high-reviewer`.
- **Sensitive, high-impact or cross-cutting waves** end with a **detached review**: a fresh
  read-only agent given only the commits and the claimed properties, never your reasoning, told to
  break the claims and above all to find a legitimate user flow the change breaks — that is where the
  most valuable defects have been. Use `opus-high-reviewer`, including between rounds or phases.
- **Fable, for sensitive material only:** one `fable-xhigh-reviewer` review, **after all planned work
  is built and before production release** — never between rounds. Fall back to
  `opus-xhigh-reviewer` when Fable is unavailable. The trigger for reviewing at all is deliberately broader than Fable's, or Fable would
  become the default.
- **Run the mechanical sweeps first and give the reviewer their output:** one detached review cost
  829k fresh tokens for four findings while missing a whole class a grep then found in seconds.
- Act on the findings; if one is wrong, say so with evidence.
- Plan reviews are covered by the `asdev-planner` skill.
