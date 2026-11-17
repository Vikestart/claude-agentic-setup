---
name: falsify-one-run-per-cwd
description: "Two falsify.py runs in the same --cwd share one recovery file, so the second undoes the first's live test edit; run them one at a time"
metadata:
  node_type: memory
  type: project
  originSessionId: 2dfe9914-9149-47f6-8ec6-3fadf22ab68b
  modified: 2026-11-17T15:24:08.474Z
---

`falsify.py` journals each live test edit in one fixed file, `.falsify-inflight.json`, inside its
`--cwd`. At start-up, `recover()` treats any journal it finds as left by a killed run and restores
the file from it. A second run started in the same `--cwd` therefore puts back the guard the first
run has just reverted: the first run's suite then tests the intact guard, so its verdict is wrong
(a guard can read as VACUOUS when it is not), and its journal and backup are deleted under it.

**Why:** found on 2026-11-17; the journal name carries no run identity and nothing locks it.
**How to apply:** run falsify batches one at a time per `--cwd` (never two in parallel, including
from two agents) until `falsify.py` gives each run its own journal or refuses a second run.
Related: [[global-claude-setup]].
