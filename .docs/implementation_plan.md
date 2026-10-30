# Implementation plan — the work setup's usage band (u4 back-port 2)

**Goal:** bring every change the work setup made to the usage band (`mods/u4as/hooks/band.tsx`)
into `mods/asdev`, and list the other work improvements worth taking, for the owner to pick.

**Decided:** owner, 2026-10-30: "incorporate all of the improvements to our modded bar" — the
Context ring, the usage bars, the hover cards, the narrow-band adaptations, all of it. Source:
`C:\Users\aleks\OneDrive\Documents\claude-agentic-setup-u4` at af7af91.

## Facts found (2026-10-30)
- Our `band.tsx` matches u4's 1634497 (2026-10-20) except the plugin key and `TIDY_AT` (200k, a
  local constant; our compaction actually triggers at `TRIGGER_FROM` 150k, so our faint arrow is stale).
- u4's band imports `TRIGGER_FROM` from `./compaction` (ours does not export it yet).
- Bar-related compaction changes in u4: `showCompacting()` (one toast and ticker per compaction,
  none for a second `/compact` while one waits, af7d7b5), `STALE_COMPACTION` (the ticker stops after
  10 minutes, 9194d31). The rest of u4's compaction diff is `notes.ts` / security-plugin work, which
  stays out (work-only, as the 2026-10-28 port decided).
- The Today/Month rows read the account's extra-usage figure (`api/oauth/usage`) and show only when
  extra usage is enabled; Today's pace runs over weekday working hours 08–16. Ported with the rest
  (owner said all); check `monthStatus` in the store after the reload and report what shows.

## Steps
1. Export `TRIGGER_FROM` from `compaction.ts`; bring `showCompacting()` and `STALE_COMPACTION`.
2. Replace `band.tsx` with u4's, adapted: plugin key `asdev`, the traps.md comments, `RED` export.
3. Port `band.test.tsx` (and the compaction tests for step 1), plugin key adapted.
4. Update `mod-asdev.spec` (falsify) for the new guards; `install/verify.py`.
5. Copy-first: change a copy of the mod, run its tests, then the live folder; reload and look.
6. Docs: `reference/` mod notes, changelog, walkthrough.

## Verification
- Mod tests green; `mod-asdev.spec` RED for the right reason on every mutation; `verify.py` all pass.
- The owner looks at the band at full width and with a side panel open.

## Other work improvements — for the owner to pick (not in this phase)
- `prices.py`: per-model list prices for `session_cost.py` / `agent_audit.py` — ours weigh every
  model as Opus, so the Sonnet/Haiku experiment's savings would be mis-measured. Recommended.
- Question detection in `compaction.ts` (u4 `asks()`): also catches `(Y/N)`, a trailing aside after
  the `?`, and ignores inline code. Recommended.
- `repos.py` (one-call git status across repos), `hygiene.py` (BOM, line endings, Python floor),
  `gate.py` (a skill's test gate as one table). Optional.
- Left out: Copilot, `notes.ts`, `ship.py`, `skilldiff.py`, `validate.py` (work-only).

## Release
Setup repo, `main` only: commit and push per step group.
