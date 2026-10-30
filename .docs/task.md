# Tasks — the work setup's usage band (u4 back-port 2)

Progress (2026-10-30): tasks 1–3 and 8 are done ON THE COPY only, at
`C:\Users\aleks\AppData\Local\Temp\claude\C--Users-aleks--claude-claude-agentic-setup\77343937-3f9a-4a05-b6d7-b246540456f6\scratchpad\root\mods\asdev`
(87/87 tests on the app's engine 2.1.309, `$CLAUDE_CODE_EXECPATH`). The live `mods/asdev` is unchanged.
The full falsify spec (126 mutations: ours + 30 of u4's band ones + [Y/N] + 3 new) is
`...\scratchpad\full.spec`, run against the copy in the background. Two of u4's own band mutations were
stale (`USAGE_EVERY` → `every`) and were retargeted. If the scratchpad is gone, redo from u4 af7af91.

- [x] 1. compaction.ts: export TRIGGER_FROM; showCompacting(); STALE_COMPACTION in the ticker (+ tests) — copy
- [x] 2. band.tsx from u4 af7af91, plugin key asdev, traps.md comment adapted — copy
- [x] 3. band.test.tsx from u4, plugin key asdev; two old `prompt.submit` mocks now return `{ text }` (2.1.309 requires it) — copy
- [ ] 4. falsify RED for the right reason on all 126; replace mod-asdev.spec with full.spec; verify.py
- [ ] 5. copy → live `mods/asdev`; reload; check `monthStatus` in the store; owner looks at the band
- [ ] 6. docs: reference mod notes (setup-architecture, traps: the PATH `claude` is 2.1.287 and refuses the band's `tabular`/`size` props, so verify.py now tests with the app's engine), changelog, walkthrough
- [x] 7. prices.py: per-model prices in session_cost.py / agent_audit.py; self_test updated + a prices test
- [x] 8. compaction.ts asks() (as `asksOwner`): (Y/N), trailing aside, inline code ignored (+ test) — copy
- [ ] 9. repos.py, hygiene.py, gate.py ported (u4 `skills/u4as-audit/tools/`) and documented in the audit skill
