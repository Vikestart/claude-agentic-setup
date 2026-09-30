# Traps — `~/.claude` tooling

Durable caveats for the global setup: things that cost real time once and would cost it again.
Lifted out of `handover.md` on 2026-09-07 so they survive handover rotation. Update this file, never
prune it.

Each entry says what happens, why it fools you, and what to do instead.

---

## Measurement

**Transcript `usage` is written once per CONTENT BLOCK, not once per API response.**
A response containing a thinking block, a text block and a tool_use block appears as three records,
each repeating the same `usage`. Summing per record inflates every figure by **2.97×**. Wrong numbers
reached `CLAUDE.md` §6 before this was caught.
→ **Dedupe by `requestId`.** `agent_audit.py` does; anything hand-rolled must too.

**`agent_audit.py --summary` walks every project, not the current one.**
Its repeat-read rate is therefore estate-wide (81%), not per-session. Do not compare the two figures
directly or you will report a regression that is only a change of scope.

**Scope-checking matches every tool's input, not just `Read`/`Bash`.**
`--forbidden "*/local/*"` must inspect all tools: `Grep` takes `path` rather than `file_path` and
returns file contents. Missing that produced a false "scope: clean" on the one agent the check was
written for.

---

## Guards and test suites

**`sync_agents_md.py --check` cannot validate a mapping.**
It compares the file to its own generator, so a broken mapping certifies itself as correct. It once
passed a substitution that rewrote the mapping's own description into the meaningless
`Luna→Luna, Terra→Terra, Sol→Sol`.
→ The bold-role-label guard in `render()` is what actually catches that class. Any self-referential
sentence in `CLAUDE.md` has the same hazard: the substitution is blind, so phrase rules about the
model names without using them.

**`unittest` prints `Ran 1 test` even when the loader failed to import the module.**
That string is not evidence a guard executed. Only an `AssertionError` is.
→ When falsifying, require the *right* failure, not merely a red result. `falsify.py` proves the
suite is GREEN on a clean tree first — otherwise "went red" may only mean it could not run.

**A guard that never reads the file cannot fail on it.**
`harness_parity.py`'s global-config check read only `CLAUDE.md` and `AGENTS.md`, so the permission
allowlist in `settings.json` named a retired path for two days while the check printed
"all target the canonical suite". Fixed 2026-09-06 by `check_settings_allowlist()`.
→ When a guard reports clean, confirm what it actually opened.

---

## Config and permissions

**`autoCompactWindow` does not reach a running desktop-app session**, although the docs say settings
reload live and do not list it as restart-only. Tested 2026-09-30 at ~220k: `get_usage` reported
auto-compaction at 97% of 1M both before and after setting 150k in the project's
`settings.local.json`, and no compaction followed; the 400k user-level value, set mid-session, did
not apply either. → The cap was removed that day, then restored at the owner's request the same
evening. A session started after it DOES obey: `get_usage` reported `contextWindow` 400000 at 92%
(~368k), 2026-09-30, app Claude Code 2.1.284. To
read where a session will compact, `get_usage` reports `contextWindow` and `autoCompactsAtPercent`;
their product is the compaction point.
Subagents get their own model's window (1M for Opus and Fable), not the parent's; no setting caps
one agent — the ~250k context hook is the only per-agent limit.
A model cannot trigger compaction: no tool does it, `send_message` refuses the current session, and
`clear_session("self")` is `/clear` (no summary), refused for a session serving Remote Control.

**A stale path in a permission rule fails silently.**
`Bash(python ~/.claude/scripts/audit_all.py *)` did not error when that directory stopped existing —
the rule simply never matched, so every scanner run fell through to a prompt. That reads as ordinary
friction, not as a bug, which is why it survived so long.
→ After moving any tool, grep the permission allowlist as well as the prose docs.

**Effort is not selectable per spawn — only per agent definition.**
The Agent tool takes a `model` but no effort parameter, so a built-in agent type inherits the
SESSION's setting. Fixed 2026-09-25 by `~/.claude/agents/*.md` definitions whose `effort:`
frontmatter sets it per agent (roster in CLAUDE.md §6); a session started before a definition was
added does not see it. Verified live 2026-09-25: a tilspire session at `medium` spawned
`opus-max-executor`, whose transcript records `max` on every message. `effort: max` is silently sent as
`high` if thinking is ever turned off. Measured earlier, in Nebulingo Phase 133: a
roster approved as one agent at `max` and another at `medium` spawned five agents, all at `high`.
→ The effort floor for sensitive work (`high` since 2026-09-25, `max` before) is a precondition to check before spawning, not a note to add
afterwards. Only the owner can raise it, in the app.

**Subagents cache for 5 minutes by default; the main chat for an hour.**
Verified 2026-09-30 from `usage.cache_creation` in transcripts. An agent that pauses longer — a long suite,
a falsify run, a resume by message — writes its whole context again at the cache-write price; one Tilspire
builder spent ~30M that way. → `settings.json` sets `"subagentPromptCacheTtl": "1h"` (Claude Code 2.1.284;
`CLAUDE_CODE_SUBAGENT_PROMPT_CACHE_TTL` overrides it). It is ignored while the subscription is in overage,
so agents fall back to 5 minutes then.

**On Windows, `subprocess` with `shell=True` means cmd.exe, whatever shell the session uses.**
cmd.exe passes single quotes through, so `python -c 'print(1)'` evaluates a string and exits 0 having
done nothing, and `a; b` never runs `b`. The first `quiet.py` ran one-string commands that way; the review
caught it. → Never `shell=True` for a command an agent wrote; `quiet.py --shell` uses Git Bash explicitly.
Killing a Windows process also leaves its children running — use `taskkill /T /F`.

**Backslashes in a Bash-tool heredoc can arrive halved,** even with a quoted `<<'EOF'`: a doubled
backslash written in Python source reached the interpreter as a single one, so `"\\n"` became a real
newline and an anchor never matched (2026-09-30, three times; the first draft of this very entry was
mangled the same way). → For text containing backslashes, use the Edit tool, a script file
written with Write, or — for several exact replacements — a `patch.py` spec written with Write.

**A running session keeps the instructions it started with — and so do its subagents.**
CLAUDE.md and the agent list load once, at session start. A session open while either changes still
follows the old text, cannot spawn a new definition ("Agent type '…' not found"), and hands its
subagents the OLD CLAUDE.md even though the file on disk is new: a reviewer spawned from such a session
on 2026-09-25 quoted the retired Sonnet rule back.
→ After changing either, tell running sessions or start fresh ones; do not trust an old session to follow
the new rules.
Exception seen 2026-09-30 (Claude Code 2.1.284): a session running since ~18:12 was offered two agent
definitions written at ~19:10, announced as "new agent types are now available". Its CLAUDE.md stays
old either way, so the advice stands.

**The desktop app runs its own Claude Code, not the CLI on PATH.**
`claude --version` said 2.1.252 while the app ran 2.1.280 from
`%APPDATA%\Claude\claude-code\<version>\claude.exe`; a review built on the cached 2.1.252 changelog had
to be redone. → Check behaviour against the newest version in that folder.

**Agent limits: what `settings.json` can enforce, and what it cannot** (2.1.280, checked 2026-09-25).
`CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS` (default 20) refuses an Agent-tool spawn past the cap, but
workflow agents never count toward it, and it is skipped under ultracode at xhigh.
`CLAUDE_CODE_WORKFLOW_MAX_CONCURRENT_AGENTS` only QUEUES a workflow's agents (default: cores − 2, max 16).
`CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH` caps nesting for every agent alike (1 = no subagent spawns;
since 2026-09-30 it is 2, for phase leads — see "Nested agents" below). `workflowSizeGuideline` is
advice to the model plus an in-app warning past its size (small = 5), off under ultracode.
→ Nothing caps a workflow's TOTAL agent count; CLAUDE.md §6 is the only limit there.
Settings changes reach a RUNNING session: a `workflowSizeGuideline` change was announced mid-session, and
new Bash commands saw changed `env` values at once. Whether the spawn check itself sees an `env` change
without a restart is unverified — start a new session when it has to be certain.

**Nested agents: a background grandchild reports to the ROOT session, not to its parent.**
Probed 2026-09-30 (Claude Code 2.1.284, depth 2): a background lead that spawned a leaf with
`run_in_background: true` and ended its turn was made to hand back at once ("the harness required a
handback"), and the leaf's result arrived at the main session. The same lead spawning in the
foreground got the result inline — nonce matched, commits made. A subagent's own background Bash
does wake it. Nested transcripts land flat in the root session's `subagents/agent-<id>.jsonl`, so
`context_guard.py` and `agent_audit.py` see them. → Leads spawn their roster in the foreground.

**A `spawn_task` chip session is a side session of the chat that offered it.**
2026-09-30: the handover's chip started its successor with `parentSessionId` set and `detached`
false, and `detach_session` refuses a chip-started session; archiving the parent may take the
successor with it. → "Detach to top level" in the sidebar, or leave the parent unarchived.

**`start_session` / `hand_off_to_session` sit behind a server-side rollout gate, not a setting.**
Found 2026-09-30 in app 2.16120: one feature gate adds both tools to `ccd_session`, and `spawn_task`
is offered only while that gate is off. No setting or app version enables them. Auto mode also
refuses reading how the app evaluates the gate, and that is right: overriding a vendor rollout is
off the table.
→ Wait for the rollout; the handover skill checks with `ToolSearch` at every handover. Until then,
`spawn_task` is the one-click fallback, but only outside git repositories. In a repo, a chip starts
its session in a new worktree branch, while the owner's sessions run in the main checkout.

---

## Windows and shell

**`fnmatch` is case-insensitive on Windows.**
`*/local/*` therefore also matched Windows' own `AppData/Local/Temp`.
→ Path rules use `fnmatchcase`. A case-only match is reported as a warning, not a violation, so the
real thing still fails loudly while the false one stays quiet.

**PowerShell does not expand `~` in a native command's arguments.**
→ All documented commands use `$HOME` with forward slashes, which works in both shells.

**Python's stdout is cp1252 here, not UTF-8.**
Printing transcript text containing `−`, `→` or `⚠` raises `UnicodeEncodeError` mid-script, after
side effects have already happened.
→ `sys.stdout.reconfigure(encoding="utf-8", errors="replace")` at the top of any script that prints
file or transcript content.

**Deleting a linked folder recursively deletes the repo's files.**
`~/.claude/agents`, `hooks`, `.docs` and each `skills/asdev-*` are junctions into
`~/.claude/claude-agentic-setup` (since 2026-09-30). PowerShell `Remove-Item -Recurse`, `rm -rf` on the
link, or Python `shutil.rmtree` walk through the junction and delete the shared files themselves.
→ `os.rmdir` (or `cmd /c rmdir`, no `/s`) removes only the link; `install.py --uninstall` turns every
link back into a real folder.

**A hook whose script is missing blocks every tool call.**
`python "<missing script>"` exits 2, and Claude Code reads exit 2 from a `PreToolUse` hook as "block" —
including the shell call you would use to repair it. → The installer swaps `hooks/` under a temporary
link name and puts the original back on any error, and refuses to merge a shared hook whose script
does not exist.

**`python` in Git Bash can be the Microsoft Store stub.**
On a fresh Windows machine the App execution alias answers `python` with a stub that exits 9009, and a
hook that fails that way is a non-blocking error: the credentials guard silently never runs.
→ `install.py` checks `python --version` inside Git Bash before installing, and afterwards runs the
guard exactly as Claude Code would and requires a refusal.

**Inside a git hook, `git.exe` is three folders deeper.**
Git for Windows puts `mingw64/libexec/git-core` first on PATH for hooks, so anything that finds Git's
root from `shutil.which("git")` by a fixed number of `parent` steps works in a terminal and fails in a
hook. It made every apply-on-pull hook stop with "Git Bash was not found"; the fresh-machine rehearsal
caught it. → Walk all `parents` looking for `bin/bash.exe`.

**Paths through a junction have two spellings.**
`Path(__file__).resolve()` follows the junction into the repo, while `os.path.abspath` keeps the
`~/.claude/...` spelling. `harness_parity.py` located `~/.claude` from its resolved path (it would have
checked the repo instead), and `security_audit.py` compared the two spellings to exempt its own
folder (it flagged its own patterns: 2 false blocking findings). → Find `~/.claude` from `Path.home()`,
and compare paths with `realpath` on both sides.

**Git commands that touch ignored files delete a person's private files.**
Own agents, own hooks and every skill `local/` overlay live inside the repo folder, kept only by
`.gitignore`. `git clean -x`/`-X` and `git stash --all` remove them, and the install backup holds only
the pre-install originals, not later edits. → Never run those in the setup repo (README, "Never").

**Never archive with PowerShell `Compress-Archive`.**
It silently omits every dot-path — `.git/`, `.docs/`, `.env.example`, `.htaccess` all vanish with no
error while the entry count still looks plausible (62 of 183 files).
→ Archive with Python's `zipfile` walking `rglob('*')`, and prove the copy before deleting any
original: on-disk count against `namelist()`, then SHA-256 each entry against its source.

**`~/.claude/.credentials.json` holds the Claude login tokens, and a recursive grep prints them.**
On 2026-09-28 `grep -rn … .` run from `~/.claude` dumped the whole file into a session transcript.
A `Read(~/.claude/.credentials.json)` deny rule in `settings.json` covers the Read, Grep and Glob
tools, but it does not reach Bash or PowerShell unless the sandbox is on, and it is not on here. The `PreToolUse` hook
`~/.claude/hooks/guard_credentials.py` covers the shells: it refuses a command that names the file,
reads it through a wildcard, or searches the home folder or `~/.claude` recursively (grep -r, rg/ag
with `--hidden`, findstr /s, find or Get-ChildItem -Recurse feeding a reader).
→ Search a subfolder (`~/.claude/skills`, `.docs`) or add `--exclude=.credentials.json`. A shell
command cannot even MENTION the file name, heredocs included — write such text with the Edit tool.
The hook stops accidents, not a determined command; the sandbox's `credentials.files` deny is the
airtight option.

---

## Text surgery

**`str.replace("", x)` inserts `x` between every character.**
A missing `-1` guard on `find()` grew `CLAUDE.md` from 21 KB to 4.5 MB. It was recovered only by
splitting on the inserted text.
→ Use the Edit tool for text surgery. When scripting a replacement, assert the anchor is found and
unique before writing anything.

**Read and write in binary when preserving line endings matters.**
Text-mode round-tripping converts CRLF to LF silently. A byte-level `replace` on `open(p,'rb')`
preserves the file exactly.

---

## Skills

**A skill's identity is its FOLDER name, not the `name:` line in `SKILL.md`.**
Tested 2026-09-29: changing only `name:` left the old name in the live skill list. Renaming a skill
therefore moves its folder, and every path into it moves too.
→ In-house skills carry the `asdev-` prefix (`asdev-blueprints`, `-conventions`, `-handover`,
`-orchestrator`, `-planner`, `-release`, `-web-audit`), so they stand apart from third-party skills. A project
file must never repeat a path into `~/.claude` — name the tool and point at the global instructions;
only the local, uncommitted `.git/hooks/pre-commit` may hold the path. Two project AGENTS.md files
still named a copy retired weeks earlier, which is how this rule was found.

**CLAUDE.md holds only what must apply before any skill loads.** Since 2026-09-29 it is a ~15 kB core;
procedures live in the skills it names by path (planning and phase completion, handover,
orchestration, release, audits, conventions), so Codex — which cannot see `~/.claude/skills` — can still open
them. Keep new procedures in a skill and give CLAUDE.md one line saying when to read it.

---

## Related

- [`setup-architecture.md`](setup-architecture.md) — the layout of `~/.claude`, the in-house skills, and the decisions with their reasons.
- `~/.claude/.docs/handover.md` — current state and next steps; links here rather than repeating.
- `asdev-web-audit` skill — the scanner inventory, suite-running rules and the CRLF tool.
- [`setup-repo.md`](setup-repo.md) — the shared repo, the installer, the links and the settings merge.
