# Walkthrough — simplify the setup (2026-10-01)

**Why:** every incident had added a rule, and the always-loaded files are re-read on every turn of
every context. This phase caps their size and removes what agents never used, without dropping a rule.

## What changed

- **Size budgets, "one in, one out".** `install/test_setup.py` (`RuleBudgets`) holds
  `CLAUDE.shared.md` to 12 kB (was 15.7 kB), each in-house `SKILL.md` to its own budget and each
  agent definition to 3 kB. A new rule must replace or shorten one. `CLAUDE.shared.md` sits at
  12,285 of 12,288 bytes, so the next addition needs a trim first, by design.
- **Evidence moved out of the rules.** Anecdotes and measurements from `CLAUDE.shared.md` and the
  orchestrator skill now live in `reference/setup-architecture.md`, "Evidence behind the rules".
  Skill paths collapsed into one line: skills live at `~/.claude/skills/<name>/SKILL.md`.
- **Orchestrator skill** 17 kB → 10.8 kB, with one sizing rule for briefs against the two agent
  limits (~125k with nothing written: stop; ~250k: hand back).
- **Agents.** All seven executors share one shorter body with a browser note; the five reviewers
  got the same browser note. The Skill tool was dropped from agents, then restored by the
  owner the same night (the skills were worth their ~6.7k listing). Phase leads and `opus-low-executor` moved to
  `reference/archive/agents/`; a test now asserts that no agent keeps the Agent tool.
- **Falsification** is now required only for guards that protect behaviour; an advisory check
  needs a unit test.
- **`session_cost.py`** gained `--agents` (cost per definition) and `--by-source` (cost per tool,
  attachment and file). Images are priced flat (~1.6k tokens) instead of by their base64 length.

## Detached review (opus-high-reviewer) and what was done

- Executors could no longer find `asdev-conventions` without the Skill tool → the skill-path line.
- Reviewers lost the browser skill with no note → note added.
- `--by-source` overpriced screenshots 10–30×, and charged the writing request a re-read → fixed,
  with a test.
- Dropped sentences restored in short form: coined terms explained or dropped; "never keep
  working without named work"; the completion-routine trigger; the fallback-spawn warning that a
  `general-purpose` stand-in runs on the session's model (so it never counts as the Fable review).
- Falsification list now reads "what a user or system relies on: …", so it is not taken as complete.
- Executors: "the brief's runner or `quiet.py`", and "return a correction request" (a subagent
  cannot ask the owner).
- Stale docs fixed (roadmap, `setup-architecture.md`, handover).
- Kept as dropped (owner's call, low value): "the thing before its label", "don't defend a choice
  nobody questioned", "read the pre-reading the brief names".

## Verification

test_setup OK · after_compact 20/20 · context_guard 8/8 · self_test 42 OK · code_nav 78/78 ·
harness_parity OK · install --check in place · verify --gate 16/16 · doc_hygiene clean ·
falsify: agent-tools 10/10, setup-repo 14/14, rule-budgets 2/2, doc-budget 4/4, doc-reference 2/2.

Running sessions keep the old rules and definitions until restarted.
