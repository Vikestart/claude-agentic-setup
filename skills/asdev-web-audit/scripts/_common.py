"""Shared helpers for the deterministic scanners bundled with asdev-web-audit.

Every script here is project-agnostic: run it from any web project root and it
scans the tree below the current working directory.

Invariants this module exists to guarantee across all scripts:

  * Directory exclusion matches whole path SEGMENTS, never substrings. The old
    scripts tested `if 'lib' in filepath`, which silently excluded core/lib/ and
    api/lib/ - i.e. exactly the security-critical code - from the audit.
  * Findings mean exit 1, clean means exit 0, so `&&` chains and CI gate
    honestly. Three scripts used to always exit 0 while printing violations.
  * Unreadable files are reported, never swallowed. A file that isn't valid
    UTF-8 used to be skipped silently and counted as clean.
  * Reports are read by humans and by agents with a limited context window, so
    output is grouped, capped (--max) and switchable to --quiet / --json.

Per-project tuning lives in an optional `.auditignore` at the project root:

    build/            # trailing slash: a directory NAME, excluded anywhere
    *.generated.css   # anything else: a glob matched against the relative path
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import shutil
import subprocess
import sys

# Directory names that never hold first-party source. Matched against whole path
# segments. Keep this list generic: these scripts serve every web project.
DEFAULT_IGNORE_DIRS = {
    ".git", ".hg", ".svn", "__pycache__", ".venv", "venv", "node_modules",
    "vendor", "dist", "build", "coverage", "cache", "backups",
    ".gemini", ".agents", ".vscode", ".idea",
    "fontawesome", "font-awesome",
    "wire", "wp-admin", "wp-includes",  # ProcessWire / WordPress cores
}

DEFAULT_IGNORE_GLOBS = [
    "*.min.js", "*.min.css", "*.bundle.js", "*.map", "*-lock.json",
]

# Path segments that mark a template fragment rather than a full page.
FRAGMENT_DIRS = {"views", "templates", "partials", "fragments"}

_TEXT_CACHE: dict[str, str] = {}
_TREE_CACHE: dict[tuple, tuple[str, ...]] = {}
_IGNORE_CACHE: dict[str, tuple[set[str], list[str]]] = {}

# When set, only these relative paths are scanned (see --changed / --since).
_SCOPE: set[str] | None = None
_SCOPE_LABEL = "whole project"
_LAST_GIT_ERROR: str | None = None


class ReadError(Exception):
    """Raised when a file cannot be read as text at all."""


def set_scope(paths: set[str] | None, label: str) -> None:
    global _SCOPE, _SCOPE_LABEL
    _SCOPE = paths
    _SCOPE_LABEL = label
    _TREE_CACHE.clear()


def scope_label() -> str:
    return _SCOPE_LABEL


def scope_active() -> bool:
    return _SCOPE is not None


def in_scope(rel: str) -> bool:
    """True when `rel` would be scanned under the current scope."""
    return _SCOPE is None or rel in _SCOPE


def scope_contains_prefix(prefix: str) -> bool:
    """True when the active scope contains `prefix` or anything below it."""
    if _SCOPE is None:
        return True
    prefix = prefix.replace("\\", "/").rstrip("/")
    return any(path == prefix or path.startswith(prefix + "/") for path in _SCOPE)


def find_git() -> str | None:
    """Resolve Git without assuming an interactive shell PATH."""
    env = os.environ.get("AUDIT_GIT")
    if env and os.path.isfile(env):
        return env
    on_path = shutil.which("git")
    if on_path:
        return on_path
    candidates = [
        r"C:\Program Files\Git\cmd\git.exe",
        r"C:\Program Files\Git\bin\git.exe",
    ]
    return next((path for path in candidates if os.path.isfile(path)), None)


def _run_git(root: str, *args: str, timeout: int = 30) -> subprocess.CompletedProcess | None:
    """Run read-only Git with a per-command safe-directory override.

    A harness sandbox account can differ from the repository owner. Passing
    safe.directory for this exact root avoids a misleading full-scan fallback
    without mutating the user's global Git configuration.
    """
    global _LAST_GIT_ERROR
    git = find_git()
    if not git:
        _LAST_GIT_ERROR = "git executable not found (set AUDIT_GIT)"
        return None
    safe_root = os.path.abspath(root).replace("\\", "/")
    try:
        # ⚠️ ENCODING AND QUOTING ARE BOTH LOAD-BEARING FOR PATHS.
        # `text=True` alone decodes with the LOCALE codec (cp1252 on Windows), which
        # mangles git's UTF-8 path bytes; and with `core.quotepath` at its default git
        # renders a non-ASCII path as an escaped C string ("n\303\270rsk.css"). Either
        # one makes the name fail to match a real file, so the path silently drops out
        # of --changed / --staged scope and the scan reports CLEAN for a file it never
        # opened. quotepath=false here, `-z` at the call sites.
        result = subprocess.run(
            [git, "-c", f"safe.directory={safe_root}", "-c", "core.quotepath=false", *args],
            cwd=root, capture_output=True, text=True, timeout=timeout,
            encoding="utf-8", errors="surrogateescape",
        )
    except (OSError, subprocess.SubprocessError) as exc:
        _LAST_GIT_ERROR = str(exc)
        return None
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "git command failed").strip()
        _LAST_GIT_ERROR = detail.splitlines()[0]
        return None
    _LAST_GIT_ERROR = None
    return result


def git_changed(root: str, ref: str | None = None) -> set[str] | None:
    """Relative paths of files changed vs `ref` (default: working tree vs HEAD).

    Returns None when this isn't a git repo or git isn't available, so callers
    can fall back to a full scan rather than silently auditing nothing.
    """
    # -z: NUL-separated, never quoted. See the encoding note in _run_git.
    commands = [["diff", "--name-only", "--diff-filter=ACMRTUXB", "-z", ref or "HEAD"]]
    # Untracked files are part of the deliverable under both --changed and
    # --since; omitting them can make a branch gate report a false clean.
    commands.append(["ls-files", "--others", "--exclude-standard", "-z"])

    found: set[str] = set()
    for command in commands:
        result = _run_git(root, *command)
        if result is None:
            return None
        found.update(part for part in result.stdout.split("\0") if part)
    return found


def git_staged(root: str) -> set[str] | None:
    """Relative paths of files staged for commit (the pre-commit hook scope)."""
    result = _run_git(root, "diff", "--name-only", "--cached",
                      "--diff-filter=ACMRTUXB", "-z")
    if result is None:
        return None
    return {part for part in result.stdout.split("\0") if part}


def git_tracked(root: str, pathspec: str) -> bool | None:
    """Whether Git tracks at least one path matching `pathspec`."""
    result = _run_git(root, "ls-files", "--", pathspec)
    if result is None:
        return None
    return bool(result.stdout.strip())


def git_ignored(root: str, pathspec: str) -> bool | None:
    """Whether Git ignores `pathspec`; None means Git state was unavailable."""
    git = find_git()
    if not git:
        return None
    safe_root = os.path.abspath(root).replace("\\", "/")
    try:
        result = subprocess.run(
            [git, "-c", f"safe.directory={safe_root}", "check-ignore", "-q",
             "--", pathspec],
            cwd=root, capture_output=True, text=True, timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode == 0:
        return True
    if result.returncode == 1:
        return False
    return None


def apply_scope(args, root: str) -> None:
    """Honour --staged / --changed / --since, warning rather than failing silently."""
    ref = getattr(args, "since", None)
    staged = getattr(args, "staged", False)
    if not getattr(args, "changed", False) and not ref and not staged:
        return
    paths = git_staged(root) if staged else git_changed(root, ref)
    if paths is None:
        reason = _LAST_GIT_ERROR or "repository state unavailable"
        print(f"warning: requested Git scope unavailable ({reason}) - "
              "scanning everything instead", file=sys.stderr)
        return
    label = (f"{len(paths)} staged file(s)" if staged
             else f"{len(paths)} changed file(s)" + (f" vs {ref}" if ref else ""))
    set_scope(paths, label)


def load_ignore_file(root: str = ".") -> tuple[set[str], list[str]]:
    """Parse an optional .auditignore in the project root."""
    cache_key = os.path.normcase(os.path.abspath(root))
    if cache_key in _IGNORE_CACHE:
        dirs, globs = _IGNORE_CACHE[cache_key]
        return set(dirs), list(globs)
    dirs: set[str] = set()
    globs: list[str] = []
    path = os.path.join(root, ".auditignore")
    if not os.path.exists(path):
        _IGNORE_CACHE[cache_key] = (set(dirs), list(globs))
        return dirs, globs
    try:
        with open(path, "r", encoding="utf-8") as fh:
            for raw in fh:
                line = raw.split("#", 1)[0].strip()
                if not line:
                    continue
                if line.endswith("/"):
                    dirs.add(line.rstrip("/"))
                else:
                    globs.append(line)
    except OSError as exc:
        print(f"warning: could not read .auditignore ({exc})", file=sys.stderr)
    _IGNORE_CACHE[cache_key] = (set(dirs), list(globs))
    return dirs, globs


def iter_files(exts, root: str = ".", extra_ignore_dirs=None,
               *, respect_scope: bool = True):
    """Yield POSIX-style relative paths of files under `root` matching `exts`.

    Results are sorted so reports are stable and diffable between runs.
    """
    root = os.path.abspath(root)
    ignore_dirs = set(DEFAULT_IGNORE_DIRS)
    ignore_globs = list(DEFAULT_IGNORE_GLOBS)
    extra_dirs, extra_globs = load_ignore_file(root)
    ignore_dirs |= extra_dirs
    ignore_globs += extra_globs
    if extra_ignore_dirs:
        ignore_dirs |= set(extra_ignore_dirs)

    exts = tuple(sorted({ext.lower() for ext in exts}))
    cache_key = (
        os.path.normcase(root),
        tuple(sorted(os.path.normcase(d) for d in ignore_dirs)),
        tuple(ignore_globs), respect_scope,
    )
    if cache_key not in _TREE_CACHE:
        ignored_dir_keys = {os.path.normcase(d) for d in ignore_dirs}
        found: list[str] = []
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = sorted(
                d for d in dirnames if os.path.normcase(d) not in ignored_dir_keys
            )
            for name in filenames:
                rel = os.path.relpath(os.path.join(dirpath, name), root)
                rel = rel.replace(os.sep, "/")
                if any(fnmatch.fnmatch(rel, g) or fnmatch.fnmatch(name, g)
                       for g in ignore_globs):
                    continue
                if respect_scope and _SCOPE is not None and rel not in _SCOPE:
                    continue
                found.append(rel)
        _TREE_CACHE[cache_key] = tuple(sorted(found))
    return [rel for rel in _TREE_CACHE[cache_key] if rel.lower().endswith(exts)]


def read_text(path: str) -> str:
    """Read a file as text, falling back to latin-1 rather than skipping it.

    A mis-encoded file is still worth scanning; silently dropping it would let a
    vulnerability hide behind a stray byte.
    """
    cache_key = os.path.normcase(os.path.abspath(path))
    if cache_key in _TEXT_CACHE:
        return _TEXT_CACHE[cache_key]
    try:
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read()
    except UnicodeDecodeError:
        try:
            with open(path, "r", encoding="latin-1") as fh:
                text = fh.read()
        except OSError as exc:
            raise ReadError(str(exc)) from exc
    except OSError as exc:
        raise ReadError(str(exc)) from exc
    _TEXT_CACHE[cache_key] = text
    return text


def is_fragment_path(rel_path: str) -> bool:
    """True when the file lives in a views/templates/partials/fragments dir."""
    return any(part in FRAGMENT_DIRS for part in rel_path.split("/")[:-1])


def strip_block_comments(text: str) -> str:
    """Remove /* ... */ comments, preserving newlines so line numbers hold."""
    def _blank(match: re.Match) -> str:
        return re.sub(r"[^\n]", " ", match.group(0))
    return re.sub(r"/\*.*?\*/", _blank, text, flags=re.DOTALL)


def mask_strings(line: str) -> str:
    """Blank out quoted string bodies so their contents can't trip a regex.

    Length is preserved so column positions stay meaningful.
    """
    def _blank(match: re.Match) -> str:
        body = match.group(0)
        return body[0] + ("x" * (len(body) - 2)) + body[-1]
    return re.sub(r'"[^"\n]*"|\'[^\'\n]*\'', _blank, line)


def is_comment_line(stripped: str, ext: str) -> bool:
    """Cheap single-line comment test, used to cut obvious false positives."""
    if stripped.startswith(("//", "/*", "*")):
        return True
    if ext in (".php", ".py") and stripped.startswith("#"):
        return True
    return False


class Report:
    """Collects findings and prints them compactly.

    `advisory=True` marks a tool whose findings need human judgement (unused
    CSS, file size, documentation hygiene) rather than blocking the gate.
    """

    def __init__(self, tool: str, advisory: bool = False):
        self.tool = tool
        self.advisory = advisory
        self.items: list[dict] = []
        self.unreadable: list[dict] = []
        self.accepted = 0
        self.scanned = 0

    def add(self, path: str, line: int | None, rule: str, message: str) -> None:
        self.items.append(
            {"file": path, "line": line, "rule": rule, "message": message}
        )

    def unread(self, path: str, reason: str) -> None:
        self.unreadable.append({"file": path, "reason": reason})

    @property
    def ok(self) -> bool:
        return not self.items and not self.unreadable

    @property
    def exit_code(self) -> int:
        if self.advisory:
            return 0
        return 0 if self.ok else 1

    def emit(self, args) -> int:
        """Print the report in the requested format. Returns an exit code."""
        if getattr(args, "json", False):
            print(json.dumps({
                "tool": self.tool,
                "advisory": self.advisory,
                "scanned": self.scanned,
                "findings": self.items,
                "unreadable": self.unreadable,
                "accepted": self.accepted,
            }))
            return self.exit_code

        label = f"{self.tool}{' (advisory)' if self.advisory else ''}"
        if getattr(args, "quiet", False):
            issues = len(self.items) + len(self.unreadable)
            print(f"{label}: {issues} issue(s) / {self.scanned} file(s)")
            return self.exit_code

        if not self.items and not self.unreadable:
            print(f"=== {label}: clean ({self.scanned} files) ===")
            return 0

        if not self.items:
            print(f"=== {label}: incomplete ({self.scanned} files) ===")
            self._emit_unreadable()
            return self.exit_code

        print(f"=== {label}: {len(self.items)} finding(s) / {self.scanned} files ===")
        cap = getattr(args, "max", 15) or 0
        by_rule: dict[str, list[dict]] = {}
        for item in self.items:
            by_rule.setdefault(item["rule"], []).append(item)

        for rule in sorted(by_rule, key=lambda r: -len(by_rule[r])):
            group = by_rule[rule]
            print(f"[{rule}] {len(group)}")
            shown = group if cap == 0 else group[:cap]
            for item in shown:
                loc = f":{item['line']}" if item["line"] else ""
                print(f"  {item['file']}{loc}  {item['message']}")
            hidden = len(group) - len(shown)
            if hidden > 0:
                print(f"  ... +{hidden} more (--max 0 to list all)")

        self._emit_unreadable()
        return self.exit_code

    def _emit_unreadable(self) -> None:
        if not self.unreadable:
            return
        print(f"[UNREADABLE] {len(self.unreadable)} file(s) could not be scanned:")
        for item in self.unreadable[:5]:
            print(f"  {item['file']}  {item['reason']}")
        if len(self.unreadable) > 5:
            print(f"  ... +{len(self.unreadable) - 5} more")


def base_parser(description: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--path", default=".", metavar="DIR",
                        help="project root to scan (default: current directory)")
    parser.add_argument("--json", action="store_true",
                        help="machine-readable output")
    parser.add_argument("-q", "--quiet", action="store_true",
                        help="print counts only")
    parser.add_argument("--max", type=_nonnegative_int, default=15, metavar="N",
                        help="max findings shown per rule, 0 for all (default: 15)")
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument("--changed", action="store_true",
                       help="only scan files modified vs HEAD, plus untracked "
                            "ones - the usual choice when finishing a task")
    scope.add_argument("--since", metavar="REF",
                       help="only scan files changed since a git ref (e.g. main)")
    scope.add_argument("--staged", action="store_true",
                       help="only scan files staged for commit (pre-commit hook)")
    return parser


def _nonnegative_int(value: str) -> int:
    try:
        number = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if number < 0:
        raise argparse.ArgumentTypeError("must be zero or greater")
    return number


def cli(run_fn, description: str) -> None:
    """Standard entry point: parse args, run, emit, exit with the right code."""
    args = base_parser(description).parse_args()
    apply_scope(args, args.path)
    try:
        report = run_fn(args)
    except KeyboardInterrupt:
        sys.exit(130)
    sys.exit(report.emit(args))
