# Tasks — a second brain in each project's `.docs/`

The plan is [implementation_plan.md](implementation_plan.md). Approved by the owner on 2026-11-17, and
reviewed. Nothing is built yet.

- [x] 1. Skill `asdev-brain`
- [x] 2. `brain.py` with `setup`, `migrate` and `check`, and tests, falsified; `doc_hygiene.py` runs `check`
  ⟲ commit and push 1–2
- [x] 3. Migrate this repo, then sort the blueprints and `htdocs`/`xampp` root notes
  - Migrated 11 notes by hash. Kept 3 as they were; rewrote 3 shorter (the live defects left out, as
    `local/` holds them). 4 dropped as covered by CLAUDE.md §6, setup-architecture.md and traps.md.
    `solo-on-own-projects`, astole and the two `xampp` notes became lines in `CLAUDE.personal.md`.
  - The blueprints and `htdocs` folders held only older copies; all three root folders renamed
    `memory.migrated-20261117-154544`. `~/.codex`'s 2 stale notes left alone (no repo, Codex decoupled).
- [x] 4. The mod's SessionStart hook (setup, migrate, index into context): build, then tests and falsify as a separate step
  - `brain.py start` does setup, then migrate, each only when it has work, and returns the index only
    then; `hooks/brain.ts` runs it at startup, resume and /clear, never at a compaction. A refusal is
    told once per device and project; the set-up session's "write notes to `.docs/brain/`" line comes
    back after a compaction. About 0.8 s per start.
- [x] 5. Rule edits: CLAUDE.shared.md, asdev-handover, asdev-planner, asdev-release; `autoDreamEnabled: false`
  - The compaction summary keeps uncommitted brain notes; setup-architecture.md has the decision.
  - Committed 770c917. 5cdb706, on the owner's question about clusters: hubs list `[[name]] — hook`,
    within the index's limits, and split into sub-hubs. `check` holds every hub to those limits and
    fails a line with no hook (tests 42/42, 3 mutations falsified).
  - The falsify run that overlapped another was rerun alone; the shared-journal fix is a chip.
- [ ] 6. Paste-ready instruction for the Nebulingo, Tilspire and Framvis chats; FYI for running chats
  - Given 2026-11-17 with the restart request; waiting for the three chats' judgement passes.
- [ ] Live check after a restart; walkthrough, changelog, completion routine
