# Walkthrough — Back-port from the work setup (2026-10-28)

## What was built

- **Guards** (`mods/asdev/hooks/guards.ts`, ced1126): the work setup's three review rounds — a
  runner piped to a filter inside compound commands and wrappers, PowerShell here-strings and wait
  loops, whole `Get-Content` reads, and a `model` on any Agent call refused.
- **Compaction stages** (`compaction.ts`, c313e00): a careful nudge from 230k; from 280k, with no
  `.docs` write since 230k, the main chat is held to docs writes, searches and git reads.
- **Rule-change notes** (`hooks/rules.ts`, e035a80): an edited CLAUDE.md rule reaches a running chat
  on its next prompt. Redesigned for this engine (see `reference/setup-architecture.md`).
- **`tasks_done.py`, `docs_init.py`** and `templates/docs/` in the audit suite (a93024c).
- **Two rules** in `CLAUDE.shared.md` (2cf28e4): designs with pros, cons and a recommendation;
  project facts into `.docs`, not memory.

## How it was verified

- Mod tests 48/48; `mod-asdev.spec` 92/92 RED for the right reason, on a copy of the mod first.
- `test_tasks_done.py` 12/12, `test_docs_init.py` 18/18; `install/verify.py` 18/18; precommit scan
  clean on every commit. Read-only runs on framvis and tilspire report as expected.

## Where to look

The decision bullet "Back-ported from the work setup" in `reference/setup-architecture.md`.
