---
name: portable-shareable-setup
description: "Private content stays in each skill's git-ignored local/ overlay; what to move there, and the two leak classes a name search misses"
metadata:
  type: reference
---

Since 2026-08-30 the skills can be handed to another developer without a second, cleaned-up copy.
Anything under a skill's `local/` folder is the author's own inventory: git-ignored, never committed,
left out of `share_bundle.py`'s zip. Every skill must still work without it (SKILL.md reads an overlay
"if present"). How the bundle is built: [setup-repo](../reference/setup-repo.md), "The share bundle".

**What moves to `local/`:** a *live defect*, a weakness still unfixed in a named running system, and
the paths that point into a project. A *pattern lesson* stays in the shared half: the incident's force
without saying whose it was. When in doubt, move it.

⚠️ **A search for project names is not enough.** Two more leak classes had to be found by reading:
- *estate-scoping phrases*: "the three reference projects", "no project has X", "verified across every
  project". They reveal how many systems the author runs and that all of them lack a control.
- *compositions*: a generic brief ("no worked example yet") next to a passage calling the missing
  thing exploitable together say which of the author's systems is exposed.

Write about the field instead ("few codebases have…", "design brief only").

**Why:** a name search passed while both classes still leaked (2026-08-30); a reading review then
missed a third of what a follow-up search caught.
**How to apply:** when editing a skill's shared half, or this repo's `.docs/` and brain, keep project
detail out; it goes to `local/` or to the project's own docs. Related: [[asdev-blueprints-skill]],
[[global-claude-setup]].
