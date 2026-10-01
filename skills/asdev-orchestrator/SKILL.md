---
name: asdev-orchestrator
description: How to run subagents and reviews in the owner's setup — the agent definitions and what each is for, how to put a roster to the owner, spawn mechanics and effort checks, briefs, file ownership, supervision, verifying agent reports, and which reviewer runs when (including the one end-of-work Fable review). Read it before spawning any subagent, proposing a roster, or starting a detached review — including the detached review that ends sensitive work done directly.
---

# Orchestration

CLAUDE.md §6 holds the rules that always apply (direct by default, the owner's request before
delegating, models, effort, the 10-agent cap, falsification, "sensitive"). This skill is how to
carry them out. The measurements behind these rules are in
`~/.claude/claude-agentic-setup/.docs/reference/setup-architecture.md` ("Evidence behind the rules").

**You are the orchestrator.** Synthesis, scope, integration and release stay with you. Use the
smallest useful roster, and give each agent concrete work that can be checked on its own.

## Is it worth an agent?

Work directly unless the pieces need independent judgement or real parallelism: unrelated
subsystems, an exploratory read too wide for one pass, concurrent workstreams. One kind of change
across many files is still direct, and a mechanical sweep is a script. An agent costs ~40–50k tokens
to start and much more before it can work, plus a brief, its result and your verification. Never
spawn one for a single small task — except a significant sensitive change in a session below the
effort floor.

## The agent definitions (`~/.claude/agents/`)

Effort comes from the definition, never from the Agent tool: a built-in agent type inherits the
session's effort. Each definition fixes model and effort together.

| Definition | Use it for |
|---|---|
| `sonnet-medium-executor` | Mechanical work: suite, gate and falsify runs reported back; fact collection (sweeps, inventories, screenshots); doc updates from facts you hand it; changes from an exact spec. Never sensitive code, never judgement. |
| `opus-medium-executor` | **The default executor:** implementation, discovery, plans, tests, fix rounds — inside a sensitive phase too, for everything but the sensitive code itself. |
| `opus-high-executor` | Significant sensitive code; debugging that resisted a `medium` attempt; a real design decision. |
| `opus-xhigh-executor` | Only after `opus-high-executor` has failed at the same work. |
| `fable-xhigh-executor` | Sensitive work that resists `opus-xhigh-executor`, or a genuinely novel sensitive design. |
| `opus-high-reviewer` | **Every review:** plan attacks, detached reviews between rounds and phases, the end of a sensitive, high-impact or cross-cutting wave. |
| `opus-xhigh-reviewer` | Only the final pre-release review of sensitive material, when Fable is unavailable. |
| `fable-xhigh-reviewer` | The one final review of sensitive material (see Reviews). |
| `opus-max-*`, `fable-max-*` | **Only when the owner names them.** |

Nothing that needs judgement runs below Opus, not even high-volume fan-out — volume is not
triviality. The phase leads and `opus-low-executor` are archived (`.docs/reference/archive/agents/`
in the setup repo).

## Keeping contexts small

Cost ≈ context size × turns, plus a full re-cache after any pause longer than the cache lives (agents
1 hour via `subagentPromptCacheTtl`; 5 minutes while the subscription is in overage).

- **One role per agent.** Planner, plan attacker and builder are separate fresh agents. A builder
  gets the plan's path and a compact brief, never the planner's thread.
- **Size every brief against the two limits:** an executor stops at ~125k with nothing written,
  and hands back at ~250k (the context hook). A brief that will not fit — more than ~2 steps across
  large files (over ~1,000 lines), or roughly 150 tool calls — is split up front into sequential
  builders with disjoint files, each starting from the previous one's hand-back.
- **A hand-back starts a fresh agent** for the rest. Agents obey the main chat's `autoCompactWindow`
  too (compaction ~33k below it, `traps.md`), so the window stays ~50k above their ceiling.
- **Approval covers the continuations.** An approved roster covers fresh continuation and
  correction agents for its roles (same definition, same files); say one line when you start one.
  They count toward the cap, so a roster for a large phase states how many it expects.
- **Corrections are fresh agents,** briefed with only the findings and the relevant diff — unless the
  fix is small enough to make and verify at a glance, which you make yourself. Resume an agent by
  message only for a tiny clarification, under ~150k and before its cache expires.
- **Keep an agent's waits short.** Agents run suite slices; a full battery or long falsify run that
  could outlast the cache is yours or a small fresh agent's, never a large builder's.
- **A long run is started once, then the turn ends;** the completion notification wakes whoever
  started it. Never a wait, sleep or polling loop. Only a background agent (the default) is woken: a
  foreground agent's end of turn kills its background commands, so never spawn one for a long run.
- **In a planned phase you stay the orchestrator.** Write the brief from the plan and the reference
  docs — reading the code first means it is read twice. Code and test edits beyond a glance-sized
  correction go to a fresh `opus-medium-executor`; suite, gate and falsify runs and fact sweeps to
  `sonnet-medium-executor`. Your own checks stay small: the diff stat, one targeted read, a run's
  summary line — at ~230k context, each turn you add costs about a small agent's whole start.
  Outside a plan, "directly by default" still governs.

## Proposing a roster

- Outside a plan, when work clears the bar, ask once in one line: "this splits into 3 independent
  pieces — spawn 3?" At the Planning Gate the roster is part of the plan's approval.
- Name each agent's definition and the **exact model release, version included** (e.g. Opus 5.5).
- Approving a roster IS the request to spawn it. The owner may override any model, effort or
  parallelism, even below the effort floor: apply it and say once what it changes.

## Spawning

- **Never pass a `model` override** to a definition; the name would then lie about the model.
- **A `fork`** inherits the session's model, effort and conversation, so it never serves as a
  detached review and never satisfies an effort rule.
- **A session opened before a definition existed** may not be offered it (`traps.md`). Then spawn
  `general-purpose` (executor) or `Plan` (reviewer) with the definition's rules in the brief; both
  inherit the session's model and effort, so a Sonnet or Fable role then runs on the session's
  model — say so, and never count such a fallback as the final Fable review.
- **Wherever effort is inherited,** check the session's effort before spawning for sensitive work;
  below `high`, say so and wait — only the owner can change it in the app.

## Splitting the work

- **By domain, with a disjoint file list each.** Prefer one writer; parallelize only disjoint work
  with a real integration benefit. Shared files, live services and mutable databases stay
  single-writer. Where two workstreams reach one file, name an owner; the other reports the change
  and you apply it.
- **The 10-agent cap is on agents running at once,** not a total: a long phase may spawn more over
  time without asking. `settings.json` refuses an eleventh concurrent spawn and stops subagents
  spawning; an approved wave above 10 at once needs that setting raised first.
- **Never run suites that share a disposable database concurrently** — two agents resetting one
  instance corrupt both runs and produce failures that look like real regressions.

## The brief

A compact handoff: objective and acceptance criteria, the steps in order, mandatory pre-reading,
database and environment constraints, files owned vs forbidden, invariants, "do not commit", and the
verification to run and quote.

- **Never "keep working"** unless the brief names the independent work to do meanwhile.
- **Hand over what you already know** — exact paths, function names, excerpts, a diff or a hash —
  rather than setting a search. A reference several agents need is read once by you and excerpted.
- **Paste the plan section and task lines the agent needs**; point at `implementation_plan.md` only
  when it needs the whole plan.
- **For large files, hand over names, not ranges,** and the instruction to use `code_map.py` /
  `code_show.py` (audit suite).
- **Always include:** the project's quiet runner (or `quiet.py`), a report cap (executors ~900
  words, reviewers ~1,200), and for any run longer than a few minutes "start it in the background
  and end your turn".

## Verifying what comes back

- **Don't trust the report.** Agents have reported vacuous assertions, order-dependence that did not
  exist, and clean audits that were not. Recheck the load-bearing claims against the code.
- **Including its effort,** which an agent cannot see: read model and effort from the transcript
  with `agent_audit.py --agent <id>` (audit suite).
- **Verify with the cheapest evidence that settles the claim:** `git diff --stat`, the gate's summary
  line, the load-bearing changed lines in slices. Anything deeper goes to a fresh reviewer.
- **After a planned phase with agents,** record its agent spend in the walkthrough
  (`session_cost.py --agents`), so drift shows up.
- **You own** the `APP_VERSION`/`CACHE_NAME` bump, the commit, the docs, and any cross-cutting fix
  an agent reported but did not own. Ask the owner only about material decisions or blockers.

## Reviews

- **Small work:** check it yourself. **Challenging work:** `opus-high-reviewer`.
- **Sensitive, high-impact or cross-cutting waves** end with a **detached review**: a fresh read-only
  `opus-high-reviewer` given only the commits and the claimed properties, never your reasoning, told
  to break the claims and above all to find a legitimate user flow the change breaks.
- **Fable, for sensitive material only:** one `fable-xhigh-reviewer` review, **after all planned work
  is built and before production release** — never between rounds; `opus-xhigh-reviewer` when Fable
  is unavailable.
- **Run the mechanical sweeps first and give the reviewer their output** — a grep finds a whole
  class in seconds that a review can miss.
- Act on the findings; if one is wrong, say so with evidence. Plan reviews are in `asdev-planner`.
