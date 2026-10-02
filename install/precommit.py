#!/usr/bin/env python3
"""Refuse a commit that would put private material in the shared setup repo.

Run by githooks/pre-commit on the staged files; `--all` scans everything tracked or staged (the
sweep before a push). Two checks, both on what git would actually store (the index), not the disk:

  * the path: only the shared layout may be committed — never a `local/` overlay, a personal file,
    the login-token file or an `.env`;
  * the content: nothing shaped like a real credential. Full token shapes, not bare prefixes, so the
    docs may name `sk-ant-` or `ghp_` while a real key still cannot slip through.

Bypassing it (`git commit --no-verify`) needs proof in the commit message that nothing private is staged.
"""
from __future__ import annotations

import fnmatch
import re
import subprocess
import sys

ALLOWED = [
    "CLAUDE.shared.md", "CLAUDE.personal.example.md", "README.md", ".gitignore", ".gitattributes",
    "install-setup.cmd", "install/*", "githooks/*", "settings/*.json", "agents/opus-*.md",
    "agents/fable-*.md", "agents/sonnet-*.md", "hooks/*.py", ".docs/*", "skills/asdev-*/*",
    "mods/*", ".auditignore",
]
FORBIDDEN_PARTS = {"local", "__pycache__", ".sandbox", "projects", "backups"}
FORBIDDEN_NAMES = {"." + "credentials.json", ".claude.json", "CLAUDE.personal.md", "setup-state.json",
                   "settings.json", "history.jsonl"}
TOKEN_SHAPES = [
    ("Anthropic key or token", r"sk-ant-[A-Za-z0-9]{2,6}-[A-Za-z0-9_\-]{20,}"),
    ("GitHub token", r"\bgh[pousr]_[A-Za-z0-9]{36,}"),
    ("GitHub fine-grained token", r"\bgithub_pat_[A-Za-z0-9_]{40,}"),
    ("private key", r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    ("AWS access key", r"\bAKIA[0-9A-Z]{16}\b"),
    ("OAuth token in JSON", r'"(?:access|refresh)Token"\s*:\s*"[^"]{20,}"'),
    ("Slack token", r"\bxox[abprs]-[A-Za-z0-9-]{20,}"),
]


def git(*args: str) -> bytes:
    return subprocess.run(["git", *args], capture_output=True, check=True).stdout


def path_problem(path: str) -> str | None:
    parts = path.split("/")
    name = parts[-1]
    if FORBIDDEN_PARTS & set(parts[:-1]):
        return "private folder"
    if name in FORBIDDEN_NAMES or (name.startswith(".env") and name != ".env.example") or name.endswith(".pyc"):
        return "private file"
    if not any(fnmatch.fnmatchcase(path, pattern) for pattern in ALLOWED):
        return "outside the shared layout"
    return None


def content_problems(path: str) -> list[str]:
    text = git("show", f":{path}").decode("utf-8", errors="ignore")
    found = []
    for label, pattern in TOKEN_SHAPES:
        for m in re.finditer(pattern, text):
            line = text.count("\n", 0, m.start()) + 1
            found.append(f"{path}:{line}: looks like a {label}")
    return found


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if "--all" in sys.argv[1:]:
        paths = git("ls-files", "-z").decode("utf-8").split("\0")
    else:
        paths = git("diff", "--cached", "--name-only", "-z", "--diff-filter=ACMR").decode("utf-8").split("\0")
    paths = [p for p in paths if p]
    problems = []
    for path in paths:
        why = path_problem(path)
        if why:
            problems.append(f"{path}: {why}")
        else:
            problems += content_problems(path)
    if "--all" not in sys.argv[1:]:
        added = git("diff", "--cached", "--name-only", "-z", "--diff-filter=A").decode("utf-8").split("\0")
        for path in added:
            if path.startswith(("agents/", "hooks/")):
                print(f"note: new shared file {path} - it reaches the other person at their next pull")
    for p in problems:
        print(f"REFUSED {p}")
    print(f"precommit: {len(paths)} file(s) scanned, {len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
