#!/usr/bin/env python3
"""A project's second brain: set it up, move the old memory in, and check it.

WHY THIS EXISTS. Claude's memory used to sit in a hidden per-device folder,
`~/.claude/projects/<slug>/memory/`, outside git, so what one device learned never reached another
(owner, 2026-11-17). The harness's `autoMemoryDirectory` setting points that memory at the
project's committed `.docs/brain/` instead. The harness honours it only in the git-ignored
`.claude/settings.local.json`, only as an absolute path, and reads it once per session from the
session's own folder, so a worktree or subfolder session needs its own copy, pointing at the main
repo's brain. What belongs in a note: the `asdev-brain` skill.

USAGE (from the session's folder, or with --project)
    brain.py setup     point the harness's memory at the main repo's .docs/brain/
    brain.py migrate   copy the old hidden memory folder in; never overwrites, never deletes
    brain.py check     the brain's rules; exit 1 on a breach
    brain.py start     setup, then migrate, each only when it has work: the asdev mod's start-up hook

--json prints one JSON object instead of lines (the asdev mod's start-up hook reads it).
Exit codes: 0 done or clean, 1 refused or a breach, 3 not applicable (no git repo, or no .docs/).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from context_override import read_json, write_json  # noqa: E402
from security_audit import PLACEHOLDER, SECRET_ASSIGN, SECRET_LITERAL  # noqa: E402

KEY = "autoMemoryDirectory"
INDEX = "MEMORY.md"
# The index is loaded into every turn of the main chat and every agent: 40 lines of at most 150
# characters keeps it near the 6 kB doc_hygiene allows a memory index.
INDEX_MAX_LINES = 40
INDEX_MAX_CHARS = 150
# Matches a session folder's file at any depth, so subfolder sessions are covered too.
SETTINGS_IGNORE = "**/.claude/settings.local.json"
OBSIDIAN_IGNORE = ".obsidian/"
# Two devices that each added index lines then merge instead of conflicting.
UNION = ".docs/brain/MEMORY.md merge=union"
NOT_APPLICABLE = 3
LIST_MAX = 8

FRONTMATTER = re.compile(r"\A﻿?---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)", re.S)
USER_TYPE = re.compile(r"^\s*type:\s*['\"]?user['\"]?\s*$", re.M)
NAME = re.compile(r"^name:\s*['\"]?([^'\"\r\n]+?)['\"]?\s*$", re.M)
WIKILINK = re.compile(r"\[\[([^\]\r\n]+)\]\]")
MDLINK = re.compile(r"\]\(([^)\s]+)\)")
HUB_ENTRY = re.compile(r"^\s*[-*+]\s+\[\[[^\]\r\n]+\]\](.*)$")


class NotApplicable(Exception):
    pass


def git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


class Where:
    """The folders one run works on: the session's, its checkout's, and the main repo's."""

    def __init__(self, session: Path):
        self.raw = Path(os.path.abspath(session))
        if not self.raw.is_dir():
            raise NotApplicable(f"{self.raw} does not exist")
        self.session = self.raw.resolve()
        found = git(self.session, "rev-parse", "--path-format=absolute", "--show-toplevel", "--git-common-dir")
        lines = found.stdout.splitlines()
        if found.returncode != 0 or len(lines) < 2:
            raise NotApplicable(f"{self.session} is not inside a git repository")
        self.checkout = Path(lines[0]).resolve()
        self.common = Path(lines[1]).resolve()
        # A linked worktree's common dir is the main repo's .git, so every worktree finds one brain.
        self.main = self.common.parent if self.common.name == ".git" else self.checkout
        if not (self.main / ".docs").is_dir():
            raise NotApplicable(f"{self.main} has no .docs/ folder")
        self.brain = self.main / ".docs" / "brain"
        self.settings = self.session / ".claude" / "settings.local.json"


class Out:
    """One verdict line per step, or one JSON object."""

    def __init__(self, command: str):
        self.command = command
        self.steps: list[dict] = []
        self.facts: dict = {}

    def step(self, ok: bool, name: str, message: str, warn: bool = False) -> bool:
        self.steps.append({"ok": ok, "warn": warn, "step": name, "message": message})
        return ok

    @property
    def passed(self) -> bool:
        return all(s["ok"] for s in self.steps)

    def emit(self, as_json: bool, where: Where | None, skipped: str = "") -> None:
        if as_json:
            print(json.dumps({"command": self.command, "passed": self.passed and not skipped,
                              "skipped": skipped, "brain": str(where.brain) if where else "",
                              "steps": self.steps, **self.facts}, ensure_ascii=False))
            return
        if skipped:
            print(f"SKIP {self.command}: {skipped}")
            return
        print(f"brain: {where.brain}")
        for s in self.steps:
            tag = "FAIL" if not s["ok"] else "WARN" if s["warn"] else "ok  "
            print(f"{tag} {s['step']}: {s['message']}")
        print(f"{'PASS' if self.passed else 'FAIL'} {self.command}")


def config_dir() -> Path:
    return Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")


def slug(path: Path) -> str:
    # The harness's own folder name for a project (doc_hygiene.memory_index uses the same).
    return re.sub(r"[^A-Za-z0-9]", "-", str(path))


def old_folders(where: Where) -> list[Path]:
    """The hidden memory folders the harness keeps for this session's folder, checkout and repo."""
    projects = config_dir() / "projects"
    if not projects.is_dir():
        return []
    wanted = {slug(p).lower() for p in (where.raw, where.session, where.checkout, where.main)}
    return sorted(d / "memory" for d in projects.iterdir()
                  if d.name.lower() in wanted and (d / "memory").is_dir())


def holding(folders: list[Path]) -> list[Path]:
    return [d for d in folders if any(p.is_file() for p in d.rglob("*"))]


def setting(where: Where) -> str | None:
    value = read_json(where.settings)[0].get(KEY)
    return value if isinstance(value, str) and value.strip() else None


def same_path(a: str, b: Path) -> bool:
    return os.path.normcase(os.path.normpath(a)) == os.path.normcase(os.path.normpath(str(b)))


def read(path: Path) -> str:
    return path.read_bytes().decode("utf-8-sig", errors="replace")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def shorten(items: list[str]) -> str:
    more = len(items) - LIST_MAX
    return ", ".join(items[:LIST_MAX]) + (f" and {more} more" if more > 0 else "")


def append_line(path: Path, line: str) -> bool:
    """Add one line unless the file already has it; keeps the file's line breaks."""
    text = read(path) if path.is_file() else ""
    if line in (ln.strip() for ln in text.splitlines()):
        return False
    nl = "\r\n" if "\r\n" in text else "\n"
    if text and not text.endswith("\n"):
        text += nl
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((text + line + nl).encode("utf-8"))
    return True


def free(path: Path) -> Path:
    """`path`, or the first `<stem>-2.md`, `-3`, ... (`<folder>-2` for a folder) that does not exist."""
    stem, suffix = (path.stem, path.suffix) if path.suffix.lower() == ".md" else (path.name, "")
    n = 2
    candidate = path
    while candidate.exists():
        candidate = path.with_name(f"{stem}-{n}{suffix}")
        n += 1
    return candidate


# ---------------------------------------------------------------------------------------------- setup

def ignored(cwd: Path, rel: str) -> bool:
    return git(cwd, "check-ignore", "-q", "--no-index", rel).returncode == 0


def ensure_ignored(where: Where, cwd: Path, probe: str, pattern: str) -> tuple[bool, str]:
    if ignored(cwd, probe):
        return True, f"{probe} is ignored"
    append_line(where.main / ".gitignore", pattern)
    if ignored(cwd, probe):
        return True, f"added {pattern} to .gitignore"
    # A worktree checks out its own branch's .gitignore, which lacks the line until it is committed
    # and merged; the shared info/exclude covers it on this device meanwhile.
    append_line(where.common / "info" / "exclude", pattern)
    if ignored(cwd, probe):
        return True, f"added {pattern} to .git/info/exclude (this checkout's .gitignore lacks it)"
    return False, f"{probe} is still not ignored"


def union_set(main: Path) -> bool:
    return git(main, "check-attr", "merge", "--", ".docs/brain/" + INDEX).stdout.strip().endswith(": union")


def setup(where: Where, out: Out) -> None:
    current = setting(where)
    if current and not same_path(current, where.brain):
        out.step(False, "setting", f"{KEY} already points at {current}; change or remove it by hand first")
        return
    if git(where.session, "ls-files", "--error-unmatch", ".claude/settings.local.json").returncode == 0:
        out.step(False, "ignore", ".claude/settings.local.json is committed; untrack it (git rm --cached) first")
        return
    ok, message = ensure_ignored(where, where.session, ".claude/settings.local.json", SETTINGS_IGNORE)
    if not out.step(ok, "ignore", message):
        return
    ok, message = ensure_ignored(where, where.main, ".docs/.obsidian/workspace.json", OBSIDIAN_IGNORE)
    out.step(ok, "obsidian", message)
    if union_set(where.main):
        out.step(True, "attributes", "the index merges with merge=union")
    else:
        append_line(where.main / ".gitattributes", UNION)
        ok = union_set(where.main)
        out.step(ok, "attributes", "added merge=union for the index to .gitattributes" if ok
                 else "merge=union is still not set for the index")
    where.brain.mkdir(parents=True, exist_ok=True)
    out.facts["newly_set"] = not current
    if current:
        out.step(True, "setting", "memory already points at the brain")
        return
    data, nl = read_json(where.settings)
    data[KEY] = str(where.brain)
    write_json(where.settings, data, nl)
    out.step(True, "setting", f"written to .claude/settings.local.json ({len(data) - 1} other key(s) kept); "
                              "it takes effect in the next session")


# -------------------------------------------------------------------------------------------- migrate

def migrate(where: Where, out: Out, stamp: str) -> None:
    current = setting(where)
    if not (current and same_path(current, where.brain)):
        out.step(False, "setting", "run `brain.py setup` first, so the harness stops writing to the old folder")
        return
    sources = holding(old_folders(where))
    out.facts["moved"] = 0
    if not sources:
        out.step(True, "old folder", "nothing to migrate")
        return
    where.brain.mkdir(parents=True, exist_ok=True)
    for source in sources:
        migrate_one(source, where.brain, out, stamp)


def migrate_one(source: Path, brain: Path, out: Out, stamp: str) -> None:
    renamed: dict[str, str] = {}
    landed: list[tuple[Path, Path]] = []
    index_source = None
    copied = same = 0
    for path in sorted(p for p in source.rglob("*") if p.is_file()):
        rel = path.relative_to(source).as_posix()
        if rel.lower() == INDEX.lower():
            index_source = path
            continue
        dest = brain / rel
        if dest.exists():
            if dest.is_file() and digest(dest) == digest(path):
                same += 1
                landed.append((path, dest))
                continue
            # Never overwrite: the brain's copy may be one a session already reviewed.
            dest = free(dest.with_name(f"{dest.stem}-migrated-{stamp}{dest.suffix}"))
            renamed[rel] = dest.relative_to(brain).as_posix()
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)
        copied += 1
        landed.append((path, dest))
    out.step(True, "notes", f"from {source}: {copied} copied, {same} already in the brain")
    for old, new in renamed.items():
        out.step(True, "clash", f"{old} differs from the brain's copy, so it arrived as {new}: merge the two",
                 warn=True)
    expected = merge_index(index_source, brain / INDEX, renamed, out) if index_source else []

    broken = [src.relative_to(source).as_posix() for src, dest in landed
              if not dest.is_file() or digest(dest) != digest(src)]
    have = {ln.rstrip() for ln in read(brain / INDEX).splitlines()} if expected else set()
    missing = [ln for ln in expected if ln not in have]
    if broken or missing:
        out.step(False, "verify", f"{len(broken)} note(s) and {len(missing)} index line(s) did not arrive "
                                  f"intact, so {source} stays as it is")
        return
    out.step(True, "verify", f"{len(landed)} note(s) match by hash, and every index line is in")
    target = free(source.with_name(f"memory.migrated-{stamp}"))
    source.rename(target)
    out.facts["moved"] = out.facts.get("moved", 0) + copied
    out.step(True, "old folder", f"renamed {target.name}; nothing was deleted")


def merge_index(source: Path, dest: Path, renamed: dict[str, str], out: Out) -> list[str]:
    """Add the old index's lines the brain's index lacks; returns the lines that must be there."""
    text = read(source)
    lines = []
    for line in text.splitlines():
        line = line.rstrip()
        for old, new in renamed.items():
            line = line.replace(f"]({old})", f"]({new})")
        lines.append(line)
    if not dest.is_file():
        nl = "\r\n" if "\r\n" in text else "\n"
        dest.write_bytes((nl.join(lines) + nl).encode("utf-8"))
        out.step(True, "index", f"{sum(1 for ln in lines if ln.strip())} line(s) copied")
        return [ln for ln in lines if ln.strip()]
    current = read(dest)
    have = {ln.rstrip() for ln in current.splitlines()}
    # A heading belongs at the top; the brain's index already has its own.
    wanted = [ln for ln in lines if ln.strip() and not ln.lstrip().startswith("#")]
    add = list(dict.fromkeys(ln for ln in wanted if ln not in have))
    if add:
        nl = "\r\n" if "\r\n" in current else "\n"
        if current and not current.endswith("\n"):
            current += nl
        dest.write_bytes((current + nl.join(add) + nl).encode("utf-8"))
    out.step(True, "index", f"{len(add)} line(s) added, {len(wanted) - len(add)} already there")
    return wanted


# ---------------------------------------------------------------------------------------------- start

def start(where: Where, out: Out, stamp: str) -> None:
    """Setup, then migrate, at every session start; quiet when neither has work."""
    current = setting(where)
    sources = holding(old_folders(where))
    # Most starts: set up long ago, nothing left behind. Setup's git checks would only cost time.
    if current and same_path(current, where.brain) and not sources:
        out.step(True, "start", "memory already points at the brain, and no old folder holds notes")
        return
    setup(where, out)
    # Notes the harness left in the old folder: the partner's, a device's first session's, or those
    # written in the session that set the brain up, since the harness switches only after it.
    if out.passed and sources:
        migrate(where, out, stamp)
    if out.facts.get("newly_set") or out.facts.get("moved"):
        out.facts["index"] = read(where.brain / INDEX) if (where.brain / INDEX).is_file() else ""


# ---------------------------------------------------------------------------------------------- check

def notes_in(brain: Path) -> dict[str, Path]:
    """Every note, by its path inside the brain; dot folders (an Obsidian vault's) are not notes."""
    found = {}
    for path in brain.rglob("*.md"):
        rel = path.relative_to(brain)
        if rel.as_posix() == INDEX or any(part.startswith(".") for part in rel.parts):
            continue
        found[rel.as_posix()] = path
    return found


def note_link(brain: Path, base: Path, target: str) -> str | None:
    """A Markdown link's note inside the brain, or None when it points anywhere else."""
    target = target.split("#")[0]
    if not target.lower().endswith(".md") or re.match(r"^[a-z][a-z0-9+.-]*:", target, re.I):
        return None
    full = Path(os.path.normpath(base / target))
    try:
        return full.relative_to(Path(os.path.normpath(brain))).as_posix()
    except ValueError:
        return None


def check(where: Where, out: Out) -> None:
    current = setting(where)
    if not current:
        out.step(False, "setting", "not set up in this folder: run `brain.py setup`, or open a new session "
                                   "(the start-up hook does it)")
    elif not same_path(current, where.brain):
        out.step(False, "setting", f"{KEY} points at {current}, not this repo's brain")
    else:
        out.step(True, "setting", "memory points at the brain")
        held = holding(old_folders(where))
        out.step(not held, "old folder",
                 f"{held[0]} holds notes again. If this session started before setup, the next session "
                 "moves them in; if not, the setting stopped working: tell the owner" if held
                 else "no hidden memory folder holds notes")
    brain = where.brain
    notes = notes_in(brain) if brain.is_dir() else {}
    index = brain / INDEX
    index_text = read(index) if index.is_file() else ""
    if not notes and not index_text.strip():
        out.step(True, "brain", "no notes yet")
        return

    lines = [(n, ln) for n, ln in enumerate(index_text.splitlines(), 1) if ln.strip()]
    long_lines = [n for n, ln in lines if len(ln) > INDEX_MAX_CHARS]
    size_ok = len(lines) <= INDEX_MAX_LINES and not long_lines
    out.step(size_ok, "index size",
             f"{len(lines)} line(s), {len(long_lines)} over {INDEX_MAX_CHARS} characters"
             + (f" (line {long_lines[0]} first)" if long_lines else "")
             + ("" if size_ok else f"; the limit is {INDEX_MAX_LINES} lines: gather related notes under a hub note"))

    listed, dead = [], []
    for _, line in lines:
        for target in MDLINK.findall(line):
            rel = note_link(brain, brain, target)
            if rel is not None:
                (listed if rel in notes else dead).append(rel)
    out.step(not dead, "index links", f"line(s) point at no note: {shorten(dead)}" if dead
             else f"{len(listed)} note(s) listed, each one there")

    by_name = {}
    for rel, path in notes.items():
        by_name.setdefault(Path(rel).stem.lower(), rel)
        found = FRONTMATTER.match(read(path))
        name = NAME.search(found.group(1)) if found else None
        if name:
            by_name.setdefault(name.group(1).strip().lower(), rel)
    reached, queue, unwritten = set(listed), list(listed), set()
    while queue:
        rel = queue.pop()
        text = read(notes[rel])
        targets = []
        for raw in WIKILINK.findall(text):
            key = raw.split("|")[0].split("#")[0].strip()
            hit = by_name.get(key.lower()) or by_name.get(Path(key).stem.lower())
            if hit:
                targets.append(hit)
            elif key:
                unwritten.add(key)
        for raw in MDLINK.findall(text):
            hit = note_link(brain, notes[rel].parent, raw)
            if hit in notes:
                targets.append(hit)
        for hit in targets:
            if hit not in reached:
                reached.add(hit)
                queue.append(hit)
    lost = sorted(set(notes) - reached)
    out.step(not lost, "reach", f"{len(lost)} note(s) the index cannot reach: {shorten(lost)}; list them, "
                                "or link them from a note it lists" if lost
             else f"all {len(notes)} note(s) reachable from the index")
    if unwritten:
        out.step(True, "unwritten", f"links to notes not written yet: {shorten(sorted(unwritten))}", warn=True)

    # A hub is drilled through like the index, so it keeps the index's limits; an entry without a hook
    # makes the session open every listed note to find the one it needs.
    hubs, over = 0, []
    for rel, path in sorted(notes.items()):
        entries = [(n, ln, m.group(1)) for n, ln in enumerate(read(path).splitlines(), 1)
                   if (m := HUB_ENTRY.match(ln))]
        if not entries:
            continue
        hubs += 1
        long_entries = [n for n, ln, _ in entries if len(ln) > INDEX_MAX_CHARS]
        bare = [n for n, _, hook in entries if not hook.strip(" \t—–-:")]
        if len(entries) > INDEX_MAX_LINES:
            over.append(f"{rel} lists {len(entries)} notes")
        if long_entries:
            over.append(f"{rel}:{long_entries[0]} is over {INDEX_MAX_CHARS} characters")
        if bare:
            over.append(f"{rel}:{bare[0]} has no hook")
    if hubs:
        out.step(not over, "hubs",
                 f"{shorten(over)}; a hub lists at most {INDEX_MAX_LINES} notes as `- [[name]] — hook`, each "
                 f"line at most {INDEX_MAX_CHARS} characters, and a full one splits into sub-hubs" if over
                 else f"{hubs} hub(s), each within the index's limits")

    personal = []
    secrets = []
    for rel, path in sorted(notes.items()):
        text = read(path)
        found = FRONTMATTER.match(text)
        if found and USER_TYPE.search(found.group(1)):
            personal.append(rel)
        secrets += [f"{rel}:{n}" for n, line in enumerate(text.splitlines(), 1) if secret(line)]
    secrets += [f"{INDEX}:{n}" for n, line in lines if secret(line)]
    out.step(not personal, "personal", f"type: user note(s), which belong in CLAUDE.personal.md: "
                                       f"{shorten(personal)}" if personal else "no type: user notes")
    # The place only, never the value: this output is read back into a conversation.
    out.step(not secrets, "secrets", f"a credential at {shorten(secrets)}; remove it, and rotate it if it "
                                     "was ever committed" if secrets else "no credentials found")


def secret(line: str) -> bool:
    if SECRET_LITERAL.search(line):
        return True
    for match in SECRET_ASSIGN.finditer(line):
        value = match.group(1).strip()
        if not (PLACEHOLDER.match(value) or "$" in value or len(set(value)) <= 2):
            return True
    return False


# ----------------------------------------------------------------------------------------------- main

def run(command: str, project: Path, stamp: str | None = None) -> tuple[Out, Where | None, str]:
    """Run one command without printing; for the CLI and for doc_hygiene."""
    out = Out(command)
    try:
        where = Where(project)
    except NotApplicable as exc:
        return out, None, str(exc)
    try:
        if command == "setup":
            setup(where, out)
        elif command == "migrate":
            migrate(where, out, stamp or datetime.now().strftime("%Y%m%d-%H%M%S"))
        elif command == "start":
            start(where, out, stamp or datetime.now().strftime("%Y%m%d-%H%M%S"))
        else:
            check(where, out)
    except (OSError, ValueError) as exc:
        out.step(False, "error", f"{type(exc).__name__}: {exc}")
    return out, where, ""


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("command", choices=["setup", "migrate", "check", "start"])
    ap.add_argument("--project", type=Path, default=Path.cwd(),
                    help="the session's folder (default: the current one)")
    ap.add_argument("--json", action="store_true", help="one JSON object instead of lines")
    ap.add_argument("--stamp", help=argparse.SUPPRESS)  # a fixed time stamp, for the tests
    a = ap.parse_args(argv)
    out, where, skipped = run(a.command, a.project, a.stamp)
    out.emit(a.json, where, skipped)
    if skipped:
        return NOT_APPLICABLE
    return 0 if out.passed else 1


if __name__ == "__main__":
    sys.exit(main())
