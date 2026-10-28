# Tasks — back-port from the work setup

Source: `~/Downloads/personal-setup-backport.md`; extracted blocks in the session scratchpad
(re-extract with a short script if it is gone: each embedded file is a ```` fence after a
`` `path` (N lines): `` label). Work a copy of the mod first, never the live folder.

- [x] 1. Guards merged (work `guards.ts` + our `AUDIT` path and `audit_all/self_test/verify.py`
      runners), tests 38/38, `mod-asdev.spec` 73/73 on a copy (incl. two stale band/trigger anchors fixed).
- [x] 2. Compaction stages: careful nudge from 230k, docs hold from 280k; tests 40/40, spec 87/87
      on a copy (one older anchor re-pointed); compaction rule in `CLAUDE.shared.md` (11,258 bytes).
      The mirror script (`sync_agents_md.py`) is paused since 2026-10-01, so step 5 does not run it.
- [ ] 3. `rules.ts` + tests, without the `notes.ts` lines; wiring in `register.ts`, `types`, `compaction.ts`.
- [ ] 4. `tasks_done.py`, `docs_init.py` (+ `templates/docs/` written here), tests, SKILL rows, `verify.py`.
- [ ] 5. `CLAUDE.shared.md`: designs with upsides/downsides and a recommendation; project facts into
      `.docs`, never memory — within the 11 kB budget; run the mirror script.
- [ ] 6. Decision bullet in `setup-architecture.md`; FYI memory now "skill changes only"; FYI for running chats.
