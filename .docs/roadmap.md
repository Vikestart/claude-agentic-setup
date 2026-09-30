# Roadmap — `~/.claude` global setup

Outcomes and order only; active work goes in `implementation_plan.md` when a phase is ready.

## Next, in order (queued 2026-09-30)

1. **Self-started fresh sessions** (owner request 2026-09-30) — a session that hits the handover
   point writes the handover and continues in a fresh session itself, without the owner starting
   one. Found 2026-09-30: the app's session tools refer to `start_session` and `hand_off_to_session`,
   but neither is offered in this session (find out what enables them — app version, a setting or a
   rollout). What is offered today: `clear_session("self")` empties the context once the turn ends
   but then waits idle for the owner's next message; `send_message` reaches only sessions that
   already exist; a one-time scheduled task (`fireAt`) starts a fresh unattended session with a
   prompt, but each one is a stored task file, it runs only while the app is open, and unattended
   sessions cannot message back. Outcome: the handover skill ends by starting the successor itself,
   with the paste-ready message as its first prompt. Also found 2026-09-30: `clear_session` is
   refused for a session serving Remote Control, and every session here has Remote Control on;
   `get_usage` (session tools) reads any running session's context size; the newer `SendMessage`
   tool supersedes `send_message`. Check `ToolSearch` for `start_session` first — the app updates.

2. **Build the scripts the mining justifies** — `automation_mine.py` exists (2026-09-30); its
   September ranking, by tokens the model wrote:
   - ~~`patch.py`~~ — built 2026-09-30 (~4,300 runs, ~2.4M tokens, ~120 failures in September);
     CLAUDE.md §0 points at it. Rerun the miner in a few weeks to see the habit actually moved
     (`automation_mine.py --since <date>`; September's figures above are the baseline).
   - **falsify mutations without a hand-written JSON file** — 138 runs build one; "inline python →
     falsify.py" is the most common command sequence (96 transcripts).
   - **Nebulingo's test-database preamble** (`PHASE98_TEST_*` exports, 171 runs) — a project
     script, for that project's own roadmap.
   - Smaller: JSON config writes (~100 runs), a `git diff --numstat` check (~200 runs). Rerun the
     miner after `patch.py` lands; fold in "Generalise the suite helpers" below if it ranks them.

## Later


- **Project AGENTS.md files stop repeating the scanner path** — xampp-pulse and tilspire-com (both had uncommitted AGENTS.md edits on 2026-09-29). xampp-pulse still points at the retired `~/.codex/skills/web-audit` copy: replace the path with a pointer to the global audit rule, at each project's next session.
- **Re-measure after the context rules** (from 2026-09-30) — once each of Nebulingo, Framvis and Tilspire has run two or three phases under the new rules, compare with `agent_audit.py` (peak context, gap re-caches, weighted total) against the 2026-09-30 figures in the orchestrator skill; adjust the ~250k ceiling and the ~150-tool-call split if they miss.
- **Generalise the suite helpers** — Nebulingo's `neighbour_suites.py` / `battery_gate.py` and Tilspire's slice runner into the audit suite with a small per-project config; when a third project needs one.
- **Project follow-ups (unverified since 2026-09-01; belong in each project's own roadmap):** nebulingo — add `.tmp/` and `.docs/proofs/` to `.auditignore` and a `.token-limits.json` for `scripts/` (242 advisory findings → ~80); nebulingo — `includes/lesson_authoring.php` (819 KB, read 309 times by agents) is the costliest file to work near.
