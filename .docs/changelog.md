# Changelog — `~/.claude` global setup

- 2026-09-30 — Phase: the setup in the shared private repo `Vikestart/claude-agentic-setup`, installed through junctions, co-maintained with the owner's partner → [`reference/setup-repo.md`](reference/setup-repo.md)
- 2026-09-30 — Phase: phase leads (two-level orchestration) and the 400k cap → [`walkthrough.md`](walkthrough.md), [`reference/traps.md`](reference/traps.md)
- 2026-09-30 — Phase leads rolled back at the owner's decision (depth 1 again; 400k cap, traps and the tightened agent test kept) → [`reference/setup-architecture.md`](reference/setup-architecture.md)
- 2026-09-30 — Phase: compaction instead of fresh chats (no handover proposals; `after_compact.py` hook; summary rule) → [`walkthrough.md`](walkthrough.md), [`reference/setup-architecture.md`](reference/setup-architecture.md)
- 2026-10-01 — Phase: leaner agents (explicit tool lists, `code_map.py`/`code_show.py`, plan sections in briefs; Sonnet for trivial work; Codex decoupled; last reply kept across compaction) → [`walkthrough.md`](walkthrough.md), [`reference/setup-architecture.md`](reference/setup-architecture.md)
