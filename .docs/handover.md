# Handover — `~/.claude` global setup — 2026-10-01

**Work continues in `C:\Users\aleks\.claude\claude-agentic-setup`** (the repo root, owner's choice),
not `C:\xampp\htdocs`. That folder's memory scope was seeded with a copy of the htdocs memories.

## State
- Repo `~/.claude/claude-agentic-setup`, branch `main`, in sync with origin at `6dc6abf` before this
  docs commit; uncommitted: none. The partner gets it at their next pull.
- Applied on this machine: `install.py --check` in place; `~/.codex/AGENTS.md` deleted (Codex decoupled).
- Checks at `6dc6abf`: `install/verify.py --gate .` 16/16, `self_test.py` OK, after-compact 19/19,
  code-nav 78/78; falsify agent-tools 7/7, code-nav 15/15, compact-hook 4/4, compact-reply 6/6,
  doc-budget 3/3, session-cost 2/2, heredoc-lang 1/1 (specs in `skills/asdev-web-audit/scripts/falsify/`).
- Elsewhere, uncommitted on purpose: the AGENTS.md scanner-path fix in xampp-pulse and tilspire-com
  (roadmap "Later"; their own sessions commit it).
- Next session's context limit: shared cap (`context_override.py status` → none).

## Since the last handover (all 2026-10-01; one line each in [`changelog.md`](changelog.md))
- Compaction instead of fresh chats; the after-compact hook also restores the last turn-ending
  message verbatim and names working files over budget.
- Leaner agents: explicit `tools:` lists (start-up 46k → ~27k CLI, ~40k in the app),
  `code_map.py` / `code_show.py` (PHP, JS, Python, Markdown) → [`reference/setup-architecture.md`](reference/setup-architecture.md).
- Effort by role; `sonnet-medium-executor` for mechanical work; phase leads and `opus-low-executor` archived.
- Simplified 2026-10-01: rule files size-budgeted ("one in, one out"), Skill tool off every agent,
  window 330k.
- Codex decoupled; working-file size budgets with a Trim step; `session_cost.py` added and taught to
  flag truncated output.

## Decisions (reasons in [`reference/setup-architecture.md`](reference/setup-architecture.md))
- Effort by role, not by phase; every review at `high`; `xhigh` only as fallback (owner).
- 1-hour agent cache kept: re-measured as a wash (96.16M vs 95.93M).
- Size budgets are enforced by `doc_hygiene.py` at phase completion, handover and every compaction.
- Codex decoupled; `sync_agents_md.py` kept only for its import expander.

## Next
1. Re-measure the next Nebulingo and Tilspire sessions with `session_cost.py` (roadmap "Re-measure"):
   effort-by-role savings, whether the Trim step shrinks their working files, and whether
   Nebulingo's main chat (43% of its cost) still does hands-on work.
2. Then decide the optional Skill-tool removal for reviewers (roadmap).

## Open questions for the owner
- Add the partner as a collaborator on GitHub (owner action).
- Disable connectors a project never uses (owner action).

## Read first
- [`roadmap.md`](roadmap.md), [`reference/setup-architecture.md`](reference/setup-architecture.md),
  [`reference/traps.md`](reference/traps.md), [`reference/setup-repo.md`](reference/setup-repo.md)
