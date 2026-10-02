# Walkthrough — Session mod: graceful compaction and enforced rules (2026-10-02)

## What was built

- **`mods/asdev`** (renamed from `context-band`), loaded in every session through
  `env.CLAUDE_CODE_PLUGIN_DIRS`; `CLAUDE_CODE_PLUGIN_DIR_WATCH=1` makes desktop sessions reload it
  when the folder changes.
  - `band.tsx` — the usage band above the prompt; stays up when a measurement is missing.
  - `compaction.ts` — `ready to compact` as a reply's last line queues `/compact` with keep/drop
    instructions; 150k arms the plan's ⟲ checkpoints, then a nudge every +50k; under `/goal` the
    blocked stop is let through and the goal re-sent after. Agents get a note at 125k with nothing
    written and from 250k every +50k. Replaced `hooks/after_compact.py` and `hooks/context_guard.py`
    (archived in `reference/archive/hooks/`).
  - `guards.ts`, `shipped.ts` — refusals with the right tool named (see
    `reference/setup-architecture.md`, the `guards.ts` row).
- **Rule text removed** (step 6): from `CLAUDE.shared.md` "never poll", the heredoc clause, "When
  compacting" and the piped-runner clause; from the 7 executors the code_map, wait/poll and
  ~125k/~250k lines; from the orchestrator skill the polling sentence and the `model` line. Budgets
  shrank: shared 11.75 kB, orchestrator 10.5 kB.

## How it was verified

- `claude plugin test mods/asdev`: 22 tests; `claude plugin validate`: passed.
- `falsify.py --suite "claude plugin test mods/asdev" --mutations
  skills/asdev-web-audit/scripts/falsify/mod-asdev.spec`: 43/43.
- Detached `opus-high-reviewer` review: the guards covered Bash only (PowerShell now too), false
  positives on ordinary commands (narrowed), a Write meant to make a file LF (told; `.sh`/`.sql`
  exempt), a stranded `/goal` resume, and line endings flipped in 7 files (restored). Accepted gaps
  are in `reference/setup-architecture.md`, the `guards.ts` row.
- Live, in the desktop app: compaction trigger, `/goal` round-trip and Tilspire's real compaction
  (saved 250k); heredoc, piped runner, whole Read, foreground wait loop and bare `cat` refused;
  CRLF kept on Write; near-misses ran. Not live-tested: the Agent `model` guard and the shipped
  claim (unit tests only).
- `install/test_setup.py` OK; `doc_hygiene.py` clean.

## Where to look

- Live findings and API quirks: `reference/traps.md`, "Mods".
- Next: the start-up trim candidates in `roadmap.md` (owner's pick).
