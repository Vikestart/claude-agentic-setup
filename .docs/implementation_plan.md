# Implementation plan — a second brain in each project's `.docs/`

**Goal:** what Claude learns about a project lives in that project's `.docs/`, as linked notes you can
read, search and open as a graph, and travels with the repo. Today it is scattered over 14 hidden
memory folders under `~/.claude/projects/` (193 files, 515 kB; Nebulingo 66, Tilspire 55), outside
git, invisible to the partner's machine, and partly duplicating `.docs/reference/`.

**Decided (owner, 2026-11-17):** a second brain inside each project's `.docs/`, like Obsidian or
Graphify. The open decisions below were settled on the recommendations: A, `.docs/brain/`, committed
to git, a code graph on the roadmap; the plan was approved, and the big projects migrate in their own
chats rather than by agents (see Subagents). The reason the owner gave:
in the repo, the brain is not tied to one device.

## What was found (2026-11-17, CLI 2.1.325)
- The harness has two settings: `autoMemoryEnabled` (false: Claude neither reads nor writes memory)
  and `autoMemoryDirectory` (where memory lives). The second is honoured in a project's
  git-ignored `.claude/settings.local.json`, but not in the committed `.claude/settings.json`.
- The memory format is already close to Obsidian's: one note per file, frontmatter, `[[name]]`
  links, and an index (`MEMORY.md`) that is loaded at the start of every turn.
- Graphify (`pip install graphifyy`) builds a graph of code and docs: an HTML view, a report, a JSON
  graph and a hook that queries the graph before every Grep. It is a third-party package.

## The main decision: how the brain gets written
- **A (recommended): point the harness's own note-taking at `<project>/.docs/brain/`** via
  `autoMemoryDirectory`. Claude keeps the habit it already has (writing a note when it learns
  something, the index in every turn) without any new hook, and the notes land in the project as an
  Obsidian-ready vault. Downside: the note format is the harness's (a flat folder of one-fact notes),
  and it depends on a setting that could change.
- **B: switch memory off and write our own notes** under rules in a skill, with a hook loading the
  index. We control the format fully, but the writing habit then rests on rules alone, and rules
  like that have been skipped before (Tilspire's roadmap had reached 101 kB).

Steps below assume A. If B is chosen, step 2 becomes `autoMemoryEnabled: false` plus a
SessionStart hook that loads `brain/index.md`.

## Scope
- In: every active project (Nebulingo, Tilspire, Framvis with Vewport's notes, TSWDB, Recurlex,
  anti-video) and this setup repo (with asdev-blueprints'; the `htdocs` and `xampp` root folders'
  notes sorted by subject); the skills and rules that mention memory; a check script.
- Out: astole (retired) and Codex (decoupled): their folders stay as they are. A Graphify-style code
  graph → roadmap. Deleting the old memory folders, which needs the owner's word.

## Steps
1. **Skill `asdev-brain`** (new, about 5 kB): the brain is `.docs/brain/` with notes, `MEMORY.md` as
   the index, and `[[links]]` that reach the `reference/` files too. It says what goes in brain
   (decisions with their reason, traps, owner corrections for this project, outside pointers) and
   what goes in `reference/` (long-form subject documents, linked from notes), and when to write: the
   turn it is learned. It also says `.obsidian/` is git-ignored, so the owner can open `.docs/` in
   Obsidian for the graph view.
2. **`brain.py`** (audit suite), one verdict line per step:
   - `setup` writes `autoMemoryDirectory` into the project's `.claude/settings.local.json`. It is
     idempotent and refuses to overwrite a different value.
   - `migrate` copies the old folder into `.docs/brain/` and renames the old folder
     `memory.migrated-<date>`. It never deletes. A re-run picks up notes written since.
   - `check` reports broken `[[links]]`, notes nothing links to, and an index past 40 lines or with
     lines over 150 characters. `doc_hygiene.py` calls it, and also reports a project that has
     `.docs/` but no brain configured.
3. **Migrate each project:** run `setup` and `migrate`, then a judgement pass. That pass merges
   near-duplicates, moves facts that `reference/` already states into a link, corrects anything
   stale, and runs `check` until it is clean. A secrets scan runs over the notes before they are
   committed.
4. **Rules:**
   - In CLAUDE.shared.md, "Project facts go there, not memory" becomes a pointer to the brain, with no
     net growth: the file is at 11,261 of 11,264 bytes.
   - `asdev-handover` step 3b is rewritten for the brain.
   - `asdev-planner` step 2 gets a one-line pointer: it is at 7,930 of 7,936 bytes, so something is
     trimmed to make room.
   - Facts in this repo's memory that apply to every project move to `CLAUDE.personal.md`, which is
     private.
5. **Every device, by itself:** `autoMemoryDirectory` sits in the git-ignored
   `settings.local.json`, so the notes reach another machine through git, but the setting does not.
   A SessionStart hook in the asdev mod fills the gap: in a folder with `.docs/brain/` and no
   setting, it runs `brain.py setup` (in force from the next session) and, for this session, adds
   the brain's index to the context. A new project gets its brain the same way once `.docs/brain/`
   exists, which `brain.py setup` creates.
6. **Committed with the work:** the skill says brain notes go into the next commit, so a `git pull`
   on the other device brings them.

## Verification
- `brain.py` tests, with `setup`, `migrate` and the doc_hygiene hook falsified (`falsify.py`): they
  protect where data is written.
- A live check in one project: a new session writes a note into `.docs/brain/`, and its index
  appears in context. Then nothing new appears in the old folder.
- File counts after migration match the old folders, less what was merged. Each merge is listed in
  the walkthrough.
- `check` is clean in every project. The secrets scan finds nothing. On production, `.docs/` is
  confirmed unreachable from the web.
- Gate: `audit_all.py --changed` in each repo touched; plugin and doc hygiene in this one.

## Subagents
None (owner, 2026-11-17): Nebulingo, Tilspire and Framvis migrate in their own running chats, from a
paste-ready instruction this chat writes once the skill and `brain.py` have shipped. Until a chat
restarts, the harness still points its memory at the old folder, so the instruction tells it to write
new notes straight into `.docs/brain/` meanwhile. This chat writes the skill, `brain.py`, the hook and
the rule edits, and migrates this repo and the projects with no chat of their own. Before step 1, the
plan gets a detached review (`opus-high-reviewer`): it changes where every session writes.

## Release
- This repo: commit and push to `main`.
- Projects: one docs-only commit on `staging` each, which rides the next release to `main`.

## Residual risks
- A chat that is running keeps writing to its old folder until it restarts. A second `migrate` run
  picks those notes up.
- The brain lives in the working tree, so checking out another branch shows that branch's notes.
  Work stays on `staging`, so this rarely matters.
- If the harness drops `autoMemoryDirectory`, notes go back to `~/.claude`. `check`'s "no brain
  configured" line would show it.

## Open decisions
None: settled 2026-11-17 (see Decided). Anything private goes to `CLAUDE.personal.md`, never into a
committed brain.
