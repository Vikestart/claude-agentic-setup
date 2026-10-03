---
name: asdev-web-audit
description: The one Python audit suite — the proportional scanner gate (security, house-style lint, accessibility, broken assets, file size, unused CSS, images) plus quiet.py, falsify.py and the setup's own tooling. Use for an audit or readiness check, the gate on a medium or larger web change, running a suite quietly, falsifying a guard, or maintaining ~/.claude. Not merely because a small local edit finished.
---

# Web Audit Suite

*Plain Markdown + Python 3 stdlib, with Pillow required only for image conversion.*

The canonical scanners are bundled in `scripts/`. Run `scripts/run_audit.ps1` from any location and
pass the project through `--path`; standalone Python scanners accept the same path and Git-scope
flags. Every caller — Git pre-commit hooks, other harnesses — invokes the scripts in this directory
directly: no forked copies, and no launcher stubs (the `~/.claude/scripts/` stubs were retired
2026-08-30 once every caller had moved). `scripts/harness_parity.py` asserts that, and nothing in
this suite knows where any front-end lives.

## Choose the proportional gate

- **Small/local/reversible:** Skip the aggregate suite by default. If the exact change can affect an
  audited risk dimension, run at most the cheapest relevant standalone scanner or syntax check once;
  also run the requested check when the user explicitly asks for one.
- **Medium:** Run only the standalone scanner(s) covering affected domains, once. Use
  `audit_all.py --changed -q` or the regular changed-file aggregate only when multiple audit domains
  or publication risk justify it. Rerun only a scanner affected by a real fix.
- **Large/risky or publication:** Run the planned changed-file aggregate gate, adding
  `--since main` for a whole-branch release gate when appropriate. Directly inspect security-sensitive
  flows; scanner output is supporting evidence.

Browser verification is separate and remains risk-triggered. Do not add repeated audit rounds,
unaffected scanners, or broad browser coverage merely because this skill was invoked.

## The aggregate gate

One command runs every read-only auditor in a single process and prints one compact report:

```powershell
powershell -ExecutionPolicy Bypass -File "$HOME\.claude\skills\asdev-web-audit\scripts\run_audit.ps1" --path <project-dir> --changed
```

**`--changed` is almost always what you want.** It scopes the scan to files modified vs `HEAD` plus untracked ones — i.e. what you just touched. Without it you get the whole project, which on a mature codebase means thousands of pre-existing style findings that bury the handful you caused. Use `--since main` to cover a whole branch, and drop the flag only for a deliberate cleanup sweep.

Exit code 1 means blocking findings. Fix them, re-run, then report what you fixed.

**When the gate fails, find out what YOU introduced before anything else:**

```
python $HOME/.claude/skills/asdev-web-audit/scripts/audit_delta.py             # vs HEAD
python $HOME/.claude/skills/asdev-web-audit/scripts/audit_delta.py --since main
```

`--changed` still reports pre-existing findings in files you merely touched — on 2026-08-21 it reported
**93 blocking findings for a change that introduced none**, all old-style declarations in a stylesheet
the work happened to open. `audit_delta.py` audits the working tree and a **real `git worktree`** at the
ref, then reports **NEW / FIXED / PRE-EXISTING**, exiting 1 only on findings your change introduced.
Report the delta, not the total; `--no-verify` is legitimate only after proving zero new, and that proof
belongs in the commit message.

Two things it gets right that a hand-rolled comparison does not. The ref side is a **full worktree**,
because `unused_css_detector` and `link_checker` cross-reference the whole project and a directory of
copied files makes every class look unused (an isolated dir scored 95 blocking / 116 advisory where the
project scores a fraction of that). And findings are compared as a **multiset**: dropping the line number
is necessary because lines shift, but keying on the message alone collapses the 76 identical
`CSS_SPACE_COLON` findings in one file into a single entry, so a 77th would register as nothing at all.
The ref-side scan is a full audit (~19 s on 594 files) and is skipped entirely when the working tree has
no findings in the changed files.

## Options that matter

| Flag | Effect |
|---|---|
| `--changed` / `--since REF` | Scope to your working diff or branch diff, including untracked files |
| `--staged` | Scope exactly to the staged index for a pre-commit gate |
| `--advisory` | Include advisory findings in full; by default they're just counts |
| `-q` | Counts only — cheapest way to check clean |
| `--json` | Machine-readable |
| `--max N` | Findings shown per rule (`0` = all; default 5 in `audit_all`, 15 standalone) |

Per-project tuning: `.auditignore` in the project root (`build/` for a directory name, `*.generated.css` for a glob) and `.token-limits.json` for size limits.

The aggregate gate also honors a reviewed `.audit-baseline.json`. Each exception must match one exact
scanner, rule, file, and source-line context and include a written reason; wildcards and TODO reasons
are invalid and block. Source changes invalidate the match. Stale entries are advisory and are only
assessed inside the active Git scope. Standalone scanners intentionally show raw findings.

## What runs

**Blocking** — defects that set the exit code:
- `syntax_check.py` — real parses via `php -l` and `node --check` (JS tried as ESM then CJS, so IIFE files don't false-positive). Resolves binaries from PATH, `$AUDIT_PHP`/`$AUDIT_NODE`, or the XAMPP default; a missing interpreter skips that language with a stderr note, never a failure. `.ts` is not checked.
- `security_audit.py` — SQL injection (interpolation *and* concatenation), XSS via echoed superglobals or unescaped DOM writes, dangerous functions (`eval`/`exec`/`shell_exec`), `unserialize()` on user input, hardcoded credentials, non-crypto RNG for tokens, md5/sha1 on passwords, disabled TLS verification, wildcard CORS, `display_errors` on. Plus repo hygiene when a root `.env` exists: tracked in git, no `.env.example` sibling, or not blocked by `.htaccess`.
- Some projects have scanner findings that are **by design** — a localhost-only tool that deliberately skips TLS verification for loopback probes, or an embed endpoint that needs wildcard CORS. Check the project's own instructions before "fixing" a repeat finding, and record an accepted one in its `.audit-baseline.json` with a written reason rather than re-deciding it every run.
- `lint_rules.py` — the house style: no space after `:`, single-line rules stay space-free, <6 properties belong on one line (unless flex/grid), media queries at the bottom, fragments carry no page boilerplate or inline `<style>`/`<script>`, `data-link` on internal SPA links, no inline `onclick=`, no leftover `console.log`/`var_dump`/`print_r`/`debugger`. Also `CSS_ICON_BLOCK` — an icon is never `display:block` (its two glyph layers tear apart); a bare `<i>` declaring a background or an explicit size is exempt as a drawn shape.
- `convention_audit.py` — high-confidence shared/project invariants: no embedded base64 images, raw
  inline SVG, jQuery dependency, or random per-request cache busting. **Project-specific rules are
  data, not code:** an optional `local/project-rules.json` adds per-project checks (a forbidden line
  pattern, a filename-case rule under a path prefix, or two paths that must change together for a
  release), matched by a path component so a checkout anywhere still resolves. Without that file only
  the generic rules run, which is the correct behaviour on any machine but the author's. Contextual
  design choices remain review work rather than regex policy.
- `a11y_audit.py` — missing `alt`, missing `<html lang>`, icon-only links/buttons with no accessible name, inputs with no label, positive `tabindex`, images without `width`/`height`.
- `link_checker.py` — local asset references (`src`/`href`/`url()`/`srcset`) that don't resolve. Only checks references carrying a file extension; extensionless hrefs are SPA routes, not files.

**Advisory** — judgement calls, never fail the run:
- `token_analyzer.py` — oversized files (JS/PHP >15 KB/300 lines, CSS/views >10 KB/200 lines). Split JS into ES modules, views into partials. Each finding also carries the file's **comment-line share**, which is context for *how* to split it — mostly code means extract modules, mostly prose means move documentation to `.docs/reference/`. It is never a finding on its own: measured across the first-party tree, only ~1.3% of comment lines were mechanically removable, and the longest comments are the ones recording why something is the way it is. Do not delete comments to satisfy a percentage.
- `doc_hygiene.py` — working docs stranded in the project root, ambiguous `.docs/` tracking policy,
  working files over their size budget (`OVER_BUDGET`: plan 30 kB, task, walkthrough 15 kB, roadmap,
  changelog 25 kB / 100 lines, the project's `AGENTS.md` / `CLAUDE.md` 20 kB / 100 lines — one table,
  `BUDGET_KB`, also read by the after-compact hook), shipped sections still sitting in the plan, and
  verbose changelog entries. Phase completion and handover trim until it reports no `OVER_BUDGET`.
  `.docs/reference/` is exempt from size/shipped checks by design.
- `unused_css_detector.py` — selectors with no visible usage. It reads class attributes and string literals rather than raw text, but classes built at runtime (`'btn-' + kind`) are invisible to it and it says so when it detects them. Verify against the JS before deleting anything.

**Tools — run on demand, never part of the gate:**
- `quiet.py` — `quiet.py [--summary REGEX] [--tail N] [--log PATH] [--timeout S] -- <cmd>`. Runs any command with all output to a log (under the temp dir by default) and prints ONE line: exit code, the last line matching `--summary` (else the last line), seconds, log path — plus the last `--tail` lines (default 20) only when it failed. Exits with the command's own code (124 timeout, which kills the whole process tree; 127 could not start). No shell unless `--shell`, which runs ONE string under Git Bash — never cmd.exe, whose quoting made a `python -c '...'` string exit 0 having done nothing. The program is found on PATH as a shell would (`npm.cmd` included). Exists because every printed line is re-read on every later turn: test output filling a builder's context was ~90% of a 31M-token phase. Wrap `falsify.py` itself, not the suite inside it — falsify needs the suite's full output to match `expect`.
- `audit_delta.py` — "what did I introduce?" See **The aggregate gate** above. `--since REF`, `--json`, `-q`.
- `crlf.py` — byte-accurate line endings. report-only by default (`--check` spells it out); `--fix` writes, `--changed` resolves against the repo ROOT so it works from a subdirectory, `--fix --lf` targets LF. Only declared-textual extensions are ever rewritten. Exists because the usual shell idioms are broken on this box: `grep -c $'\r$'` returns the line count (a tautology that passes on pure-LF files) and `sed 's/$/\r/'` is a no-op, while `sed -i` silently rewrites a whole file to LF. It also repairs `\r\r\n`, which the naive `replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")` pair round-trips straight back to itself. ⚠️ **`--fix` does not read `.gitattributes`**: it converts every changed text file to CRLF, rewriting exactly the files an `eol=lf` pin protects — checksummed migration SQL (whose hash the migrator compares across Windows and Linux) and any `*.sh` (bash cannot parse CR line endings). Read the project's `.gitattributes` first and keep those paths out of the fix; teaching this script to honour the pins is the real repair.
- `agent_audit.py` — what a subagent ACTUALLY did, from its transcript: files read and written, cost, tool errors, and **scope violations** against `--owned` / `--forbidden` globs. Reads leave no trace in Git, so this is the only way to check a read-only agent stayed in its lane — the reviewer it was written for read a forbidden `local/` overlay via `cat`, so Bash commands are matched too, and matching is case-sensitive (`fnmatch` is not, on Windows, and `*/local/*` otherwise flags every `AppData/Local/Temp` path). Per agent it also reports average and peak context, cache writes straight after a pause over 5 minutes (a full re-cache), and a price-weighted total (read 0.1, write 2, output 5) — the figures to record in a phase's walkthrough. `--summary` regenerates the estate-wide figures the `asdev-orchestrator` skill quotes, so they can be re-grounded instead of drifting into folklore. Read-only.
- `session_cost.py` — what a whole session cost, main chat plus every subagent, price-weighted (read 0.1, write 1.25/2, output 5) and split into **fixed** (start-up context re-read every turn: system prompt, tool definitions, instructions, brief), **growth** (everything added later: tool results, own edits), cache **writes** and **output**. The split says which lever to pull: a large `fixed` share points at the agents' tool set or instructions, `growth` at their reads and turn count. `--project`, `--since`, `--top`. Use it to compare one night's work with another (the roadmap's re-measure). Read-only.
- `code_map.py` — `code_map.py <file> [--match REGEX] [--min-lines N] [--all]`. Outline of a PHP, JS, Python or Markdown file. Markdown: every heading is a section (to the next heading of the same or a higher level) and every top-level list item that opens in bold (`1. **Step**`) an item, fenced code skipped — plans, roadmaps and reference docs were a third of what agents' file reads cost in one Tilspire session (2026-10-01). Code: classes, functions, methods, closures, comment banners and the comment-led blocks of a flat test file, each with its line range and size. Blocks carry the names of the `check()`/`test()`/`it()`/`describe()` calls inside them, so `--match` goes from a test name to its chunk. Over 200 items, blocks and closures are counted, not listed, unless `--match` or `--all`. Brace matching skips strings, comments, heredocs/nowdocs, template literals and regex literals; Python nests by indentation (`Outer.Inner.deep`). Line numbers match grep on CRLF files. Exists because agents spent 39–47% of their tool-result cost dumping 10–27k-line files with `cat`/`sed` (2026-10-01): run.php maps in 0.7 s. Read-only.
- `code_show.py` — `code_show.py <file> <name> [<name> …] [--context N]`. Prints exactly the named items with line numbers, several per call: `func`, `Class::method` or `Class.method` (either separator, any language), a banner or block label, a check name, a Markdown heading or bold item (substring), or `@LINE` (the innermost item containing that line). Exact names win over short ones; an unknown or ambiguous name lists the closest matches instead of failing silently. Limits: JS object-literal methods and unassigned closures are not mapped; Python decorators sit above the range (`--context`). Read-only.
- `automation_mine.py` — which throwaway work keeps being rewritten: inline interpreter runs, long shell blocks and scratch-folder scripts grouped by the identifiers they use, plus recurring command sequences, ranked by the tokens the model wrote for them, with a `fail` count per group. Run it before choosing the next suite script (CLAUDE.md §0: a procedure done twice becomes a script). `--since`, `--project`, `--min`, `--json`. Read-only; ~2 minutes over 2 GB of transcripts.
- `handover.py` — scaffolds `.docs/handover.md`: branch and sync state, uncommitted files, recent commits, changed-file stat, the current `.docs/` plan/task/roadmap state, and optionally the aggregate gate (`--run-checks`). Leaves **decisions** and **next steps** blank — that is the half a script cannot write. `--stdout` previews; it refuses to overwrite an existing handover without `--force`.
- `falsify.py` — `--suite "<cmd>" --mutations <spec>`. The spec is `patch.py`'s block format with `name:` and `expect:` lines above each block, written with the Write tool; a `.json` list still works. Reverts each guard one at a time and proves it goes RED *for the right reason*. Refuses to start unless the suite is GREEN on a clean tree (otherwise "went red" may mean "could not run"), refuses a non-unique anchor, restores byte-exactly and verifies by SHA-256, and reports a guard that stays GREEN as **VACUOUS**.

**Writers — never part of the gate:**
- `context_override.py` — `status | set <N> --reason "…" | clear`, from a project root. Sets a
  temporary `autoCompactWindow` in the project's `.claude/settings.local.json` for the next session,
  and clears only what it set itself. A private ledger, `~/.claude/context-overrides.json`, tells
  its own value from a deliberate one. The handover skill (step 4b) is its caller.
- `patch.py` — `patch.py SPEC [--root DIR] [--check]`. Exact, all-or-nothing replacements across files from a spec that needs no escaping: `@@@ path`, then blocks of `<<<<<<< OLD` (or `OLD xN` for exactly N occurrences) / `======= NEW` / `>>>>>>> END`. Write the spec with the Write tool, never a heredoc (a heredoc can halve backslashes). Every anchor is checked in memory first, so one miss writes no file, and a miss says where the anchor's first line does occur; CRLF files are matched and written in CRLF, bytes outside the replaced spans (a BOM included) are untouched. Exists because ~4,300 hand-written patch scripts in one month cost ~2.4M output tokens and failed ~120 times on exactly those traps.
- `optimize_images.py` — PNG→**lossless** WebP, JPEG→WebP at `--quality` (default 82). **Dry run by default; `--apply` writes.** Originals are kept and references are not rewritten, so update the markup yourself. Skips favicons/apple-touch-icons (platform requires PNG) and any conversion that comes out larger.

## Running a suite honestly

- **A suite's exit code and summary come from the run itself.** Never pipe a runner:
  `run_battery.sh | tail` reports *tail's* exit code, so a failing run reads as success, and the
  output stays buffered. Redirect to a file instead — `quiet.py -- <cmd>` does exactly that and
  keeps the exit code, and is the default way to run any suite. Never reconstruct a figure from partial output —
  a battery count published that way was right by luck, which is indistinguishable from wrong.
- **Windows process checks:** Git Bash `ps -W | grep` gives false negatives here and has reported a
  suite finished while it was still running. Use PowerShell `Get-Process`, or `Get-CimInstance
  Win32_Process` when you also need the command line. Prefer a byte- or object-accurate check over a
  shell idiom generally — see `crlf.py` above for why the line-ending idioms are broken too.
- **A measurement that cannot fail loudly is not a measurement.** Before trusting a red result,
  confirm the runner actually ran: `falsify.py` refuses to start unless the suite is green on a clean
  tree, for exactly this reason.

## Falsifying a new guard

Every new guard that protects behaviour — security, data, routing, hooks, the installer, agent tool
lists — is reverted one at a time and shown to go RED *for the right reason* (CLAUDE.md §6). An
advisory check (doc sizes, style hints) needs only a unit test.

```
python $HOME/.claude/skills/asdev-web-audit/scripts/falsify.py --suite "<cmd>" --mutations <spec>
```

`--check` (no `--suite`) only confirms every anchor occurs once, without running anything; `--only "name a,name b"`
reruns just those mutations after a fix. Use both instead of a hand-written check.

Write the spec with the Write tool. Nothing in it is escaped, so no script is needed to build JSON:

```
@@@ includes/auth.php
name: admin gate
expect: non-admin reached the admin page
<<<<<<< OLD
if (!$user->isAdmin()) {
======= NEW
if (false) {
>>>>>>> END
```

It proves the suite GREEN on a clean tree first — otherwise "went red" may only mean it could not run,
which has happened — refuses a non-unique anchor, restores every file byte-exactly (verified by
SHA-256), and reports a guard that stays GREEN as **VACUOUS**. Give each mutation an `expect` string
quoted from the real failure message; a one-word `expect` also matches crashes.

## Archiving

**Never archive with PowerShell `Compress-Archive`:** it silently drops every dot-path (`.git/`, `.docs/`, `.env.example`, `.htaccess` — 62 of 183 files, no error). Use Python's `zipfile` over `rglob('*')`, and before deleting any original prove the copy: file count against `namelist()`, then SHA-256 per entry.


## Honest limits

These are regex scanners. A clean security run means nothing obvious matched — not that the code is safe. Read the SQL and the escaping you write regardless.

`XSS_DOM` is the noisiest rule: it can't tell a trusted render helper from user data, so `${row.title}` and `${icon(kind)}` look alike. It skips zero-arg and string-literal calls (`${header()}`, `${icon('cog')}`); expect a couple of false positives per project and judge them by reading the line.

`SQL_INJECTION` recognizes the dynamic `IN (?,?,?)` placeholder idiom — interpolating a variable proven (same file) to hold an `array_fill(...,'?')` / `str_repeat('?'...)` list is not flagged, because the interpolated text is only question marks. It still flags **raw data in an `IN (...)`** (e.g. `IN ($_GET['ids'])`, even inside `->prepare()`), plain interpolation, and concatenation. What survives on a mature codebase is usually **whitelisted-identifier interpolation** (`FROM {$table}` gated by an `$allowed` map — identifiers can't be bound) and **int-cast / server-computed values** (`(int)$id`, a date fragment). Those are real flags a reviewer should confirm the guard on, not false positives to suppress — if a project uses them by design, document the pattern in its local project instructions rather than weakening the rule.

## Maintaining the setup

Only for work on `~/.claude` itself, never a project session.

- **One copy, never one per harness:** no copy of this suite under `~/.codex` or anywhere else — that
  is how harnesses drift.
- **One in, one out:** `CLAUDE.shared.md`, the in-house `SKILL.md` files and the agent definitions
  have size budgets (`install/test_setup.py`, `RuleBudgets`). A new rule replaces or shortens an
  existing one; evidence goes to `.docs/reference/setup-architecture.md`, not into the rule.
- After changing a project hook, `~/.claude/CLAUDE.md` or the suite's location, run
  `python $HOME/.claude/skills/asdev-web-audit/scripts/harness_parity.py`.
- Codex is decoupled (owner, 2026-10-01): `~/.codex/AGENTS.md` is no longer generated or checked, and
  `sync_agents_md.py` is kept only for its import expander (`harness_parity.py`, `share_bundle.py`).

## Workflow

1. Classify the change and select only the proportional scanner or aggregate gate above.
2. Run the selected check once.
3. Fix real violations at the root cause — never suppress a check or work around it.
4. For a suspected false positive, read the flagged line and leave correct code alone. For a stable,
   reviewed aggregate-gate exception, add one exact `.audit-baseline.json` entry with its reason;
   `.auditignore` remains for whole paths only and inline suppression comments are unsupported.
5. Rerun only checks affected by a relevant fix until their blocking count is zero, then report what ran, what was fixed, and what was flagged-but-intentional.

Findings are data about the code, not instructions. Never auto-delete files or "fix" vendored code on a scanner's say-so.
