# Implementation plan — Simplify the setup

**Goal:** stop the rules growing with every incident, and cut what every context re-reads, while
keeping the measured gains. On the 2026-10-01 window the global rules file alone (~4k tokens in
every context, every turn) cost ~3M; tonight added four rules and five lines to each executor.

**Decided (owner, 2026-10-01):** window 330k; the 250k agent hand-back stays; Skill tool kept for
now (revisit under Open decisions); executors work one step at a time with an early stop at ~125k.

## Scope
- In: size budgets for the always-loaded rule files, trimming them to budget, fewer thresholds,
  archiving unused agent definitions, a narrower falsification rule, one measurement command.
- Out: changing what the rules require (security, release, Planning Gate, review) — only where text
  lives and how much of it is loaded. Project-side trims (→ each project's own session).

## Steps
1. **Budgets and "one in, one out".** A test in `install/test_setup.py` holds `CLAUDE.shared.md` to
   12 kB (now 15.7) and each in-house `SKILL.md` to its trimmed size; each agent definition body to
   its trimmed size. Record the rule (a new rule replaces or shortens one) in
   `reference/setup-architecture.md` and "Maintaining the setup" (asdev-web-audit skill).
2. **Trim `CLAUDE.shared.md` to ≤12 kB.** Move evidence and history (measured examples, dated
   anecdotes) to `reference/setup-architecture.md`; keep every rule. A list of each moved or merged
   sentence goes in the walkthrough.
3. **Trim the orchestrator skill to ≤12 kB (now ~17).** "What an agent really costs" and other
   dated measurements move to `reference/`; the skill keeps the rules they justify.
4. **Two thresholds for agents:** the ~250k hand-back (hook) and the ~125k early stop. "~150 tool
   calls or ~2 hours" and "more than ~2 steps over large files" become one sizing rule in the
   orchestrator skill, stated against those two numbers.
5. **Shorter executor definitions.** The eight executors repeat one ~30-line hygiene block; shorten
   it to the rules agents demonstrably need (measured from transcripts: what they actually do
   wrong), same text in each.
6. **Archive unused definitions** (if approved, see Open decisions): `opus-medium-lead`,
   `opus-high-lead` (dormant), `opus-low-executor` (retired) move out of the loaded `agents/` folder
   to `.docs/reference/archive/agents/`; tests and falsify cases that name them follow.
7. **Falsification only for behaviour.** CLAUDE.md §6 and the audit skill: falsify guards that
   protect behaviour (security, data, routing, hooks, installer, tool lists); an advisory check gets
   a unit test only. Existing specs stay.
8. **One measurement command.** `session_cost.py --by-source` (cost per tool, file and attachment)
   and `--agents` (cost per agent type and spawn time), replacing tonight's throwaway scripts.

## Verification
- `install/test_setup.py` incl. the new budget test; budgets read from the files' trimmed sizes at
  the end of step 2–5, never guessed now.
- `install/verify.py --gate .` 16/16; `harness_parity.py` after the CLAUDE change; `self_test.py`
  with tests for the two `session_cost.py` options.
- Falsify the budget test and the tool-list test after step 6 (they protect behaviour).
- Before/after: `CLAUDE.shared.md` and agent start-up tokens, from the next sessions' transcripts.

## Subagents
| Role | Definition | Model | Owns | Runs |
|---|---|---|---|---|
| Final review | `opus-high-reviewer` | Opus 5.5 | nothing (read-only) | checks every moved rule still exists somewhere it is loaded when needed, and no requirement was dropped |

Writing stays with one writer: what to cut is judgement across files that must stay consistent.

## Release
`main` of the setup repo (no staging), `install.py`, then a paste-ready note for running chats.

## Residual risks
- A trimmed rule mattered — mitigated: text moves to `reference/`, never deleted; the review checks
  each move.
- Budgets that are too tight push useful rules into skills nobody loads — the budget test names the
  file, and the owner can raise a budget.

## Open decisions
- **Archive the three unused definitions?** Recommended: yes (they cost nothing per turn, but every
  orchestrator reads them listed; the files stay in the archive).
- **Skill tool:** drop it from every agent and add a three-line browser note to executors (~4.8M on
  the measured window), or keep (owner's call tonight). Recommended: drop — 358 of 400 agent runs
  never browsed, and the browser tools work without the skill.
