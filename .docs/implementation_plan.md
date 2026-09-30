# Implementation plan — the global setup in a shared private repo

**Goal:** the setup lives in the private GitHub repo `Vikestart/claude-agentic-setup`, maintained by
the owner and their partner (Windows, co-maintainer). Each machine clones it and runs one installer.
After that, every edit to the setup is a git change, and each person gets the other's changes with
`git pull`. Memory, transcripts, credentials, `backups/` and `local/` overlays stay private.

**Decided:** link everything, copy nothing; the repo sits inside `~/.claude`; `~/.claude/CLAUDE.md`
is a one-line import stub, so nobody needs Developer Mode or admin rights; `local/` stays out of git
(2026-09-28). Partner on Windows, co-maintainer; a per-person file for the machine bullets; a shared
settings fragment merged additively; the zip bundle stays for one-off sharing (2026-09-30).
Replaces `proposals/setup-repo-migration.md` (now in `backups/`): it predated the `asdev-*` rename,
listed 3 skills instead of 7, and had no context hook.

**Found while planning:** the empty repo exists on GitHub (private, no commits), with a local clone
at `~/.claude/claude-agentic-setup` (no commits). Two scripts break when reached through a link:
`harness_parity.py` finds `~/.claude` from its own *resolved* path, so it would check the repo folder
instead; `security_audit.py:306` exempts its own folder by comparing path spellings, so it would scan
itself and report 2 false blocking findings (reproduced by the plan review).

## Repo layout

| Repo path | Reached from | How |
|---|---|---|
| `CLAUDE.shared.md` | `~/.claude/CLAUDE.md` | a stub with one line: `@claude-agentic-setup/CLAUDE.shared.md` (not named `CLAUDE.md`, so a session opened in the repo does not load it twice) |
| `CLAUDE.personal.example.md` | — | template for `~/.claude/CLAUDE.personal.md` (outside the repo) |
| `agents/` (12 definitions) | `~/.claude/agents` | junction; git tracks only `opus-*` and `fable-*` definitions, so a person's own agents sit in the folder untracked and private (per-file hard links would break at the first pull, which replaces files) |
| `hooks/` (2 hooks + their tests) | `~/.claude/hooks` | junction |
| `.docs/` | `~/.claude/.docs` | junction |
| `skills/asdev-*` (all 7) | `~/.claude/skills/<name>` | one junction each |
| `settings/shared-settings.json` | merged into `~/.claude/settings.json` | installer |
| `githooks/pre-commit`, `post-merge`, `post-rewrite` | `core.hooksPath`, set by the installer | — |
| `install/install.py`, `install/test_setup.py`, `install-setup.cmd`, `README.md`, `.gitignore`, `.gitattributes` | — | — |

- **Stays out:** the six third-party skills, `projects/` (memory and transcripts), `settings.json`
  itself, the login tokens, caches, `backups/`, `proposals/`, `plugins/`, every `local/` overlay.
- **`.gitignore`:** `skills/*/local/`, `__pycache__/`, `*.pyc`, `.sandbox/`, and `agents/*` except
  `opus-*.md` and `fable-*.md`.
- **`.gitattributes`:** `* -text` — git keeps bytes exactly, whatever either person's `core.autocrlf`.
- **The per-person file.** CLAUDE.md §2's three machine bullets (XAMPP, Edge, Plesk) move to
  `~/.claude/CLAUDE.personal.md`. In the shared file, a line `@~/.claude/CLAUDE.personal.md` takes
  their place and the italic "replace these bullets" note goes. "Never push directly to `main`" moves
  from the Plesk bullet into the shared Branches bullet, naming the setup repo as the exception.
- **The settings fragment** holds what the setup owns: the two `env` agent caps,
  `subagentPromptCacheTtl`, `workflowSizeGuideline`, the 14 `asdev-web-audit` allow rules, the
  credentials deny rule, and both hooks. The installer records what it last applied in
  `~/.claude/setup-state.json` (private). A missing entry is added; a value is replaced only while it
  still equals what was last applied, so the fragment's own changes land and a person's deliberate
  override never does (`--check` reports it). A `retire` list removes exact entries the fragment added.
- **Git hooks, tracked, so both people get them.** `pre-commit` refuses a staged path outside the
  layout (any `local/`, `.env`, the login-token file) and content matching a full token shape (not a
  bare prefix, so docs that mention the prefixes pass). `post-merge` and `post-rewrite` (a rebasing
  pull runs only the latter) run the installer in apply mode and regenerate `~/.codex/AGENTS.md`, so
  a pull applies the other person's changes; `settings.json` is backed up whenever it changes.

## Installer (`install-setup.cmd` → `install/install.py`)

- **Preflight:** Python and git run; the repo is at `~/.claude/claude-agentic-setup`; the exact hook
  command (`python "$HOME/.claude/hooks/…"`) runs in Git Bash — a Microsoft Store `python` stub would
  otherwise turn the credentials guard off without a word.
- **Safe swap, per link:** already right → skip. A person's own agent definitions → moved into the
  linked `agents/`, where git ignores them. Any other folder holding a file the repo lacks → list it
  and stop; nothing is moved. Otherwise: create the link under a temporary name, move the original to
  `~/.claude/backups/pre-install-<timestamp>/`, rename the link into place; on any error, put the
  original back. A missing `hooks` folder blocks every shell call (the hook exits 2), so this order matters.
- **CLAUDE.md:** identical to the shared file → replace with the stub. Different and no personal file
  yet (the partner's own rules) → it becomes `CLAUDE.personal.md`, and the installer says so. Personal
  file still missing → copy the example.
- **Settings:** back up `settings.json`, then merge the fragment. Set `core.hooksPath`.
- **Afterwards:** `sync_agents_md.py`, `harness_parity.py`, and one probe command naming the
  login-token file, which the guard must refuse.
- **`--check`** reports drift and changes nothing; a second run changes nothing.
- **`--uninstall`** removes links with `os.rmdir`/unlink (never a recursive delete: PowerShell's
  `Remove-Item -Recurse` on a junction deletes the repo's files) and replaces each with a real copy
  of what it shows, so no edit made since install is lost; CLAUDE.md gets the shared text back. The
  pre-install originals stay in the backup folder. *(Changed while building, 2026-09-30: restoring the
  backups would have thrown away every edit made through the links since install.)*

## Steps

0. **Baseline.** Run every check below, the `audit_all.py` gate included, and keep each summary line
   as the expected value — nothing is hardcoded.
1. **Tools work through links and imports.** `sync_agents_md.py` inlines whole-line `@path` imports,
   recursively, and fails loudly on a missing file (an `@` inside prose or code is never an import);
   its header names the shared file as the one to edit. `harness_parity.py` takes `~/.claude` from
   `Path.home()` and reads CLAUDE.md through the same expansion. `security_audit.py` compares
   `realpath` on both sides. `share_bundle.py` bundles the shared file, the example, and an AGENTS.md
   built from those two — never the personal file — and its README stops telling recipients to
   replace §2's bullets.
2. **Split CLAUDE.md** as above; write the owner's `CLAUDE.personal.md`; regenerate AGENTS.md. Take
   the SHA-256 baseline of every file that will move **now**, after the intended edits.
3. **Fill the repo:** copy (not move) the files in; add the installer, its tests, fragment, hooks,
   README, `.gitignore`, `.gitattributes`. Compare hashes with step 2.
4. **Private-data sweep** of the repo tree: the token shapes, plus a read for hostnames, IPs, emails
   and `.env` values; `git status --ignored` lists every `local/` as ignored. Run `pre-commit` on the
   fully staged tree. Then a **local commit, not pushed** — a restore point, and what step 5 clones.
5. **Rehearse a fresh machine:** clone that commit into a scratch home (`HOME`/`USERPROFILE` pointed
   there), seeded with a stand-in CLAUDE.md, an agent of its own and a hook of its own; run the
   installer, `--check`, a second run, then `--uninstall`, and confirm the scratch home is back as it was.
6. **Install on this machine.** Just before each swap, compare the live original with its repo copy
   byte for byte and stop on any difference — an edit made after step 3 is never parked in backups.
7. **Docs.** New `.docs/reference/setup-repo.md` (layout, installer, merge rules, a new machine, the
   co-maintainer workflow, uninstall); update `setup-architecture.md`, and add to `traps.md` the
   junction-delete and Store-`python` traps. Shared docs cite two private memories
   (`agent-model-effort-policy`, `measuring-agent-cost`) the partner cannot see: fold their durable
   facts into `.docs/reference/` and repoint the citations. Update the `global-claude-setup` memory.
   A paste-ready FYI for chats already running.
8. **Final review** of the repo tree before anything leaves the machine (see Subagents); fix findings.
9. **Sweep again** (step 4's checks, `pre-commit` included) over everything steps 7–8 wrote, then
   commit and push to `origin main`. Approving this plan approves that push.
10. **Partner access:** you add them as a collaborator (open decision 1); their steps are in the README.

## Verification

- **Nothing changed through the links:** every file hashes as in the step-2 baseline, except the
  docs step 7 edits on purpose.
- **AGENTS.md is complete:** the regenerated file differs from step 0's only by the removed italic
  note and the moved "never push to `main`" clause — proves the import expansion lost nothing.
- **All checks match the step-0 baseline:** `asdev-web-audit` self-test, `asdev-blueprints`
  self-test, `harness_parity.py` clean, `sync_agents_md.py --check`, both hook test suites, and the
  `audit_all.py` gate — run from the repo path and from the linked path.
- **`install/test_setup.py`** (scratch home, a scratch repo with the hooks, an import fixture,
  `harness_parity.py` through a link) passes, and is the suite `falsify.py` mutates. RED for the right
  reason on each: a missing personal file fails `sync_agents_md.py`; a planted token (built by string
  concatenation, so no real-shaped token sits in any file) and a staged `local/` file are refused by
  `pre-commit`; the merge overwrites a person's own value; the swap loses the original on an error;
  `harness_parity.py` through the junction checks the repo folder. Mutations kept in
  `skills/asdev-web-audit/scripts/falsify/setup-repo.json`.
- **The rehearsal** (step 5) installs, re-runs cleanly and uninstalls back to the starting state, and
  keeps the stand-in's own agent, hook and rules.
- **The credentials guard runs** after install: the probe command naming the token file is refused.
- **A fresh session sees it:** a new Code session (the desktop's `claude.exe -p` if its login works,
  otherwise one you open with a probe prompt I give you) lists the 12 agents and 7 `asdev-*` skills,
  and quotes one rule found only in the shared file and one found only in the personal file —
  proving both import levels load.

## Subagents

This is sensitive work (secrets leaving the machine, the setup's core architecture), so its floor is
`high`; this session is below that, so the build goes to agents. Two sequential builders, because the
work would pass ~150 tool calls.

| Role | Definition · model | Owns | Checks it runs |
|---|---|---|---|
| Plan review (done) | `opus-xhigh-reviewer` · Opus 5.5 | read-only | — |
| Builder A: steps 0–4 | `opus-high-executor` · Opus 5.5 | the four scripts, CLAUDE.md, the personal file, the repo tree | baseline, tests, falsify, sweep, local commit |
| Builder B: steps 5–7 | `opus-high-executor` · Opus 5.5 | the repo tree, `~/.claude` links, `settings.json`, docs | rehearsal, install, all checks |
| Final review (step 8) | `fable-xhigh-reviewer` · Fable 5.1 | read-only | — |

Up to one fresh correction agent per builder: 6 at most. I keep step 9 (sweep, commit, push),
step 10, verifying each hand-back, and the memory update.

## Release

Local only, then the push in step 9. There is no staging or production: each machine takes a change
when its owner pulls.

## Residual risks

- **Chats already open** keep the rules they started with; the files are identical, only reached
  through links.
- **A bad change travels by pull** and is applied by the pull hooks. Rollback is `git revert` plus a
  pull; `--uninstall` and the step-6 backups remain until you release them.
- **Two people editing `handover.md` or `roadmap.md`** will sometimes conflict; resolved by hand,
  never by discarding either side.
- **A third-party skill updater** cannot touch the repo: only `asdev-*` folders are links.
- **If Claude Code will not load an import from inside an imported file,** the probe catches it; the
  fallback is a stub that imports both files.
- **A person's own agent named `opus-*` or `fable-*`** would be tracked and shared; the README says
  to pick another prefix, and `pre-commit` lists new agent files for a second look.

## Open decisions

1. **Partner access.** Recommended: you add them in GitHub → Settings → Collaborators. Or give me
   their GitHub username and approve a `gh` invite, which sends them an email in your name.
2. **Branching in the setup repo.** Recommended: `main` only, direct pushes, `git pull --rebase`
   before pushing, the `pre-commit` hook as the gate — no deploy hangs off `main` here. The
   alternative is a PR for every change, reviewed by the other person.
3. **Pull applies changes automatically.** Recommended: yes — the pull hooks run the installer, so
   the other person's settings and links land without a second step. The alternative is that a pull
   only reports drift, and each person runs `install-setup.cmd` themselves.
