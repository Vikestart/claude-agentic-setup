# Implementation plan — back-port from the work setup

**Goal:** bring back what the work setup fixed and added since it was ported from here on 2026-10-20,
without losing anything only this setup has. Source: `~/Downloads/personal-setup-backport.md`
(owner, 2026-10-28; it embeds every file byte-for-byte; the embedded code was scanned and reaches no
network and no credentials).

**Decided:** the owner asked for the back-port and approved this plan, both recommendations
included: a `model` on any Agent call is refused, and `ship.py` stays out (2026-10-28). Names map `u4as` → `asdev`, and
`tools/` and `tests/` → `scripts/`. Merge, never overwrite: what only this setup has stays
(`offset`, `DEFINITION`, `INLINE_CODE`, `READER` in `guards.ts`, and the 2026-10-21 rules).

## Scope

Measured first: the work `guards.test.ts`, run against our `guards.ts`, passes 34 tests and fails 4.

| # | Item | Verdict | Why |
|---|---|---|---|
| 1 | Guards (`mods/asdev/hooks/guards.ts`) | **Port** | 4 real gaps: a runner piped to a filter inside compound commands and wrappers (`timeout 300 pytest \| tail`), PowerShell here-strings and wait loops, whole `Get-Content` reads, a `model` on an Agent call. |
| 2 | Compaction stages (`compaction.ts`) | **Port, scaled to our 330k window** | Careful from **230k**, and from **280k** with no `.docs` written since 230k, every tool except `.docs` writes, searches and git reads is refused. Today nothing stops a session drifting into the automatic compaction (~297k) with stale docs. |
| 3 | Rule-change notes (`hooks/rules.ts`, new) | **Port** | A running chat sees an edited CLAUDE.md rule on its next prompt, not only after a compaction. The hand-written FYI is then needed only for skill changes. |
| 4a | `tasks_done.py` | **Port** | Moves ticked `task.md` items to a dated archive: step 3 of the planner's completion routine, now done by hand. |
| 4b | `docs_init.py` | **Port, with templates written here** | Creates a missing `.docs/` layout. Its `templates/docs/` folder is not embedded, so I write the templates from the `asdev-planner` layout. The work SessionStart hook `docs_check.py` is left out. |
| 4c | `ship.py` | **Leave out** | It ships through a feature branch and a PR. Our rule is `staging` → `main` with no other branch, and this repo pushes straight to `main`. `asdev-release` already covers the release. |
| 5 | Two rules in `CLAUDE.shared.md` | **Merge the wording, within budget** | "Draw UI first" gains *each direction's upsides and downsides, and which one I recommend*. Add "Project facts go into `.docs`, never memory." The file has 4 bytes left under its 11 kB budget, so the same number of bytes comes out elsewhere. |

Out: `ship.py`; `notes.ts` and the move to native events (only for Team and Enterprise managed
plugins, so not needed here); the work-only rules.

## Steps
1. **Guards:** merge the work `guards.ts` function by function (`program`, `group`, `hasHereString`,
   `psWaitLoop`, `WRAPPER`, `KEYWORD`, `PS_OPERATOR`…), keep the four parts only we have, and merge
   both test files. Add the work falsify entries to `mod-asdev.spec`.
2. **Compaction:** port `CAREFUL_FROM` (230k), `DOCS_BY` (280k), `docsAt`, `docsHold()`, the careful
   nudge, the `docsAt` update and its reset on compaction, with their three tests and falsify entries.
   Update the compaction rule in `CLAUDE.shared.md` to match.
3. **Rules notes:** add `rules.ts` and its tests, without the `notes.ts` lines the document names.
   Wire it into `register.ts`, `types/index.d.ts` (`rules`) and `compaction.ts` (`baseline` on
   compaction, `start` on session start). Add its falsify entries, without the `measure` ones.
4. **Scripts:** `tasks_done.py`, `docs_init.py` and their tests under `scripts/`, plus `templates/docs/`,
   their two `SKILL.md` table rows and `verify.py` entries. `tasks_done.py` is named in the
   planner's completion step 3.
5. **Rules:** edit `CLAUDE.shared.md` and run the mirror script.
6. **Records:** one decision bullet in `setup-architecture.md`, and the FYI memory now reads "skill changes only".

## Verification
- `claude plugin validate` and `claude plugin test` on a **copy** of the mod (the live folder runs in
  every open session), then on the live folder once the copy passes.
- Every new guard falsified on the copy with the ported spec entries; each must go RED for its stated reason.
- `test_tasks_done.py`, `test_docs_init.py`; `install/verify.py` (all checks) and `test_setup.py`
  with its budgets; `audit_all.py --changed`; the precommit scan.
- A live check after the mod reloads: a whole `Get-Content` of a big file is refused, and an edit
  to a rule line shows a note on the next prompt.

## Subagents
None. Every step is a merge into files I have already diffed, and they depend on each other
(`compaction.ts` is touched by steps 2 and 3). One writer avoids conflicts.

## Release
This repo has only `main`: commit and push per step, so each step can be undone on its own. No
staging. Then an FYI for the running chats.

## Residual risks
- A new guard refuses something legitimate in every open session — the reload makes it live at
  once. The tests' near-miss cases guard against it, and a bad commit is one revert.
- The 280k hold could trap a session that cannot write `.docs`. Mitigation, ported as is: a
  project with no `.docs` working files and subagents are never held.

## Open decisions
- **A `model` on any Agent call refused** (the work rule), against only on our own definitions
  (ours). Recommended: port it. Model choice then always comes from the definition, and an override
  is applied by picking another definition.
- **Leave `ship.py` out.** Recommended: yes, for the branch-rule reason above.
