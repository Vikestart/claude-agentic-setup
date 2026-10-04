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
  The same night's simplification (owner) archived the phase leads and `opus-low-executor` and
  gave the rule files size budgets; it dropped the Skill tool from agents, which the owner then
  restored (the ~4.8M listing cost is accepted). Open: projects trim
  working files and Nebulingo's AGENTS.md/MEMORY.md; next measurement checks all of the above, and
  whether any agent missed a skill.
  Not worth it: cache misses 1.6M (owner breaks), repeated identical calls (11). A keep-alive mod
  (owner agreed 2026-10-02): suites finish inside the 1h cache; only a real turn renews it, which
  enters the chat; pings beat one rebuild only for breaks under ~20h.
- **Compaction backstop** (from the mods phase, 2026-10-02): once checkpoint compactions prove
  reliable in project sessions, the `autoCompactWindow` backstop may rise from 330k to ~400k (not
  1M: every turn re-reads the whole context, and agents share the window). Unverified: whether
  the mod's compaction instructions reach subagents.
- **From the 2026-10-02 session mining, not built** (the four mods it ranked were, in the mods
  phase): a guard on pushing `main` in a project repo — a release pushes `main` after merging
  `staging`, which a guard cannot tell from a direct push without risking a blocked release.
  Not mods: Nebulingo's `PHASE98_TEST_*` exports and bearer-token reads from `.env` (~400 repeated
  commands) belong in that project's `.claude/settings.local.json` `env` (secrets: owner's call);
  permission prompts the owner was stopped by → the `fewer-permission-prompts` skill. 240 refused
  Edits/Writes ("not read yet", "modified since read") cost a turn each; no mod fix found.
- **CLOSED 2026-10-03 (owner), not built: at 0.05 cache-read weights the largest candidate is ~2%
  of spend and compaction keeps main chats short.** Kept for its measurements, delete on next trim.
  **Start-up trim, from the second 2026-10-02 mining** (67 transcripts since 2026-10-01 18:00,
  109M price units; scripts `mine4.py`, `startup2.py`, scratchpad). Start-up text re-read by every
  request is now **25%** of spend (main chat median 82k at start, agents 35–46k). **Owner decision
  2026-10-02: none of the four for now (avoid over-engineering); re-measure first.** After a few
  project nights with the 150k checkpoints, rerun the mining and revisit only if start-up is still
  ~25%. **First data point:** the Tilspire and Nebulingo night of 2026-10-02 — weekly usage was
  48% when the owner left them running, 49% next morning. Measured 2026-10-03: both stopped by
  themselves (Tilspire's goal done, Nebulingo awaiting a draft approval), not by the expired login;
  ~13.4M after the owner left (Tilspire 9.8M closing Phase 6, main 25%; Nebulingo 3.6M, main 35%).
  All 13 compactions were checkpoint ones, none automatic; Tilspire's main still peaked at 259k.
  Too little night data to judge the trim; next measurement after a full night.
  Day run 2026-10-03 (08:40–20:15 UTC, scratchpad `segments.py`): Tilspire 53.1M (main 26%), Nebulingo
  42.2M (main 38%); 21 checkpoint compactions, none automatic; main peaks 144–194k, one 212k;
  restart at 74–90k; no repeated agent task or commit. Nebulingo's high executors (28, 18M) were
  mostly Phase 225 authority/schema work; ~2M content fixes and lesson reviews. Weekly usage
  49% → 58%: ~10–11M weighted (0.05 weights) per weekly percent, matching the night (1 point). Candidates then:
  1. Main chat tool definitions are 53k: Artifact 15.3k, PowerShell 5.2k, Workflow 2.5k,
     ScheduleWakeup 2.2k, visualize/SendUserFile/SuggestPluginInstall ~4k. Denying the unused
     ones in project sessions saves ~3% of all spend (~10% of the main chat's) — first probe that
     a deny rule removes a definition, not only blocks the call.
  2. The built-in browser's tools (8.7k) load in every agent through the definitions' tool lists:
     ~4%. Keep them only on the agents that check UI (owner's call: it changes what agents can do).
  3. AGENTS.md budget 20 kB → ~12 kB (Nebulingo 20.4 kB, Framvis 16 kB, Tilspire 6 kB): ~1%.
  4. The skill list is 6.9k, the owner's skills ~1k of it; hiding unused built-in and plugin
     skills (if a setting allows; probe) ~1.5%.
  Not worth it: batching lookups (one read-only call per request in 56–87% of agent requests,
  but a sample shows reviewers already chain reads with `;` and most steps follow the last
  result). Healthy since the rules: requests at 300k+ fell 43% → 2.5% of spend, cache misses
  11% → 1.8% (all owner breaks of 1h+), tool errors 1.2%, output 9%. Main chat still spends 40%
  at 200k+; the 150k compaction checkpoints should cut it — re-measure.
- **Output sweep, 2026-10-03** (owner asked; scripts `output_split.py`, `out_by_type.py`, scratchpad):
  output is 23% of spend since 10-01 at Opus 5.5 prices (main 17%, agents 20–30%; the cost tools
  weighted a cache read 0.1 until 2026-10-03, now 0.05, so earlier figures overstate re-reading
  about twice); ~60–65% of output is hidden reasoning,
  which follows turns × effort. Hand-written replace scripts fell from 11% of output to ~3% once
  the heredoc guard landed. Built 2026-10-03 (owner: "both"): `falsify.py --check` / `--only`, and
  the pipe guard exempts `--help`. Nothing else visible worth a script. Effort check (scratchpad
  `effort_check.py`): high executors were the default until effort-by-role (10-01 17:50); since
  then 16 runs, ~14.5M, about a third not sensitive (sweeps, lesson reviews); xhigh reviewers gone;
  high executors' final reports ~1,250 tokens vs medium ~450. **Owner 2026-10-03: leave the rules
  as they are** (no tighter wording, no report cap, sensitive floor kept).
- **Clawd on the usage bar: live check** (built 2026-10-04; owner's pick: all three idle tricks at
  random, M3 vacuum for compaction): still to confirm on the desktop that the absolutely placed
  trick drawing paints over the band (only a browser mock was seen), that the once-a-second redraw
  during compaction does not restart the vacuum animation, and that the trick positions roughly
  meet the meters (they are fixed pixel guesses). While a trick plays (6–12 s) the ✕ under it may
  not take clicks. Added later the same day (owner): four more tricks (dance, juggle, flip, chase;
  never the same twice running), and a red pace arrow and figure when a limit runs ahead of pace.
  The meters' browser tooltips (seen working) became a dark one-line strip over the band on hover
  (owner's pick: plugins cannot raise the app's own tooltip). The first build never showed live (a
  keyed hidden Box can't be hovered); the desktop draws it as its own light card above the band, so
  it is now that card: the meter's name, then one point per line. To confirm: the card reads cleanly
  and the cache ring's grows leftwards; plus the limits read "used / pace" and follow the newest reading.
- **Usage bar A5 + cache ring: live check** (built 2026-10-03; owner saw it live after a restart):
  still to confirm that the heat gradient and arrows draw, the row wraps cleanly when narrow, and the cache ring counts down
  and turns red under 10 min. Known gap: a session in usage overage drops to a 5-minute cache, which
  the engine does not report, so the ring still counts an hour.
- **Generalise the suite helpers** — Nebulingo's `neighbour_suites.py` / `battery_gate.py` and Tilspire's slice runner into the audit suite with a small per-project config; when a third project needs one.
- **Project follow-ups (unverified since 2026-09-01; belong in each project's own roadmap):** nebulingo — add `.tmp/` and `.docs/proofs/` to `.auditignore` and a `.token-limits.json` for `scripts/` (242 advisory findings → ~80); nebulingo — `includes/lesson_authoring.php` (819 KB, read 309 times by agents) is the costliest file to work near.
