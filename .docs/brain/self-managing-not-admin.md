---
name: self-managing-not-admin
description: The owner wants mechanisms that run themselves; anything needing them should shrink to a one-word answer at the moment it matters.
metadata:
  node_type: memory
  type: feedback
  originSessionId: 1b4075b7-528b-4288-afd7-86ed997eed69
  modified: 2026-09-30T20:07:10.460Z
---

The owner does not want to administrate settings or remember to undo things ("I don't want to
administrate/manage this", 2026-09-30, about a context-window override). Offering them a per-session
setting to flip, or a file to edit and revert, misses the point even when it is technically correct.

**Why:** they run several project sessions at once; every manual step is one they will forget, and
the setup exists to take that load off them.

**How to apply:** design the mechanism so a session manages it itself and cleans up after itself.
Where the owner's judgement is genuinely needed (e.g. `/compact`, which a model cannot run), reduce it
to one question with a one-word answer, asked once, at the moment it matters — never a standing
chore. Check first that the self-managing path actually works: the first design here (a session
raising its own `autoCompactWindow`) was built, then proven inert in a running desktop session with
`get_usage`, and removed. See [[global-claude-setup]].
An option the owner triggers in one sentence IS welcome when cleanup is automatic: they asked for
the handover to raise the next session's limit on request, while the next handover clears it
(2026-09-30, `context_override.py`). "Rarely fires on its own" is fine; "they must undo it" is not.
