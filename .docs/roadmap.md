# Roadmap — `~/.claude` global setup

Outcomes and order only; active work goes in `implementation_plan.md` when a phase is ready.

## Next, in order (queued 2026-09-30)

1. **Self-started fresh sessions** (owner request 2026-09-30) — waiting on the vendor. Found
   2026-09-30: `start_session` / `hand_off_to_session` are behind a server-side rollout gate in the
   app (→ `reference/traps.md`, Config and permissions). No setting or version enables them, and
   the gate is not ours to override. Done meanwhile: the handover skill's Finish step hands off by
   itself once the tool appears. Outside git repositories it offers a one-click `spawn_task` chip
   instead. In a repo the paste-ready block stays. **Workarounds tried and rolled back
   2026-09-30** (owner decision; → `reference/traps.md`, "A cleared session wakes only on a
   message"): a relay session that sends the kickoff after the old session clears itself worked end
   to end, but the next handover stops on an app prompt (Remote Control that Claude turned on cannot
   be turned off silently), and the owner wants no extra sessions. A detached script or headless
   `claude -p` sending the kickoff was refused by auto mode as an unsafe agent — not to be retried.
   Also ruled out: hooks and `CronCreate` after a clear, scheduled tasks and Dispatch (unattended),
   deep links (only fill the prompt box), cloud sessions (no local XAMPP). Only lead left if ever
   revisited: whether the app's Remote Control default reconnects a cleared session by itself.

2. **Build the scripts the mining justifies** — `automation_mine.py` exists (2026-09-30); its
   September ranking, by tokens the model wrote:
   - ~~`patch.py`~~ — built 2026-09-30 (~4,300 runs, ~2.4M tokens, ~120 failures in September);
     CLAUDE.md §0 points at it. Rerun the miner in a few weeks to see the habit actually moved
     (`automation_mine.py --since <date>`; September's figures above are the baseline).
   - ~~falsify mutations without a hand-written JSON file~~ — built 2026-09-30: `--mutations` takes
     `patch.py`'s unescaped block spec with `name:` / `expect:` lines. Baseline: 138 runs built the
     JSON; "inline python → falsify.py" was the most common command sequence (96 transcripts).
   - **Nebulingo's test-database preamble** (`PHASE98_TEST_*` exports, 171 runs) — a project
     script, for that project's own roadmap.
   - Smaller: JSON config writes (~100 runs), a `git diff --numstat` check (~200 runs). Rerun the
     miner after `patch.py` lands; fold in "Generalise the suite helpers" below if it ranks them.

## Later

- **Commit the AGENTS.md scanner-path fix** — done in the working tree 2026-09-30: xampp-pulse
  (on `main`) and tilspire-com (on `staging`) now point at the global audit rule instead of a
  retired path. Each project's next session commits it with its other pending edits.
- **Re-measure after the context rules** (from 2026-09-30) — once each of Nebulingo, Framvis and Tilspire has run two or three phases under the new rules, compare with `agent_audit.py` (peak context, gap re-caches, weighted total) against the 2026-09-30 figures (`reference/setup-architecture.md`, "Evidence behind the rules"); adjust the ~250k ceiling and the ~150-tool-call split if they miss. Also record each main session's
  context growth per phase. If it is still ~100k under the new rules, revisit phase leads (built and
  rolled back 2026-09-30, `reference/setup-architecture.md`). Also judge compaction instead of fresh chats (2026-09-30): do compacted
  sessions lose decisions or repeat work after a compaction? If so, tighten the summary rule.
  Leaner agents (2026-10-01): run `session_cost.py` on the next two Nebulingo/Tilspire nights against
  the 2026-10-01 night baseline (Tilspire 38.8M for 2 phases + review + plan; Nebulingo 24.3M for
  phase 221; agents' fixed share 23–32%, start-up 52–58k) — start-up should sit near 27k; check agents use `code_map.py` /
  `code_show.py` on big files (else firmer wording in the definitions) and whether any agent reports
  a dropped tool it needed.
  Measured 2026-10-01 (afternoon): Tilspire 26.5M, main chat 11%, agents start ~40k, hidden
  reasoning ~30%; Nebulingo ~23.6M (output a floor), main chat **43%** — 326 turns at ~225k doing
  its own dumps, greps, fixes and checks. Next measurement should show (a) effort by role cutting
  agent cost, (b) the Trim step shrinking Tilspire's and Nebulingo's working files, (c) whether
  Nebulingo's main chat still does hands-on work; if so, tighten the orchestrator rule for the main
  session (delegate verification and small fixes to `sonnet-medium-executor` / `opus-medium-executor`).
  Measured 2026-10-01 (evening; sessions 13:07–20:13, effort by role from 17:50, so mixed):
  (a) both sessions switched to medium/Sonnet agents mid-session, but per-agent cost did not
  fall — Tilspire medium 2.17M avg vs high 1.97M, Nebulingo 1.30M vs 1.57M (different tasks;
  cost follows turns × context, not effort). Sonnet falsify/gate run: 0.29M. (b) Trim step landed
  after both sessions: untested; both projects still over budget (Nebulingo changelog 109 kB,
  task 69 kB; Tilspire roadmap 99 kB, plan 46 kB). (c) Nebulingo main chat still hands-on: 44%,
  352 turns at avg 233k, 49 edits to code and tests → orchestrator rule tightened the same day.
  Next: one more night each — check (b), whether Nebulingo's main share drops, and Tilspire's
  reviewers (still `opus-xhigh-reviewer` before 17:50; should be `opus-high-reviewer`).
- **Spend levers, measured 2026-10-01 night** (4 Nebulingo/Tilspire sessions since 09-30 evening,
  ~156M; method: price every token by its write plus later re-reads). Applied 2026-10-01:
  PowerShell off every agent, web tools off the common ones (~2.4M est.); a 6 kB memory-index
  budget; reference files over 60 kB flagged (advisory, split on next edit; archive/ exempt).
  Window 400k → 330k (agents obey it too, so it stays ~50k above their 250k ceiling); executors
  work one step at a time and stop at ~125k with nothing written; large briefs split up front.
  The same night's simplification (owner) dropped the Skill tool from every agent (its listing,
  6.7k per agent request, ~4.8M) in favour of a short browser note in each definition, archived the
  phase leads and `opus-low-executor`, and gave the rule files size budgets. Open: projects trim
  working files and Nebulingo's AGENTS.md/MEMORY.md; next measurement checks all of the above, and
  whether any agent missed a skill.
  Not worth it: cache misses 1.6M (owner breaks), repeated identical calls (11).
- **Mods experiment** (Claude Code 2.1.287+; checked 2026-10-01, the CLI is on it but the desktop
  app still bundles 2.1.284, so start once the app updates). A mod is a plugin whose hooks are a JS
  module, loaded once per session. Try: rebuild `context_guard` as a mod (no Python start per tool
  call; it could enforce the ~125k nothing-written stop), and turn two prose rules into enforced
  guards (piped suite runner, heredoc for multi-line content, push to `main` in a project repo,
  whole-file read of a 1,000+ line file → `code_map.py`), then delete them from the rules text. The
  API also has `$.session.compact` (between turns) and `$.session.usage` — a mod could compact at a
  chosen size, or show live spend above the prompt. Each mod must delete a rule or a hook to earn
  its place; tests through `claude plugin test`; the API may change between releases. Its own
  planned phase.
- **Generalise the suite helpers** — Nebulingo's `neighbour_suites.py` / `battery_gate.py` and Tilspire's slice runner into the audit suite with a small per-project config; when a third project needs one.
- **Project follow-ups (unverified since 2026-09-01; belong in each project's own roadmap):** nebulingo — add `.tmp/` and `.docs/proofs/` to `.auditignore` and a `.token-limits.json` for `scripts/` (242 advisory findings → ~80); nebulingo — `includes/lesson_authoring.php` (819 KB, read 309 times by agents) is the costliest file to work near.
