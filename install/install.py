#!/usr/bin/env python3
"""Install the shared setup into ~/.claude, check it, or take the links out again.

    install-setup.cmd                          # or: python install/install.py
    python install/install.py --check          # report drift, change nothing
    python install/install.py --force-backup   # also replace folders holding files the repo lacks
    python install/install.py --uninstall      # replace every link with a real copy of what it shows

The repo must sit at ~/.claude/claude-agentic-setup: the CLAUDE.md stub imports it by that path.
Nothing is ever deleted. Whatever a link replaces goes to ~/.claude/backups/pre-install-<time>/, and
a person's own files (their agents, hooks, skill `local/` overlays) move INTO the linked folders,
where .gitignore keeps them untracked and private.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import time
from pathlib import Path

HOME = Path.home() / ".claude"
REPO = HOME / "claude-agentic-setup"
SHARED_MD = REPO / "CLAUDE.shared.md"
EXAMPLE_MD = REPO / "CLAUDE.personal.example.md"
CLAUDE_MD = HOME / "CLAUDE.md"
PERSONAL_MD = HOME / "CLAUDE.personal.md"
SETTINGS = HOME / "settings.json"
STATE = HOME / "setup-state.json"
FRAGMENT = REPO / "settings" / "shared-settings.json"
AUDIT = HOME / "skills" / "asdev-web-audit" / "scripts"
STUB = b"@claude-agentic-setup/CLAUDE.shared.md\n"

# Where a person's own files may live beside the shared ones. In `agents/` and `hooks/` every extra
# file is theirs; in a skill only its `local/` overlay and `.sandbox/` output are. Any other file
# the repo lacks stops the install, because moving it could break whatever still expects it.
ADOPT_ROOTS = {"agents", "hooks"}
ADOPT_PARTS = {"local", ".sandbox"}
SKIP_PARTS = {"__pycache__"}  # regenerated; left in the backup, never adopted

IO_REPARSE_TAG_MOUNT_POINT = 0xA0000003  # a junction
IO_REPARSE_TAG_SYMLINK = 0xA000000C


class Stop(Exception):
    """A condition the person must resolve; raised before anything has changed."""


def fault(point: str) -> None:
    """Test hook: SETUP_INSTALL_FAULT=<point> raises there, to prove the swap puts things back."""
    if os.environ.get("SETUP_INSTALL_FAULT") == point:
        raise OSError(f"injected fault at {point}")


# --- links -----------------------------------------------------------------------------------

def is_link(p: Path) -> bool:
    try:
        st = os.lstat(p)
    except OSError:
        return False
    return stat.S_ISLNK(st.st_mode) or getattr(st, "st_reparse_tag", 0) in (
        IO_REPARSE_TAG_MOUNT_POINT, IO_REPARSE_TAG_SYMLINK)


def points_to(link: Path, target: Path) -> bool:
    try:
        return is_link(link) and os.path.samefile(link, target)
    except OSError:
        return False


def make_link(link: Path, target: Path) -> None:
    if os.name == "nt":
        import _winapi  # junctions need neither admin rights nor Developer Mode
        _winapi.CreateJunction(str(target.resolve()), str(link))
    else:
        os.symlink(target.resolve(), link, target_is_directory=True)


def remove_link(link: Path) -> None:
    # Never shutil.rmtree or PowerShell's Remove-Item -Recurse here: through a junction they delete
    # the repo's files. os.rmdir removes only the link itself.
    if os.name == "nt":
        os.rmdir(link)
    else:
        os.unlink(link)


def link_pairs() -> list[tuple[Path, Path]]:
    pairs = [(HOME / "agents", REPO / "agents"), (HOME / "hooks", REPO / "hooks"),
             (HOME / ".docs", REPO / ".docs")]
    pairs += [(HOME / "skills" / d.name, d) for d in sorted((REPO / "skills").iterdir()) if d.is_dir()]
    return pairs


def survey(real: Path, target: Path) -> tuple[list[Path], list[Path], list[Path]]:
    """Files in a real folder about to be replaced: (theirs to adopt, extra, differing)."""
    adopt, extra, differ = [], [], []
    root_adopts = real.name in ADOPT_ROOTS
    for p in sorted(real.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(real)
        if SKIP_PARTS & set(rel.parts):
            continue
        twin = target / rel
        if twin.is_file():
            if twin.read_bytes() != p.read_bytes():
                differ.append(rel)
        elif root_adopts or ADOPT_PARTS & set(rel.parts):
            adopt.append(rel)
        else:
            extra.append(rel)
    return adopt, extra, differ


def plan_links(force: bool) -> list[tuple[str, Path, Path, list[Path]]]:
    actions, stops = [], []
    for link, target in link_pairs():
        name = link.relative_to(HOME).as_posix()
        if points_to(link, target):
            actions.append(("ok", link, target, []))
        elif is_link(link):
            actions.append(("relink", link, target, []))
        elif not link.exists():
            actions.append(("create", link, target, []))
        elif not link.is_dir():
            stops.append(f"{name} is a file, not a folder")
        else:
            adopt, extra, differ = survey(link, target)
            if (extra or differ) and not force:
                lines = [f"  only here: {r.as_posix()}" for r in extra]
                lines += [f"  differs from the repo: {r.as_posix()}" for r in differ]
                stops.append(f"{name} holds files the repo does not have as they are:\n" + "\n".join(lines))
            actions.append(("swap", link, target, adopt))
    if stops:
        raise Stop("\n".join(stops) + "\nNothing was changed. Keep what you need elsewhere, then run again, "
                   "or run with --force-backup to move these into the backup folder.")
    return actions


def swap(link: Path, target: Path, adopt: list[Path], backup_root: Path) -> None:
    """Replace a real folder with a link, keeping the window without a folder to one rename.

    A missing hooks folder blocks every shell call (the hook command exits 2), so the link is built
    first under a temporary name, and any failure puts the original back.
    """
    tmp = link.with_name(link.name + ".install-tmp")
    if is_link(tmp):
        remove_link(tmp)
    make_link(tmp, target)
    backup = backup_root / link.relative_to(HOME)
    backup.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.replace(link, backup)
    except BaseException:
        remove_link(tmp)
        raise
    try:
        fault("after-backup")
        os.replace(tmp, link)
    except BaseException:
        os.replace(backup, link)
        remove_link(tmp)
        raise
    for rel in adopt:  # copied, so the backup stays a complete picture of what was there
        dst = target / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(backup / rel, dst)


# --- CLAUDE.md --------------------------------------------------------------------------------

def plan_claude_md(force: bool) -> str:
    if not CLAUDE_MD.exists():
        return "write"
    data = CLAUDE_MD.read_bytes()
    if data == STUB:
        return "ok"
    if data == SHARED_MD.read_bytes():
        return "replace"
    if not PERSONAL_MD.exists():
        return "to-personal"
    if force:
        return "replace"
    raise Stop("CLAUDE.md has rules of its own and CLAUDE.personal.md already exists. Move the rules you "
               "want to keep into CLAUDE.personal.md, then run again (or --force-backup). Nothing was changed.")


def write_atomic(path: Path, data: bytes) -> None:
    tmp = path.with_name(path.name + ".install-tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


# --- settings ---------------------------------------------------------------------------------

def merge_settings(settings: dict, fragment: dict, last: dict) -> tuple[dict, list[str], list[str]]:
    """(merged settings, changes made, personal overrides kept). Pure; never mutates its inputs."""
    s = copy.deepcopy(settings)
    changes, overrides = [], []
    for key, value in fragment.get("set", {}).items():
        *parents, leaf = key.split(".")
        node = s
        for part in parents:
            node = node.setdefault(part, {})
        if leaf not in node:
            node[leaf] = value
            changes.append(f"set {key}")
        elif node[leaf] == value:
            continue
        elif key in last and node[leaf] == last[key]:
            node[leaf] = value
            changes.append(f"updated {key}")
        else:
            overrides.append(f"{key} is {node[leaf]!r} here; the shared value is {value!r}")

    for section, sign in (("add", 1), ("retire", -1)):
        for key, entries in fragment.get(section, {}).items():
            if key == "hooks":
                for event, items in entries.items():
                    groups = s.setdefault("hooks", {}).setdefault(event, [])
                    for item in items:
                        changes += (_add_hook if sign > 0 else _retire_hook)(groups, event, item)
                    if not groups:
                        del s["hooks"][event]
                continue
            *parents, leaf = key.split(".")
            node = s
            for part in parents:
                node = node.setdefault(part, {})
            current = node.setdefault(leaf, [])
            for entry in entries:
                if sign > 0 and entry not in current:
                    current.append(entry)
                    changes.append(f"added {key}: {entry}")
                elif sign < 0 and entry in current:
                    current[:] = [e for e in current if e != entry]
                    changes.append(f"retired {key}: {entry}")
    return s, changes, overrides


def _add_hook(groups: list, event: str, item: dict) -> list[str]:
    if any(h.get("command") == item["command"] for g in groups for h in g.get("hooks", [])):
        return []
    group = next((g for g in groups if g.get("matcher") == item["matcher"]), None)
    if group is None:
        group = {"matcher": item["matcher"], "hooks": []}
        groups.append(group)
    group["hooks"].append({"type": "command", "command": item["command"], "timeout": item["timeout"]})
    return [f"added hook {event}: {item['command']}"]


def _retire_hook(groups: list, event: str, item: dict) -> list[str]:
    changed = []
    for g in groups:
        kept = [h for h in g.get("hooks", []) if h.get("command") != item["command"]]
        if len(kept) != len(g.get("hooks", [])):
            g["hooks"] = kept
            changed.append(f"retired hook {event}: {item['command']}")
    groups[:] = [g for g in groups if g.get("hooks")]
    return changed


def hook_scripts(fragment: dict) -> list[Path]:
    """The script each shared hook runs. A hook whose script is missing blocks every tool call."""
    out = []
    for items in fragment.get("add", {}).get("hooks", {}).values():
        for item in items:
            m = re.search(r'"\$HOME/([^"]+)"', item["command"])
            if m:
                out.append(Path.home() / m.group(1))
    return out


def read_json(path: Path, default: dict) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else default


def write_settings(new: dict) -> None:
    raw = SETTINGS.read_bytes() if SETTINGS.is_file() else b""
    text = json.dumps(new, indent=2, ensure_ascii=False) + "\n"
    if b"\r\n" in raw:
        text = text.replace("\n", "\r\n")
    write_atomic(SETTINGS, text.encode("utf-8"))


# --- helpers ----------------------------------------------------------------------------------

def find_bash() -> str | None:
    """Git Bash, which Claude Code runs hook commands in on Windows (never WSL's bash.exe)."""
    configured = os.environ.get("CLAUDE_CODE_GIT_BASH_PATH")
    if configured and Path(configured).is_file():
        return configured
    if os.name != "nt":
        return shutil.which("bash")
    git = shutil.which("git")
    # Climb from git.exe to Git's root: from a terminal PATH gives Git\cmd\git.exe, but inside a
    # git hook it gives Git\mingw64\libexec\git-core\git.exe, three levels further down.
    for root in Path(git).parents if git else ():
        if (root / "bin" / "bash.exe").is_file():
            return str(root / "bin" / "bash.exe")
    return None


def run(argv: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", errors="replace", **kw)


def preflight() -> str:
    if sys.version_info < (3, 10):
        raise Stop(f"Python 3.10 or newer is needed; this is {sys.version.split()[0]}.")
    if Path(__file__).resolve().parent.parent != REPO.resolve():
        raise Stop(f"The repo must be cloned to {REPO}; the CLAUDE.md stub imports it from there.")
    if not shutil.which("git"):
        raise Stop("git is not on PATH.")
    bash = find_bash()
    if not bash:
        raise Stop("Git Bash was not found. Install Git for Windows, or set CLAUDE_CODE_GIT_BASH_PATH.")
    probe = run([bash, "-c", "python --version"])
    if probe.returncode != 0 or not probe.stdout.startswith("Python 3"):
        raise Stop("`python` inside Git Bash is missing or is the Microsoft Store stub, so the hooks "
                   "would silently not run. Install Python from python.org with 'Add to PATH', or turn off "
                   "the python App execution aliases in Windows settings.")
    return bash


def guard_probe(bash: str, fragment: dict) -> str | None:
    """Run the shared PreToolUse guard exactly as Claude Code would; it must refuse this command."""
    command = next((i["command"] for i in fragment["add"]["hooks"].get("PreToolUse", [])
                    if "guard_credentials" in i["command"]), None)
    if command is None:
        return None
    token_file = "~/.claude/" + ".credentials" + ".json"
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": f"cat {token_file}"},
                          "cwd": str(Path.home())})
    r = run([bash, "-c", command], input=payload, timeout=60)
    if '"deny"' not in r.stdout:
        return f"the credentials guard did not refuse its probe (exit {r.returncode}): {r.stderr.strip()[-300:]}"
    return None


# --- modes ------------------------------------------------------------------------------------

def check() -> int:
    drift = []
    for link, target in link_pairs():
        if not points_to(link, target):
            state = "a real folder" if link.is_dir() and not is_link(link) else (
                "a link elsewhere" if is_link(link) else "missing")
            drift.append(f"{link.relative_to(HOME).as_posix()} is {state}")
    if not CLAUDE_MD.is_file() or CLAUDE_MD.read_bytes() != STUB:
        drift.append("CLAUDE.md is not the one-line stub")
    if not PERSONAL_MD.is_file():
        drift.append("CLAUDE.personal.md is missing")
    fragment = read_json(FRAGMENT, {})
    _, changes, overrides = merge_settings(read_json(SETTINGS, {}), fragment,
                                           read_json(STATE, {}).get("set", {}))
    drift += [f"settings.json: not yet {c}" for c in changes]
    if (REPO / ".git").exists() and run(["git", "-C", str(REPO), "config", "core.hooksPath"]).stdout.strip() != "githooks":
        drift.append("git core.hooksPath is not githooks")
    sync = run([sys.executable, str(AUDIT / "sync_agents_md.py"), "--check"])
    if sync.returncode:
        drift.append("AGENTS.md: " + (sync.stdout.strip().splitlines() or ["check failed"])[0])
    for o in overrides:
        print(f"note  personal override kept: {o}")
    for d in drift:
        print(f"DRIFT {d}")
    print("check: in place" if not drift else f"check: {len(drift)} item(s) drifted; run install-setup.cmd")
    return 1 if drift else 0


def install(force: bool, from_hook: bool) -> int:
    bash = preflight()
    link_actions = plan_links(force)
    md_action = plan_claude_md(force)
    fragment = read_json(FRAGMENT, {})
    backup_root = HOME / "backups" / time.strftime("pre-install-%Y%m%d-%H%M%S")
    changed = 0

    (HOME / "skills").mkdir(parents=True, exist_ok=True)
    for action, link, target, adopt in link_actions:
        name = link.relative_to(HOME).as_posix()
        if action == "ok":
            continue
        if action == "relink":
            remove_link(link)
            make_link(link, target)
        elif action == "create":
            make_link(link, target)
        else:
            swap(link, target, adopt, backup_root)
        changed += 1
        extra = f"; kept {len(adopt)} file(s) of your own inside it" if adopt else ""
        print(f"link  {name} -> repo ({action}{extra})")

    if md_action != "ok":
        if CLAUDE_MD.exists():
            backup_root.mkdir(parents=True, exist_ok=True)
            shutil.copy2(CLAUDE_MD, backup_root / "CLAUDE.md")
        if md_action == "to-personal":
            shutil.copy2(CLAUDE_MD, PERSONAL_MD)
            print("note  your CLAUDE.md is now CLAUDE.personal.md; delete from it what the shared rules already say")
        write_atomic(CLAUDE_MD, STUB)
        changed += 1
        print("file  CLAUDE.md -> one-line stub importing the shared rules")
    if not PERSONAL_MD.exists():
        shutil.copy2(EXAMPLE_MD, PERSONAL_MD)
        changed += 1
        print(f"file  CLAUDE.personal.md created from the example: fill in your machine and hosting ({PERSONAL_MD})")

    missing = [p for p in hook_scripts(fragment) if not p.is_file()]
    if missing:
        raise Stop("The shared hooks point at scripts that do not exist, and a missing hook script blocks "
                   "every tool call; settings.json was left alone: " + ", ".join(map(str, missing)))
    last = read_json(STATE, {}).get("set", {})
    current = read_json(SETTINGS, {})
    merged, changes, overrides = merge_settings(current, fragment, last)
    if changes:
        backup_root.mkdir(parents=True, exist_ok=True)
        if SETTINGS.is_file():
            shutil.copy2(SETTINGS, backup_root / "settings.json")
        write_settings(merged)
        changed += 1
        for c in changes:
            print(f"set   settings.json: {c}")
    for o in overrides:
        print(f"note  personal override kept: {o}")
    if last != fragment.get("set", {}):
        write_atomic(STATE, (json.dumps({"set": fragment.get("set", {})}, indent=2) + "\n").encode("utf-8"))

    if (REPO / ".git").exists():
        hooks_path = run(["git", "-C", str(REPO), "config", "core.hooksPath"]).stdout.strip()
        if hooks_path != "githooks":
            run(["git", "-C", str(REPO), "config", "core.hooksPath", "githooks"])
            changed += 1
            print("git   core.hooksPath -> githooks (pre-commit scan, apply-on-pull)")

    problems = []
    sync = run([sys.executable, str(AUDIT / "sync_agents_md.py")])
    if sync.returncode:
        problems.append("AGENTS.md: " + (sync.stdout + sync.stderr).strip()[-300:])
    if not from_hook:
        parity = run([sys.executable, str(AUDIT / "harness_parity.py")])
        if parity.returncode:
            problems.append("harness_parity.py: " + parity.stdout.strip()[-300:])
    probe = guard_probe(bash, fragment)
    if probe:
        problems.append(probe)
    for p in problems:
        print(f"FAIL  {p}")
    if backup_root.exists():
        print(f"note  originals kept in {backup_root}")
    print(f"install: {changed} change(s), {len(problems)} problem(s)"
          + ("" if changed else "; everything was already in place"))
    return 1 if problems else 0


def uninstall() -> int:
    """Replace each link with a real copy of what it shows, so no edit made since install is lost.

    The pre-install originals stay in the backups folder; settings.json keeps the shared entries,
    which stay valid because the files they name are copied into place.
    """
    for link, target in link_pairs():
        if not is_link(link):
            continue
        tmp = link.with_name(link.name + ".uninstall-tmp")
        shutil.copytree(target, tmp, ignore=shutil.ignore_patterns("__pycache__"))
        remove_link(link)
        os.replace(tmp, link)
        print(f"copy  {link.relative_to(HOME).as_posix()} is a real folder again")
    if CLAUDE_MD.is_file() and CLAUDE_MD.read_bytes() == STUB:
        write_atomic(CLAUDE_MD, SHARED_MD.read_bytes())
        print("file  CLAUDE.md holds the shared rules again (still importing CLAUDE.personal.md)")
    print("uninstall: done; the repo folder and settings.json are unchanged")
    return 0


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="report drift; change nothing")
    mode.add_argument("--uninstall", action="store_true", help="replace every link with a real copy")
    ap.add_argument("--force-backup", action="store_true",
                    help="also replace folders holding files the repo lacks (they go to the backup)")
    ap.add_argument("--from-hook", action="store_true", help=argparse.SUPPRESS)
    args = ap.parse_args()
    try:
        if args.check:
            return check()
        if args.uninstall:
            return uninstall()
        return install(args.force_backup, args.from_hook)
    except Stop as stop:
        print(f"STOP  {stop}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
