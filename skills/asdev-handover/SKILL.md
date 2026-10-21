---
name: asdev-handover
description: Hand a project over to a fresh chat — bring every .docs working document up to date, review stray docs, sweep the reference library, write handover.md, and give a short paste-ready message for the new chat. Use ONLY when the user asks for a handover or to wrap up for a new chat (another machine, their partner, a long break) — sessions never propose one; compaction handles context size. Not for ordinary phase completion, a changelog line, or a status summary.
---

# Handover

**The goal:** a new chat that reads only files can carry on without the old transcript. Whatever is
not written down is lost, and `handover.md` is replaced next time rather than archived — so durable
material belongs in `.docs/reference/`, and the handover only points at it. Work through the steps
in order: each one feeds the next.

## Before you start

- **Only when the owner asks** (CLAUDE.md §1): switching machines, handing to their partner, or
  before a long break.
- **List every repo this session touched** — a session on one project often edits another's docs,
  hooks or shared skills. Each one whose state changed gets steps 0–3 in its own `.docs/`; the
  handover itself goes where the work continues.
- **A global-setup session** (`~/.claude` itself) hands over in `~/.claude/.docs/`, which is part of
  the shared repo `~/.claude/claude-agentic-setup`: commit there and push to `main` (`git pull
  --rebase` first; the other maintainer sees it at their next pull).

## 0. Establish the true state — from the source, not memory

- **Nothing half-done:** finish or back out any edit in progress. If a phase is mid-flight, note
  exactly where it stopped — what is done, what is not, which files are uncommitted. Never start the
  next phase "to save time": that work lands in a context about to be discarded.
- **Facts, checked now — never copied from the old handover,** which only supplies the last
  handover's date: `git status`, the branch and its sync state, the commits since then, and the
  deployment state of local, staging and production. Verify each level — "pushed" that was only
  committed and "deployed" that was only pushed are the usual errors; a deploy is verified by the
  running version on the site (`asdev-release`).
- **Let the script gather them:** `python $HOME/.claude/skills/asdev-web-audit/scripts/handover.py
  --path . --stdout` prints the factual half — branch, commits, changed files, check results —
  straight from git, and leaves decisions and next steps to you. Merge its output into step 4 (it
  refuses to overwrite an existing `handover.md`; see `--help`). Outside a git repository
  (`~/.claude` itself) it has nothing to gather: run the project's own checks and record their results.

## 1. Working documents

Bring each in line with what actually shipped — the handover inherits any staleness as fact. The
rules are `asdev-planner`'s ("Working documents", "Completing a phase"); afterwards:

| File | Must say |
|---|---|
| `implementation_plan.md` | The one active or ready-next phase, or plainly that no plan is active. Completed phases removed — their durable facts move in step 3. |
| `task.md` | Only that phase's open tasks. |
| `roadmap.md` | Remaining outcomes in order, shipped ones removed, newly found future work added. |
| `changelog.md` | One line per phase completed since the last handover, rotated as in `asdev-planner` step 5. |
| `walkthrough.md` | The most recent completed phase only. |

Create `roadmap.md` if missing; the others only if the project already uses them. Then trim until
`doc_hygiene.py` is clean, as in `asdev-planner` step 6 — move, never delete, anything still open.

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
   lines, and this session's decisions and traps.
2. **Record and prune** as in `asdev-planner` step 2: each durable item, decisions *with their
   reason*, in the file that owns its subject; stale facts corrected or removed; generated files
   only through their tool; release and audit history never removed. Where no file owns a subject,
   create one and link it from the project's index if it has one. Put first what a new session
   would otherwise rediscover the hard way — commands, checks, traps that cost real time.
3. **Test it:** could a new session act correctly from `reference/` alone? If it would have to ask
   "why did we…?", the answer belongs there, with its reason.

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

Short, and linking rather than repeating — anything written only here is lost next time:

```markdown
# Handover — <project> — <YYYY-MM-DD>

## State
- Branch: <branch>, <in sync with origin | ahead/behind>; uncommitted: <none | files>
- Deployment: local <…> · staging <…> · production <…> (how each was verified)
- Next session's context limit: <shared cap | override <N> — <reason>> (step 4b)

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

## 4b. The next session's context limit

Every main session compacts at the shared `autoCompactWindow` cap (330k, compacting ~33k below it).
A project may get a temporary override for the next session only, set now because settings load at
session start. From the project root, with `S=$HOME/.claude/skills/asdev-web-audit/scripts`:

1. `python $S/context_override.py status`.
   - `temporary`: an earlier handover set it for this session. Clear it
     (`python $S/context_override.py clear`), unless point 2 sets it again.
   - `deliberate`: leave it alone.
2. Decide the next session's limit. The default is the shared cap. Raise it when:
   - the owner asks for it (use their number, or size it as below); or
   - the next phase must hold more than ~370k in the main session with no natural split point, for
     example this session hit compaction mid-phase, or the plan's next phase is large and cannot be
     split.
   Size it at the expected peak plus ~30k, rounded up to 50k, at most 1,000,000. Set it with
   `python $S/context_override.py set <N> --reason "<phase, why>"`; the script refuses a value at or
   below the cap and never overwrites a deliberate setting. The phase-completion routine clears it
   once its phase is done (`asdev-planner` step 7), so it cannot outlive that phase.
3. Record the result on the handover's "Next session's context limit" line, and in the paste-ready
   message when it is raised.

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
  start, keep following them, hand the old text to their subagents, and may not be offered an agent
  definition added since. State the new rules plainly, as information rather than tasks.
- Report one line per step (what changed, what was retired), then the paste-ready block.
- **Start the successor**, so the owner does not have to paste:
  - `ToolSearch` `select:mcp__ccd_session__hand_off_to_session`. If it loads, hand off with a fresh
    context (not a fork) and the paste-ready message as the prompt, then report where the successor
    started. If it started on a new branch in a project bound to `main`/`staging`, say so.
  - Otherwise, if the session folder is **not** a git repository, offer the successor as a
    `spawn_task` chip: title "Continue: <project> handover", the paste-ready message as the prompt.
    One click from the owner starts it. It starts as a side session of this one (`detach_session`
    refuses it), so tell the owner to use "Detach to top level" in the sidebar, or not to archive
    this chat while the successor runs.
  - Otherwise, the paste-ready block is the hand-off. A chip in a git project starts its session in
    a new worktree branch, which breaks the branch rule.
