# Walkthrough — compaction instead of fresh chats (2026-09-30)

**What changed.** Sessions keep going without the owner: they never propose a fresh chat or ask for
`/compact`. Automatic compaction (92% of the 400k window) handles their size; the working docs carry
the state across it. The owner can still ask for a handover (another machine, the partner, a break).
Why, and the self-restart routes tried first → `reference/setup-architecture.md` ("Compaction, not
fresh chats") and `reference/traps.md` ("A cleared session wakes only on a message").

**Built**
- `hooks/after_compact.py` — `SessionStart` hook, matcher `compact`, installed through
  `settings/shared-settings.json`. Names the `.docs/` working files in the session folder and tells
  the session they beat the summary; a general reminder where the folder has no `.docs/`.
- `CLAUDE.shared.md` §1 — "Compaction, not fresh chats" replaces the handover-proposal rule, plus a
  "When compacting" line telling the summary what to keep. `~/.codex/AGENTS.md` regenerated.
- `hooks/context_guard.py` — main-chat notices removed (250k handover, 400k `/compact`); the
  subagent hand-back notice is unchanged.
- Skills: `asdev-handover` runs only on the owner's request, and its step 4b override is now also
  cleared by the phase-completion routine (`asdev-planner` step 6), since handovers are rare;
  `asdev-orchestrator`'s ceiling note updated.
- `.gitignore` lets the two new hook files into the repo (the reviewer caught that they were
  ignored, which would have stopped the partner's install).

**Verified**
- `hooks/test_after_compact.py` 8/8, `hooks/test_context_guard.py` 8/8; both run in
  `install/verify.py --gate .` (passes, 0 blocking).
- Falsified 4/4: `python skills/asdev-web-audit/scripts/falsify.py --suite "python hooks/test_after_compact.py" --mutations skills/asdev-web-audit/scripts/falsify/compact-hook.spec`
- Live in the desktop app: a probe session with a 100k window compacted three times and got the
  hook's notice each time, then re-read its plan. The summary kept task and state and dropped file
  contents — consistent with the new rule, though a toy session cannot prove the rule caused it.
- Detached review (`opus-high-reviewer`): four findings, all fixed (ignored hook files, an override
  outliving its phase, a stale reference line, silence for htdocs-root sessions).

**Not verified:** how well the summary rule holds up in a long real phase — the roadmap's re-measure
item covers it.
