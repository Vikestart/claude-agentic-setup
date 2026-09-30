"""One-copy self-check for the asdev-web-audit suite.

The canonical scanners and skill documents live in `~/.claude/skills/` (`asdev-web-audit` and
`asdev-conventions`). Every caller — the per-repo Git pre-commit hooks, the global config, and any
other harness such as Codex — must point at THAT copy. This check exists because the front-ends
forked once (June–August 2026) and silently ran different security gates.

⚠️ The historical launcher stubs in `~/.claude/scripts/` were retired on 2026-08-30: every caller had
already moved to the skill path, so 15 shims were verifying nothing. This script therefore now
asserts the inverse of what it once did — that NO rival copy of a scanner exists anywhere, including
in that folder.

    python $HOME/.claude/skills/asdev-web-audit/scripts/harness_parity.py

Run it after changing a hook, the global config, or the canonical script location.

Portability: the projects root is read from `PROJECTS_ROOT`, falling back to the first of a few
common locations that exists, so this runs on a machine that is not the author's.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

from sync_agents_md import expand_imports

# From the home folder, never from this file's resolved path: the skill is a junction into the setup
# repo, so resolving __file__ lands in ~/.claude/claude-agentic-setup and every check below would
# look at the repo instead of what sessions load.
HOME_ROOT = Path.home() / ".claude"
SKILLS_ROOT = HOME_ROOT / "skills"
CANONICAL_SCRIPTS = SKILLS_ROOT / "asdev-web-audit" / "scripts"
CANONICAL_SKILLS = ["asdev-web-audit", "asdev-conventions"]

SCANNERS = [
    "a11y_audit.py", "audit_all.py", "convention_audit.py", "doc_hygiene.py",
    "link_checker.py", "lint_rules.py", "optimize_images.py",
    "security_audit.py", "syntax_check.py", "token_analyzer.py",
    "unused_css_detector.py", "audit_delta.py", "crlf.py", "falsify.py",
    "agent_audit.py", "handover.py", "automation_mine.py",
]
HOOK_LAUNCHERS = ["run_audit.sh", "run_audit.ps1"]

# Places a rival copy has appeared before, or plausibly would. A scanner FILENAME found in any of
# these (outside the canonical directory) means two harnesses can run different gate code.
RIVAL_ROOTS = [HOME_ROOT / "scripts", Path.home() / ".codex" / "scripts", Path.home() / ".codex" / "skills"]

# ONE pattern for every check below. An INVOCATION is a launcher path with a filename on the end;
# the bare directory appears as prose ("the stubs were retired") and flagging that would fail for
# the wrong reason. Backslash-tolerant and `%USERPROFILE%`-tolerant because this box documents
# Windows absolute paths — the global-config check used a forward-slash-only variant and therefore
# missed exactly the spelling most likely to appear here.
# Anchored on a HOME reference. An earlier version led with `[\\/.~%][A-Za-z]*` and so also matched
# `project/.claude/scripts/hook.sh` — a project's own tooling, which is legitimate and would have
# failed the one-copy check for the wrong reason.
STALE_INVOCATION_RE = re.compile(
    r"(?:~|\$HOME|%USERPROFILE%|[A-Za-z]:[\\/][^\s\"']*?)[\\/]\.claude[\\/]scripts"
    r"[\\/][A-Za-z0-9_-]+\.(?:py|sh|ps1)")

problems: list[str] = []
warnings: list[str] = []


def projects_root() -> Path | None:
    """Where the user's web projects live. Configurable so this is not one machine's script."""
    env = os.environ.get("PROJECTS_ROOT")
    if env:
        p = Path(env)
        return p if p.is_dir() else None
    for candidate in (Path("C:/xampp/htdocs"), Path("/opt/lampp/htdocs"),
                      Path.home() / "projects", Path.home() / "Sites"):
        if candidate.is_dir():
            return candidate
    return None


def check_canonical_suite() -> None:
    for name in SCANNERS + HOOK_LAUNCHERS + ["_common.py", "_baseline.py", "self_test.py"]:
        target = CANONICAL_SCRIPTS / name
        if not target.is_file():
            problems.append(f"canonical script is missing: {target}")
    for name in CANONICAL_SKILLS:
        skill = SKILLS_ROOT / name / "SKILL.md"
        if not skill.is_file():
            problems.append(f"canonical skill is missing: {skill}")


def check_no_rival_copies() -> None:
    """No second copy of any scanner, anywhere. A junction or a fork both count."""
    names = set(SCANNERS) | set(HOOK_LAUNCHERS)
    for root in RIVAL_ROOTS:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.name in names and path.is_file():
                problems.append(f"rival copy of a canonical scanner: {path}")
        if root.name == "scripts" and root.is_dir() and any(root.iterdir()):
            warnings.append(f"{root} still exists; the launcher stubs were retired 2026-08-30")


def check_hooks() -> None:
    """Per-repo pre-commit hooks must call the canonical run_audit.sh."""
    root = projects_root()
    if root is None:
        warnings.append("no projects root found (set PROJECTS_ROOT); hook check skipped")
        return
    checked = 0
    for project in root.iterdir():
        hook = project / ".git" / "hooks" / "pre-commit"
        if not hook.is_file():
            continue
        checked += 1
        text = hook.read_text(encoding="utf-8", errors="replace")
        if "run_audit" in text and "skills/asdev-web-audit" not in text:
            problems.append(f"{hook} calls run_audit outside the canonical home")
    if checked == 0:
        warnings.append(f"no pre-commit hooks found under {root}")


def check_global_routing() -> None:
    """The global config must route audits at the canonical suite, not a retired shim path."""
    for cfg in (HOME_ROOT / "CLAUDE.md", Path.home() / ".codex" / "AGENTS.md"):
        if not cfg.is_file():
            continue
        # CLAUDE.md is a stub whose rules arrive by import; checking its own text would check nothing.
        text = expand_imports(cfg) if cfg.name == "CLAUDE.md" else cfg.read_text(encoding="utf-8-sig")
        if "asdev-web-audit" not in text:
            warnings.append(f"{cfg} no longer routes audits to the suite")
        stale = STALE_INVOCATION_RE.findall(text)
        if stale:
            problems.append(f"{cfg} still invokes the retired launchers: {sorted(set(stale))}")
    check_settings_allowlist()


def check_settings_allowlist() -> None:
    """`settings.json` names scanner paths too — in PERMISSION RULES, where a stale path fails
    silently rather than loudly.

    Omitting this file let the whole allowlist rot: eleven `Bash(python ~/.claude/scripts/<x>.py *)`
    rules kept naming the retired launcher directory for two days after it stopped existing, so every
    scanner run fell through to a prompt while this check still printed "all target the canonical
    suite". Only the stale-invocation half applies — a settings file with no audit rules at all is a
    legitimate fresh install, not a routing failure.
    """
    cfg = HOME_ROOT / "settings.json"
    if not cfg.is_file():
        return
    stale = STALE_INVOCATION_RE.findall(cfg.read_text(encoding="utf-8-sig"))
    if stale:
        problems.append(f"{cfg} still invokes the retired launchers: {sorted(set(stale))}")


TEXT_SUFFIXES = {".md", ".py", ".sh", ".ps1", ".yml", ".yaml", ".json", ".template", ".snippet", ".txt"}


def check_skill_content() -> None:
    """Skill documents — and especially the TEMPLATES they ship to other machines — must not tell a
    reader to invoke a retired launcher.

    This check exists because its absence shipped one: `pre-commit.template.sh` kept pointing at
    `~/.claude/scripts/harness_parity.py` for a full day after that path stopped existing, and a
    scaffolded project inherited the dead instruction. Checking the two global config files was
    never enough — a path in a shipped asset is a path a stranger will run.
    """
    for path in sorted(SKILLS_ROOT.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        if "__pycache__" in path.parts or path.resolve() == Path(__file__).resolve():
            continue                       # this file carries the detection regex, not an invocation
        try:
            text = path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError):
            continue
        stale = STALE_INVOCATION_RE.findall(text)
        if stale:
            problems.append(f"{path.relative_to(SKILLS_ROOT)} invokes a retired launcher: {sorted(set(stale))}")


# Per-project files that routinely name the audit suite. A fixed list, not a tree walk: scanning whole
# project trees takes minutes and this check has to be cheap enough to run on every hook change.
PROJECT_CONFIGS = [".auditignore", "AGENTS.md", "CLAUDE.md", ".claude/settings.local.json",
                   "tests/manifest.php", ".github/workflows/ci.yml",
                   # The hook is the file class this whole check exists for: check_hooks() only
                   # fires on the literal "run_audit", so a hook invoking a retired launcher by any
                   # other name was caught by nothing.
                   ".git/hooks/pre-commit"]


def check_project_configs() -> None:
    """Projects that still INVOKE a retired launcher — reported as warnings, not failures.

    Fixing these belongs to each project's own repository, so this surfaces them without blocking a
    run here. CI workflows and test manifests are the ones that actually break; a comment in an
    `.auditignore` only misleads a reader.
    """
    root = projects_root()
    if root is None:
        return
    for project in sorted(p for p in root.iterdir() if p.is_dir()):
        for rel in PROJECT_CONFIGS:
            path = project / rel
            if not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8-sig")
            except (OSError, UnicodeDecodeError):
                continue
            stale = STALE_INVOCATION_RE.findall(text)
            if stale:
                warnings.append(f"{project.name}/{rel} invokes a retired launcher: {sorted(set(stale))}")


def main() -> int:
    check_canonical_suite()
    check_no_rival_copies()
    check_hooks()
    check_global_routing()
    check_skill_content()
    check_project_configs()
    for message in problems:
        print(f"FAIL: {message}")
    for message in warnings:
        print(f"WARN: {message}")
    if not problems and not warnings:
        print("one-copy check: hooks, global config and skills all target the canonical suite")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
