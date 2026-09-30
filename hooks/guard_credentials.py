#!/usr/bin/env python3
"""PreToolUse guard (Bash, PowerShell): keep ~/.claude/.credentials.json out of shell output.

That file holds the Claude login tokens. The Read(...) deny rule in settings.json covers the Read,
Grep and Glob tools, but not shell commands, and on 2026-09-28 a recursive grep run from ~/.claude
printed the whole file into a session. This refuses a shell command that names the file, reads it
through a wildcard, or searches recursively from the home folder or ~/.claude without excluding it.
It is a guard against accidents, not a sandbox: a deliberately obfuscated command gets past it.
"""
import fnmatch
import json
import os
import re
import shlex
import sys
from pathlib import Path

HOME = Path.home()
CLAUDE = HOME / ".claude"
TARGET = ".credentials.json"


def norm(p):
    return os.path.normcase(os.path.abspath(p))


# A recursive scan of either directory reaches the file.
ROOTS = {norm(HOME), norm(CLAUDE)}

NAMES = re.compile(r"\.cred|credentials\.json", re.I)
EXCLUDES = re.compile(
    r"""--exclude(?:-dir)?[= ]['"]?\.?credentials\S*?['"]?(?=\s|$)"""
    r"""|(?:-g|--glob|--iglob)[= ]?['"]?!\S*credentials\S*?['"]?(?=\s|$)"""
    r"""|-Exclude\s+['"]?\S*credentials\S*?['"]?(?=\s|$)""",
    re.I,
)
READERS = re.compile(
    r"\b(?:grep|egrep|fgrep|rg|ag|ack|findstr|Select-String|sls|Get-Content|gc|cat|type|head|tail"
    r"|less|more|strings|xxd|od|base64|xargs)\b|-exec\b",
    re.I,
)
CD = {"cd", "pushd", "chdir", "set-location", "sl"}
GREP = {"grep", "egrep", "fgrep"}


def expand(tok, cwd):
    t = tok.strip("'\"")
    t = re.sub(r"^(?:~|\$\{?HOME\}?|\$env:USERPROFILE|%USERPROFILE%)(?=[/\\]|$)",
               lambda _: HOME.as_posix(), t, flags=re.I)
    m = re.match(r"^/([a-zA-Z])(/.*|$)", t)  # Git Bash /c/Users/...
    if m:
        t = f"{m[1]}:{m[2] or '/'}"
    return Path(t) if os.path.isabs(t) else Path(cwd) / t


def recursive_kind(words, seg):
    """'read' when the segment itself prints file contents recursively, 'list' when it only
    walks a tree (dangerous once something later in the command reads what it lists)."""
    head = words[0].lower() if words else ""
    if head in GREP and re.search(r"(?<!\S)-[a-zA-Z]*[rR][a-zA-Z]*(?=\s|$)|--(?:dereference-)?recursive", seg):
        return "read"
    if head in {"rg", "ag"} and re.search(r"--hidden|(?<!\S)-[a-zA-Z]*u[a-zA-Z]*u|(?<!\S)-\.", seg):
        return "read"  # without these they skip dotfiles, so the file is never read
    if head == "findstr" and re.search(r"(?<!\S)/s\b", seg, re.I):
        return "read"
    if head == "find" or re.search(r"-Recurse\b", seg, re.I) \
            or head == "ls" and re.search(r"(?<!\S)-[a-zA-Z]*R", seg) \
            or head == "dir" and re.search(r"(?<!\S)/s\b", seg, re.I):
        return "list"
    return None


def reaches_file(words, cwd):
    """True when a path argument is a root, or when none is given and the scan starts at cwd."""
    saw_path = False
    for w in words[1:]:
        if w.startswith("-") or w.startswith("/") and len(w) == 2:
            continue
        p = expand(w, cwd)
        if p.exists():
            saw_path = True
            if norm(p) in ROOTS:
                return True
        # A bare `*.pyc` is a search pattern (find -name, --include), not a path to walk.
        elif re.search(r"[/\\]", w) and any(c in p.name for c in "*?[") and norm(p.parent) in ROOTS:
            return True
    return not saw_path and norm(cwd) in ROOTS


def violation(cmd, cwd):
    if NAMES.search(EXCLUDES.sub("", cmd)):
        return "it names the credentials file"
    excluded = bool(EXCLUDES.search(cmd))
    reads = bool(READERS.search(cmd))
    for seg in re.split(r"&&|\|\||[;|\n]", cmd):
        try:
            words = shlex.split(seg, posix=False)  # posix mode eats Windows backslashes
        except ValueError:
            words = seg.split()
        if not words:
            continue
        if words[0].lower() in CD and len(words) > 1:
            cwd = expand(words[1], cwd)
            continue
        for w in words[1:]:  # a wildcard read inside ~/.claude, e.g. Get-Content ~/.claude/*
            p = expand(w, cwd)
            if any(c in p.name for c in "*?[") and norm(p.parent) == norm(CLAUDE) \
                    and fnmatch.fnmatch(TARGET, p.name) and READERS.search(seg):
                return "a wildcard in ~/.claude matches the credentials file"
        kind = recursive_kind(words, seg)
        if kind and not excluded and (kind == "read" or reads) and reaches_file(words, cwd):
            return "it searches the home folder or ~/.claude recursively"
    return None


def main():
    data = json.load(sys.stdin)
    cmd = (data.get("tool_input") or {}).get("command") or ""
    why = violation(cmd, data.get("cwd") or os.getcwd())
    if why:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": (
                f"Blocked: {why}, so it could print ~/.claude/.credentials.json (the Claude login "
                "tokens). Search a subfolder instead, or exclude the file: grep --exclude=.credentials.json, "
                "rg -g '!.credentials.json', Get-ChildItem -Exclude .credentials.json."),
        }}))


if __name__ == "__main__":
    main()
