# Implementation plan — a second brain in each project's `.docs/`

**Goal:** what Claude learns about a project lives in that project's `.docs/brain/`, as linked notes
you can read, search and open as a graph in Obsidian, and travels with the repo to every device.
Today it is scattered over 14 hidden memory folders under `~/.claude/projects/` (193 files, 515 kB;
Nebulingo 66, Tilspire 55), outside git, and partly duplicating `.docs/reference/`.

**Decided (owner, 2026-11-17):**
- A second brain inside each project's `.docs/`, like Obsidian or Graphify. The open decisions were
  settled on the recommendations: the harness's own memory pointed at `.docs/brain/`, committed to
  git, a code graph on the roadmap.
- The reason the owner gave: in the repo, the brain is not tied to one device.
- No agents: Nebulingo, Tilspire and Framvis do their judgement pass in their own chats.
- The plan review (`opus-high-reviewer`, 2026-11-17) changed steps 2, 4–6 and the checks; see "Review".

## Facts (2026-11-17, CLI 2.1.325)
- `autoMemoryDirectory` is honoured in a project's git-ignored `.claude/settings.local.json`, but
  never in the committed `settings.json`. It must be an absolute path. The harness resolves it once
  per session, so a change takes effect from the next session.
- On Windows the local settings file is read from the session's own folder, so a worktree or a
  subfolder session does not see the project root's file.
- The note format is already Obsidian-like: one note per file, frontmatter, `[[name]]` links, and a
  `MEMORY.md` index loaded every turn. The harness treats `type: user` notes as always private.
- `recurlex` and `anti-video` have memory folders but no project folder on this machine. TSWDB's
  `legacy-wp` folder has no git and no `.docs/`.
- `autoDreamEnabled` (background memory consolidation) is not set in `settings.json`.
- The owner works alone on their projects; the partner has separate projects and shares only this
  setup repo (owner, 2026-11-17). So `merge=union` guards one person's devices, and this repo's brain
  is the only one both write to.

## Steps
1. **Skill `asdev-brain`** (new, about 5 kB). The rules it sets:
   - **Where things go.** Brain notes hold decisions with their reason, traps, owner corrections
     about this project, and outside pointers. Long-form subject documents stay in `reference/`, and
     notes link to them.
   - **Never in a committed brain:**
     - notes about the person, which go to `CLAUDE.personal.md`;
     - secrets.
   - **Commit habit.** New notes go into the next commit.
   - **Obsidian.** `.obsidian/` is git-ignored.
2. **`brain.py`** (audit suite), one verdict line per step, with tests:
   - **`setup`** finds the main repo root (`git rev-parse --git-common-dir`) and writes that root's
     absolute `.docs/brain` path into the session folder's `settings.local.json`, so worktrees share
     one brain. It also:
     - keeps every other key in the file;
     - adds `settings.local.json` and `.obsidian/` to the project's `.gitignore` and checks they are
       ignored;
     - adds `.docs/brain/MEMORY.md merge=union` to `.gitattributes`, so two devices' index lines
       merge instead of conflicting.
   - **`migrate`** copies the old memory folder into the brain. Its safeguards:
     - It never overwrites. Index lines are merged, and a note whose name already exists in the
       brain arrives under a new name and is reported.
     - It renames the old folder `memory.migrated-<date>-<time>` only after every copy is verified
       by hash.
     - It refuses when the target repo does not exist.
     - It never deletes.
   - **`check`** fails on:
     - an index line pointing at no note, and a note the index cannot reach, directly or through
       `[[links]]` (built: a lost note is the real breakage, because the harness loads only the
       index; a `[[link]]` to a note not yet written is listed, not failed, since the harness's
       own instructions and Obsidian both use those as "worth writing");
     - an index over 40 lines, or with lines over 150 characters;
     - `type: user` notes;
     - a secrets-scanner finding in a note;
     - a hidden `memory/` folder the harness recreated for this project, which is the real sign that
       the setting is not taking effect.

     `doc_hygiene.py` shows its findings, so `audit_all --changed` scans new notes at every gate.
   - Built: `setup` adds an ignore rule only where the file is not already ignored. Claude Code puts
     `settings.local.json` in each person's global git ignore, and setup runs on every device.
3. **This repo:**
   - `setup` and `migrate`, then the judgement pass.
   - Notes about the owner personally go to `CLAUDE.personal.md`. Notes about the shared setup stay,
     committed.
   - asdev-blueprints' and the `htdocs`/`xampp` root folders' notes are sorted into this brain or a
     project's brain by subject.
4. **The hook, so every device and project manages itself.** In the asdev mod's `classic.SessionStart`,
   in a folder inside a repo with `.docs/` and no setting:
   - it runs `setup`, then `migrate` whenever an old memory folder holds notes, which covers the
     partner's own notes and later recreated folders;
   - it adds the brain's index to this session's context, with the line "write new notes to
     `.docs/brain/` this session", because the harness still uses the old folder until the next
     session.

   With that, `recurlex` and `anti-video` migrate the first time a session opens in them, wherever
   they exist. Building and testing the hook are separate steps (orchestrator rule), and the hook is
   falsified.
5. **Rules:**
   - In CLAUDE.shared.md, "Project facts go there, not memory" becomes a pointer to the brain, with no
     net growth (the file is at 11,261 of 11,264 bytes).
   - `asdev-handover` step 3b is rewritten. The handover and the compaction routine report
     uncommitted `.docs/brain/` changes.
   - `asdev-planner` step 2 gets a one-line pointer (7,930 of 7,936 bytes, so something is trimmed).
   - `asdev-release` §2 step 1 commits brain changes before any branch switch, so a release cannot
     strand or split notes.
   - `autoDreamEnabled: false` is set in `settings.json`, so no background job rewrites the brain
     unattended.
6. **The three big projects** (paste-ready instruction, after steps 1–5 ship and the app restarts):
   the hook has already migrated each one. Its own chat does the judgement pass: it merges
   near-duplicates, replaces facts that `reference/` already states with a link, corrects anything
   stale, runs `check` until clean, and makes one docs-only commit on `staging`. ⟲

## Verification
- `brain.py` tests, falsified with `falsify.py`:
  - `setup` keeps the existing keys (Nebulingo's file has some);
  - worktree resolution;
  - `migrate` never overwrites, on a re-run and on a name clash, and renames uniquely;
  - `migrate` refuses a missing target;
  - `merge=union` holds with two clones adding index lines at once.
- The hook, tested and falsified: it runs only where it should, and adds the index once.
- After migration, each project's set of note names and content hashes equals the old folder's,
  apart from the merges listed in the walkthrough.
- Live, in one project after a restart: a note written by a new session lands in `.docs/brain/`, and
  no hidden `memory/` folder is recreated (`check` confirms it). A worktree session writes to the
  same brain.
- `check` is clean in every project. `.docs/` is already deployed and blocked from the web in the
  three big projects; a URL check on production confirms `.docs/brain/` is not served.
- Gate: `audit_all.py --changed` in each repo touched; plugin test, plugin validate and doc hygiene
  here.

## Subagents
None (owner, 2026-11-17). This chat builds steps 1–5. The three big projects do step 6 in their own
chats.

## Release
- This repo: commit and push to `main`.
- Projects: one docs-only commit on `staging` each, which rides the next release to `main`.

## Review (opus-high-reviewer, 2026-11-17)
It found:
1. the partner's notes, and a device's first session, silently skipped;
2. `MEMORY.md` conflicts stalling releases;
3. a re-run of `migrate` overwriting reviewed notes;
4. worktree and subfolder sessions bypassing the brain;
5. private `user` notes committed;
6. missing project folders;
7. checks that could not fail;
8. the release checkout splitting the brain;
9. the commit habit, ignore rules and background consolidation.

All nine are taken into the steps and checks above.

## Residual risks
- Notes written after a session's last commit reach the other device only once something commits
  them. The handover and compaction routines report them.
- A CLI update could rename or drop `autoMemoryDirectory`. `check`'s "hidden memory/ recreated"
  failure is what would show it.
