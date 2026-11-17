---
name: asdev-blueprints-skill
description: "The capability-inventory skill: the owner's scope rule (its chat never fixes projects), and the lessons from building it"
metadata:
  type: project
---

`skills/asdev-blueprints/` is the inventory every web project is held to: capability ids in four
tiers, contracts, invariants, and a per-project `.docs/reference/platform-manifest.md`, with three
modes (Scaffold, Audit, Build). Its pointers into the owner's projects, and their live defects, are in
its git-ignored `local/` ([[portable-shareable-setup]]). Built 2026-08-23 with the skill-creator loop:
with the skill, test tasks scored 97% against 81% without, and 100% after the detached review's fixes.

**Scope rule (owner, 2026-08-23):** work on the skill never fixes a project. A gap it finds is closed
in that project's own chat, through the skill's Audit or Build mode; no fix chips from skill work.
The owner confirmed it on 2026-11-17: a fix in this repo is made here, a fix in a project goes to that
project's chat.

**Lessons:**
- The authors trusted the projects' docs where the code disagreed; six claims in the references were
  wrong until a detached review read the code. Check a load-bearing claim against the code.
- A reading review and a mechanical search each find what the other misses; run both
  (`asdev-orchestrator`, reviews).
- Agents running evals side by side shared one scratch folder and overwrote each other's files; give
  each its own.
- `scripts/self_test.py` checks that every cited path exists; `install/verify.py` runs it.

**Why:** three projects had built the same platform three times; the owner wants consistency from the
start. **How to apply:** read SKILL.md before scaffolding or auditing a project; keep the scope rule.
Related: [[global-claude-setup]].
