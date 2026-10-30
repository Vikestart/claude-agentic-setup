# Walkthrough — The work setup's usage band, back-port 2 (2026-10-30)

## What was built

- **The band** (`mods/asdev/hooks/band.tsx` and its tests, from u4 af7af91): Context ring with the
  150k mark, usage windows with pace, hover cards, a collapsed form for narrow windows, and Today /
  Month spend rows when the account has extra usage.
- **Compaction** (`compaction.ts`): one `/compact` per trigger while one waits; the Compacting
  counter stops after 10 minutes unseen; question detection skips code, reads `(Y/N)` and a `?`
  before an aside.
- **Audit suite:** `prices.py` (per-model list prices in `session_cost.py` and `agent_audit.py`,
  cdb102b), `hygiene.py` (BOM, endings, Python floor, f-string backslash), `repos.py` (every project
  repo in one table; only commits outside `main` and `staging` count against a branch).
- **`install/verify.py`** takes `gate.py`'s two lessons instead of a second runner: test files are
  found rather than listed (`test_code_nav.py` had never run), and a suite without its summary line
  fails. It tests the mod with the app's engine, which is newer than the `claude` on PATH.

## How it was verified

- Mod tests 87/87 on the app's engine 2.1.309, on a copy first; `mod-asdev.spec` 126/126 RED for
  the right reason (30 of the work setup's band mutations, two retargeted; 4 new).
- `verify.py` 19/19; its two new rules falsified (`falsify/verify.spec`, 2/2); `HygieneTests`,
  `ReposTests`, `Verify` unit tests; the audit skill back under its 21 kB budget (cdb102b had put
  it 61 bytes over).
- Not yet seen live: the band needs an app restart (roadmap, "Work-setup band: live check").

## Where to look

`reference/setup-architecture.md`, the `band.tsx` row; `reference/traps.md`, Mods (the PATH engine).
