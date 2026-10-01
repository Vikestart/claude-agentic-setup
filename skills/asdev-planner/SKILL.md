---
name: asdev-planner
description: Write, review and close out a planned phase — the implementation_plan.md template, the subagent roster question, the detached plan review, the roadmap/plan/task rules, and the phase-completion routine (reference docs, walkthrough, changelog). Use when a change is large or risky enough for the Planning Gate, when writing or revising .docs/implementation_plan.md, when promoting roadmap work into a plan, or when a planned phase is complete. Not for small or medium changes that need no plan, and not for a handover (that is the asdev-handover skill).
---

# Planning

CLAUDE.md §1 holds the gate itself: when a plan is required, that you halt for approval, and what an
approval covers. This skill is how to do the work around it.

## When a plan is needed

- **Large or risky** work (CLAUDE.md §0): always.
- **Medium** work: only when the project's convention or the value of a handoff warrants it.
- **Never** for a small fix that strictly tightens a boundary — that is done directly and reported.
- If a plan is already active and the new work is not part of its phase, it goes to the roadmap.

## Working documents (`.docs/`)

| File | Holds |
|---|---|
| `roadmap.md` | Future outcomes, their order and dependencies — never tasks or implementation detail. Always exists, even if it only says it is empty. |
| `implementation_plan.md` | ONE phase: the active one, or the ready-next one. |
| `task.md` | That phase's tasks, and only those. |

While a plan is active, future work goes to the roadmap. **Promote, never duplicate:** when a
roadmap item becomes the next phase, move it into the plan and delete it from the roadmap. With no
plan active, a ready phase may go straight into `implementation_plan.md`.

## Writing the plan

Size the plan to the phase — a short phase gets a short plan. Don't restate CLAUDE.md; state what is
specific to this work.

```markdown
# Implementation plan — <phase name>

**Goal:** <the outcome, and why it matters, in one or two sentences>

**Decided:** <choices already made with the owner, dated>

## Scope
- In: …
- Out: … (→ roadmap, if it is still wanted)

## Steps
1. <what changes, in which files>

## Verification
- <check> — <what it proves>. Expected values derived from the source of truth, never hardcoded.
- Every new behaviour guard falsified (`falsify.py`; an advisory check needs only a unit test), its mutations kept as a file (`scripts/falsify/<phase>.json`
  where the project has that folder) so a reviewer re-runs every proof in one command.
- Gate: `audit_all.py --changed`, or `--since main` for release scope.

## Subagents
None — <why one writer is right> | a table: role · agent definition · exact model release · files owned · checks it runs

## Release
local → staging → production (or which stage is excluded, and why)

## Residual risks
- <risk> — <what it costs if it happens>

## Open decisions
- <question for the owner, with a recommended answer>
```

## The roster question

Put the roster to the owner in chat **as its own question**, separate from pointing at the plan:

- one line per agent: the definition (e.g. `opus-medium-executor`), the exact model release with
  its version (e.g. Opus 5.5), its task and the files it owns;
- for a large phase, how many fresh continuation or correction agents it expects (only the
  10-at-once cap applies, not a total; the `asdev-orchestrator` skill has the rule);
- or "No subagents", with the one-line reason.

Approving the roster IS the owner's request to spawn it; they may override roster, models, effort or
parallelism. If any agent would inherit the session's effort (a built-in type rather than a
definition) and the work is sensitive, check the session's effort first — below `high`, say so and wait.

## Plan review — only for an intricate, sensitive or complex plan

Most plans skip this, however long. For one that qualifies, spawn a detached reviewer:
`opus-high-reviewer`, sensitive work included. This is a standing
request from the owner; no separate ask.

- **Give it** the plan's path and its goal, plus the output of any mechanical sweep you ran first
  (callers of what changes, files that match a pattern). **Never** your reasoning or the conversation.
- **Ask it to find:** a legitimate user flow the plan would break; a gap in verification (a claim
  with no check, or a check that cannot fail); an irreversible step with no backup or rollback; a
  step whose order is wrong.
- **Then:** fix what holds up; for anything you reject, say why with evidence. Tell the owner in two
  to four lines what it found and what changed.

## Presenting the plan

Point to the file in a sentence or two — don't summarize it in chat — ask the roster question, then
halt until the owner approves. Approval covers every listed phase and the full local → staging →
production path unless the plan or the owner excludes one; don't re-ask at routine transitions.

## During the phase

- Track tasks in `task.md`.
- If the scope changes materially, update the plan and ask again.
- Anything discovered for later goes to the roadmap, not into the running phase.

## Completing a phase

1. **Verify** against the plan's verification section — evidence, not claims.
2. **Reference docs:** record durable architecture, decisions *with their reason*, invariants and
   caveats in `.docs/reference/`, in the file that owns the subject. Correct or remove only what has
   gone stale. Generated files (`platform-manifest.md`, dated audit reports) are rewritten by the
   tool that owns them, never by hand. If this touches the project's `CLAUDE.md` / `AGENTS.md`, keep it within the size budget in the `asdev-conventions` skill.
3. **Clear** the phase from `implementation_plan.md` and its tasks from `task.md`. If the approved
   plan listed another phase, promote it; otherwise the plan says no plan is active.
4. **`walkthrough.md`:** replace it with this phase only — what was built, how it was verified, and
   where to look.
5. **`changelog.md`:** append one line, `Phase N — …`, linking the reference doc if there is one.
   Near ~100 lines or at a major release or year boundary, rotate the oldest block into a dated
   reference archive. Never delete release or audit history.
6. **Trim.** Run `python $HOME/.claude/skills/asdev-web-audit/scripts/doc_hygiene.py`
   from the project root and fix every `OVER_BUDGET` line before carrying on — each names the file,
   its budget and how to trim it. Shipped roadmap items are deleted (the changelog keeps the
   history), open follow-ups leave `task.md` for the roadmap as outcomes, detail moves to the plan
   when its item is promoted, the changelog's oldest block rotates into a dated reference archive,
   and occasional detail in `AGENTS.md` moves to `.docs/reference/` behind a one-line pointer. Never
   delete a decision, an open question or unshipped work — move it. If something must stay over
   budget, say why in the walkthrough. Measured 2026-10-01: Tilspire's roadmap had reached 101 kB
   and Nebulingo's changelog 112 kB, read again and again by every agent, although the rules
   above already said to prune them.
7. **Carry on.** No fresh-chat question: the docs just updated are what a compaction falls back
   on (CLAUDE.md §1, "Compaction, not fresh chats"). If a handover raised this project's context
   limit for the phase just finished, clear it: `python $HOME/.claude/skills/asdev-web-audit/scripts/context_override.py status`,
   then `clear` when it reports `temporary` (a deliberate value is never touched). Start the next
   approved phase, if any.
