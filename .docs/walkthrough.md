# Walkthrough — leaner agents (2026-10-01)

**Why.** `session_cost.py` on the night of 2026-09-30/10-01 (Nebulingo + Tilspire, 29 agents, ~55M
price-weighted) put 23–32% of agent cost in start-up context (mostly tool definitions, re-read every
turn) and 37–45% in growth, of which file dumps were 39–47% and ranged reads 19–26% of the
tool-result cost — in 10–27k-line files.

**What changed.**
- **Tool lists.** Every executor and reviewer definition carries an explicit `tools:` list instead of
  inheriting everything (reviewers: no Edit/Write). Start-up context in the CLI: 46.3k with all
  tools → 26.8k executor, 26.0k reviewer. Rationale and the kept/dropped groups:
  [`reference/setup-architecture.md`](reference/setup-architecture.md). Enforced by
  `install/test_setup.py`, falsified by `falsify/agent-tools.spec` (5/5).
- **Code navigation.** `code_map.py` (outline with line ranges, check names on test blocks) and
  `code_show.py` (print named items, several per call) in the audit suite; the definitions and the
  orchestrator's brief guidance point agents at them for files over ~1,000 lines. 68 fixture tests,
  `falsify/code-nav.spec` 11/11; run.php maps in 0.7 s, lesson_authoring.php in 0.4 s.
- **Briefs carry the plan section** an agent needs (`asdev-orchestrator`, "The brief").
- **Also this phase, at the owner's request:**
  - `sonnet-medium-executor` takes trivial work instead of `opus-low-executor` (file kept);
    `.gitignore` admits `agents/sonnet-*.md`.
  - Codex decoupled: `~/.codex/AGENTS.md` is no longer generated or checked
    (`sync_agents_md.py` kept for its import expander).
  - `after_compact.py` restores the session's last message before a compaction, verbatim
    (`falsify/compact-reply.spec` 5/5).
- **Found on the way:** `a11y_audit.py` read a PHP heredoc opener `<<<HTML` as an `<html>` tag
  (regression test in `self_test.py`, `falsify/heredoc-lang.spec`); a Python rewrite turned agent
  definitions into CRLF, which hid them from the CLI (`reference/traps.md`).

**Verified.**
- Gate: `install/verify.py --gate .` 16/16; `install.py --check` in place.
- Probes from the CLI (fresh definitions): opus-medium-executor 26.8k, sonnet-medium-executor 26.8k
  on Sonnet 5.5. A fresh executor asked to find one check in `run.php` answered in 3 turns,
  26.9k → 32k context, with one grep and a 9-line read — no dumps.
- Detached review: `opus-high-reviewer`.

**Agent spend.** Builder (`opus-medium-executor`, Opus 5.5 medium): 42 turns, peak 160k, avg 126k,
~0.83M price-weighted.

**Baseline for the re-measure** (roadmap): 2026-10-01 night — Tilspire 38.8M for 2 phases + review +
plan; Nebulingo 24.3M for phase 221; agents' fixed share 23–32%, start-up 52–58k. The next two nights
measured with `session_cost.py --project … --since …` should show start-up near 27k and a smaller
dump share. Running sessions keep the old definitions until restarted.
