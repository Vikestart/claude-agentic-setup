# Finished tasks, 2026-10

## 2026-10-28

- [x] 1. Guards merged (work `guards.ts` + our `AUDIT` path and `audit_all/self_test/verify.py`
      runners), tests 38/38, `mod-asdev.spec` 73/73 on a copy (incl. two stale band/trigger anchors fixed).
- [x] 2. Compaction stages: careful nudge from 230k, docs hold from 280k; tests 40/40, spec 87/87
      on a copy (one older anchor re-pointed); compaction rule in `CLAUDE.shared.md` (11,258 bytes).
      The mirror script (`sync_agents_md.py`) is paused since 2026-10-01, so step 5 does not run it.
- [x] 3. `rules.ts` + tests; tests 48/48, spec 92/92. Changed from the work version: this engine
      refuses `$` passed to an imported function and a second `session.start`/`session.compact` hook,
      so `compaction.ts` clears the stored rules on a compaction and the next prompt re-baselines.
- [x] 4. `tasks_done.py`, `docs_init.py` (+ `templates/docs/` written here), tests 12/12 and 18/18,
      SKILL line, `verify.py` 18/18. `reference/README.md` dropped from the required set: no project has one.
- [x] 5. `CLAUDE.shared.md`: designs with pros, cons and a recommendation; project facts into
      `.docs`, not memory. 11,263 bytes: the duplicate "§3 never regresses" bullet in §4 and a few words came out.

## 2026-10-30

- [x] 1. compaction.ts: export TRIGGER_FROM; showCompacting(); STALE_COMPACTION in the ticker (+ tests) — copy
- [x] 2. band.tsx from u4 af7af91, plugin key asdev, traps.md comment adapted — copy
- [x] 3. band.test.tsx from u4, plugin key asdev; two old `prompt.submit` mocks now return `{ text }` (2.1.309 requires it) — copy
- [x] 4. falsify RED for the right reason on all 126; replace mod-asdev.spec with full.spec; verify.py
- [x] 5. copy → live `mods/asdev`; reload; check `monthStatus` in the store; owner looks at the band
- [x] 6. docs: reference mod notes (setup-architecture, traps: the PATH `claude` is 2.1.287 and refuses the band's `tabular`/`size` props, so verify.py now tests with the app's engine), changelog, walkthrough
- [x] 7. prices.py: per-model prices in session_cost.py / agent_audit.py; self_test updated + a prices test
- [x] 8. compaction.ts asks() (as `asksOwner`): (Y/N), trailing aside, inline code ignored (+ test) — copy
- [x] 9. repos.py, hygiene.py, gate.py ported (u4 `skills/u4as-audit/tools/`) and documented in the audit skill
