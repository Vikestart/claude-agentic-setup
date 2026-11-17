---
name: global-claude-setup
description: "Where the setup's knowledge lives: the handover, the repo's mechanics, the decisions with their reasons, and the traps; read the matching one before changing the setup"
metadata:
  type: reference
---

The shared setup is this repo, `claude-agentic-setup`, cloned at `~/.claude/claude-agentic-setup` and
linked into `~/.claude` (agents, hooks, `.docs`, each `skills/asdev-*`). Setup work runs from the repo
root (since 2026-10-01). What is already written down, and where:

- [handover](../handover.md): the state, read first.
- [setup-repo](../reference/setup-repo.md): how the repo, the links, the installer and the share
  bundle work.
- [setup-architecture](../reference/setup-architecture.md): every decision with its reason, the agent
  roster's and the cost measurements' included.
- [traps](../reference/traps.md): what cost real time. ⚠️ Deleting a linked folder recursively deletes
  the repo's files; measured `usage` repeats per content block (2.97×), so dedupe by `requestId`.

**Why:** these notes were first written from other folders (the htdocs root, the blueprints skill),
then merged here on 2026-11-17; the reference docs had since taken over most of their facts.
**How to apply:** look a fact up in the doc above that owns it, and correct it there, not in a note.
Related: [[portable-shareable-setup]], [[asdev-blueprints-skill]].
