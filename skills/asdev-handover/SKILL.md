---
name: asdev-handover
description: Hand a project over to a fresh chat — bring every .docs working document up to date, review stray docs, sweep the reference library, write handover.md, and give a short paste-ready message for the new chat. Use ONLY once the user says yes to a proposed fresh chat, asks for a handover, or asks to wrap up for a new chat. Not for ordinary phase completion, a changelog line, or a status summary.
---

# Handover

**The goal:** a new chat that reads only files can carry on without the old transcript. Whatever is
not written down is lost, and `handover.md` is replaced next time rather than archived — so durable
material belongs in `.docs/reference/`, and the handover only points at it.

Work through the steps in order: each one feeds the next. Output tokens cost several times input, so
update files with `Edit` and scripts, and never re-emit a document that barely changed.

## Before you start

- **Only on the owner's yes.** CLAUDE.md §1 says when to *ask*; this skill runs once they answer.
  While the question is open, finish the current phase but do not start or research the next.
- **List every repo this session touched** — a session on one project often edits another's docs,
  hooks or shared skills. Each one gets steps 0–3; the handover itself goes where the work continues.
- **A global-setup session** (`~/.claude` itself) hands over in `~/.claude/.docs/`. It is not a git
  repository, so there is no commit step; its backups are the ones `reference/setup-architecture.md`
  names.

## 0. Establish the true state — from the source, not memory

- **Scope:** the `.docs/` of each repo whose state changed this session.
- **Nothing half-done:** finish or back out any edit in progress. If a phase is mid-flight, note
  exactly where it stopped — what is done, what is not, which files are uncommitted.
- **Facts, checked now:** `git status`, the branch and its sync state, the commits since the last
  handover (its date is in the old `handover.md`), and the deployment state of local, staging and
  production. Never write "deployed" or "pushed" unless you just verified it — for a deploy, by the
  running version on the site, not by a successful push (see the `asdev-release` skill).
- **Let the script gather them:** `python $HOME/.claude/skills/asdev-web-audit/scripts/handover.py
  --path . --stdout` prints the factual half of a handover — branch, commits, changed files, check
  results — straight from git, so none of it is written from memory. It leaves decisions and next
  steps blank; those are yours. It never overwrites an existing `handover.md` without being told
  to (see `--help`), so use `--stdout` and merge its output into step 4. Outside a git repository (`~/.claude` itself) it
  has nothing to gather: run the project's own checks and record their results instead.

## 1. Working documents

Bring each one in line with what actually shipped. The handover is written from them, so it inherits
any staleness as fact.

| File | Must say afterwards |
|---|---|
| `implementation_plan.md` | The one active or ready-next phase, or plainly that no plan is active. Completed phases removed — their durable facts move in step 3. |
| `task.md` | Only that phase's open tasks. |
| `roadmap.md` | Remaining outcomes in order, shipped ones removed, newly found future work added. Always exists, even if it says empty. |
| `changelog.md` | One line per phase completed since the last handover (`Phase N — …`, linking its reference doc). Near ~100 lines, rotate the oldest block into a dated reference archive. |
| `walkthrough.md` | The most recent completed phase only. |

Create `roadmap.md` if missing; create the others only if the project already uses them.

## 2. Any other `.md` directly in `.docs/`

List every `.md` directly in `.docs/` besides the five above and `handover.md`. For each, decide:

- **Still needed** → keep it and update it.
- **Holds durable material** → move that material into the reference file that owns the subject, then retire the file.
- **Obsolete** → retire it.

"Retire" means delete only when git tracks the file, so history keeps it; otherwise move it to
`.docs/reference/archive/` or the Recycle Bin — never hard-delete untracked material. Report each
decision in one line.

## 3. Sweep `.docs/reference/`

1. **Collect** what changed since the last handover: the commits and diff stat, the new changelog
   lines, and the decisions and traps from this session.
2. **Record** each durable item in the file that owns its subject — architecture, decisions *with
   their reason*, invariants, caveats, commands and checks a new session needs, and traps that cost
   real time. Create a new file where no file owns the subject, and link it from the project's index
   if it has one. Order by what a new session would otherwise rediscover the hard way.
3. **Prune** what has gone stale: correct what is now wrong and remove what is superseded. Never
   remove release or audit history. Generated files (`platform-manifest.md`, dated audit reports) are
   rewritten by the tool that owns them, never by hand.
4. **Test it:** could a new session act correctly from `reference/` alone? If it would still need
   the transcript for something, that something is missing. If this touches the project's `CLAUDE.md` / `AGENTS.md`, keep it within the size budget in the `asdev-conventions` skill.

## 3b. Memory — only what outlives the project

`reference/` holds facts about *this* project. Memory holds what applies across projects: the
owner's preferences and corrections, how they like to work, pointers to outside resources. For each
lesson from this session, pick one home, never both:

- about this codebase → `reference/` (step 3);
- about the owner or how to work with them, and not obvious from any file → memory: one fact per
  file, update an existing one rather than adding a near-duplicate, index line in `MEMORY.md`;
- already recorded in code, git history or an instruction file → neither.

Correct or delete a memory this session proved wrong. The index `MEMORY.md` is loaded every turn:
keep each line under ~150 characters, merge superseded entries, and once it passes ~40 lines run
the `consolidate-memory` skill.

## 4. Write `.docs/handover.md`

Short, and linking rather than repeating:

```markdown
# Handover — <project> — <YYYY-MM-DD>

## State
- Branch: <branch>, <in sync with origin | ahead/behind>; uncommitted: <none | files>
- Deployment: local <…> · staging <…> · production <…> (how each was verified)

## Since the last handover
- <one line per shipped phase or fix, linking changelog/reference>

## Decisions
- <decision> — <why> (→ `reference/<file>.md`)

## Next
1. <the immediate next step>
2. <then>

## Open questions for the owner
- <or "none">

## Read first
- `implementation_plan.md`, `reference/<file>.md`, …
```

## 5. The paste-ready message

End with a very short message in a fenced markdown block, ready to paste into the new chat — about
five lines: the project and its path, "read `.docs/handover.md` first", the immediate next step, and
any question waiting on the owner. Everything else belongs in the files. For example:

```markdown
myapp (C:\xampp\htdocs\myapp). Read .docs/handover.md first, then the files it lists.
Next: Phase 141 — the plan is written and approved, start at task 1.
Waiting on the owner: whether the old export stays after launch.
```

## Finish

- Check that every path `handover.md` links to exists.
- If the project commits `.docs/`, commit the documentation as one docs-only commit, following the
  project's branch rules, and report the true commit and push state.
- If this session changed the global `CLAUDE.md`, a skill or `~/.claude/agents`, add a second
  fenced block: an FYI for the owner's other running chats. They loaded the old instructions at
  start, keep following them, hand the old text to their subagents, and cannot spawn an agent
  definition added since. State the new rules plainly, as information rather than tasks.
- Report one line per step (what changed, what was retired), then the paste-ready block.

## Failures seen before

- **Copying state from the old handover.** Every state line is re-checked now; the old file is only
  where the last handover's date comes from.
- **"Pushed" that was only committed, "deployed" that was only pushed.** Verify each level.
- **A handover that needs the transcript.** If the new chat would have to ask "why did we…?", the
  answer belongs in `reference/` with its reason.
- **Restating reference docs inside `handover.md`.** It is replaced next time, so anything only
  written there is lost. Link instead.
- **Starting the next phase to "save time".** That work lands in a context about to be discarded,
  and the new chat inherits it half-done.
