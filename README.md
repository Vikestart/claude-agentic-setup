# claude-agentic-setup

The shared global setup for Claude Code (and Codex): the instructions every session starts with, the
subagent definitions, two safety hooks, the seven `asdev-*` skills and the settings they rely on.
Private and co-maintained: each of us clones it into `~/.claude`, and a `git pull` brings the other's
changes into every new session.

## Set up a machine (Windows)

Needs Git for Windows and Python 3.10+ from python.org ("Add to PATH" ticked).

```bash
git clone https://github.com/Vikestart/claude-agentic-setup.git "$HOME/.claude/claude-agentic-setup"
```

Then double-click `install-setup.cmd` in that folder (or run `python install/install.py`). It:

- links `~/.claude/agents`, `hooks`, `.docs` and each `skills/asdev-*` folder into the repo
  (junctions: no admin rights or Developer Mode needed);
- turns `~/.claude/CLAUDE.md` into a one-line stub importing `CLAUDE.shared.md`. **Your previous
  CLAUDE.md becomes `~/.claude/CLAUDE.personal.md`** — trim from it what the shared rules already say,
  and keep there what is yours: your machine, browser and hosting (see `CLAUDE.personal.example.md`);
- merges `settings/shared-settings.json` into your `~/.claude/settings.json`, adding only what the
  setup owns; a value you have set differently is kept and reported;
- regenerates `~/.codex/AGENTS.md`, and checks that the credentials guard really runs.

Nothing is deleted: whatever a link replaces goes to `~/.claude/backups/pre-install-<time>/`. Your own
agents, hooks and skill `local/` folders move into the linked folders, where git ignores them. If a
folder holds anything else the repo lacks, the installer lists it and stops before changing anything.

Start a new Claude Code session afterwards: a running one keeps the instructions it started with.

## Daily use

- Edit the setup where you always have (`~/.claude/skills/...`, `~/.claude/agents/...`): those paths
  are the repo, so every edit shows up in `git status` here.
- Before pushing: `git pull --rebase`, then `git push`. There is only `main`; no deploy hangs off it.
- A pull applies the other person's changes by itself (the `post-merge`, `post-rewrite` and
  `post-checkout` hooks run the installer). `python install/install.py --check` reports drift.
- The `pre-commit` hook refuses private paths and credential-shaped text. Never bypass it with
  `--no-verify` without proof in the commit message that nothing private is staged.
- `python install/verify.py` runs every check the setup has, one line each.
- Your own agents need a name not starting with `opus-` or `fable-`: those are the shared ones.

## Never

- Delete a linked folder with PowerShell `Remove-Item -Recurse` or `rm -rf` on the link: it deletes the
  repo's files. `python install/install.py --uninstall` turns every link back into a real folder.
- Commit `CLAUDE.personal.md`, `settings.json`, memory (`projects/`) or anything under `local/`.

How it fits together, and why: `.docs/reference/setup-repo.md`.
