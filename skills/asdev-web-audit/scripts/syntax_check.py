"""Real syntax check for PHP and JavaScript via the actual interpreters.

The regex scanners can only find patterns; this tool asks `php -l` and
`node --check` whether each changed file actually parses. It exists because a
missing brace ships to production more often than a SQL injection does, and
nothing else in the suite would catch it.

Notes
-----
* PHP binary resolution: $AUDIT_PHP > `php` on PATH > the XAMPP default.
  Node: $AUDIT_NODE > `node` on PATH > the standard Windows install path.
* A missing interpreter skips that language with a note - it never fails the
  run, because these scripts serve machines that may have only one runtime.
* JS files are checked as an ES module first (the house style), then retried
  as CommonJS; a finding is reported only when BOTH parses fail, so IIFE
  scripts and legacy files don't false-positive.
* .ts files are skipped: type-checking needs tsc and a tsconfig; a syntax-only
  gate would give false confidence.

Run from a project root. Supports --changed / --since like the other tools.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _common import Report, cli, iter_files, read_text, ReadError  # noqa: E402

PHP_FALLBACKS = [r"C:\xampp\php\php.exe", "/opt/lampp/bin/php"]
NODE_FALLBACKS = [r"C:\Program Files\nodejs\node.exe"]
PHP_LINE = re.compile(r" on line (\d+)")
NODE_LINE = re.compile(r":(\d+)\n")


def find_php() -> str | None:
    env = os.environ.get("AUDIT_PHP")
    if env and os.path.exists(env):
        return env
    on_path = shutil.which("php")
    if on_path:
        return on_path
    for candidate in PHP_FALLBACKS:
        if os.path.exists(candidate):
            return candidate
    return None


def find_node() -> str | None:
    env = os.environ.get("AUDIT_NODE")
    if env and os.path.exists(env):
        return env
    on_path = shutil.which("node")
    if on_path:
        return on_path
    return next((path for path in NODE_FALLBACKS if os.path.isfile(path)), None)


def _run(cmd: list[str]) -> tuple[int, str]:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError) as exc:
        return 1, str(exc)
    return proc.returncode, (proc.stderr or "") + (proc.stdout or "")


def check_php(php: str, root: str, rel: str) -> tuple[str, int | None, str] | None:
    code, output = _run([php, "-l", os.path.join(root, rel)])
    if code == 0:
        return None
    match = PHP_LINE.search(output)
    line = int(match.group(1)) if match else None
    message = output.strip().splitlines()[0] if output.strip() else "parse error"
    # Strip the redundant absolute path php echoes back.
    message = re.sub(r" in .*? on line", " on line", message)
    return rel, line, message


def check_js(node: str, root: str, rel: str) -> tuple[str, int | None, str] | None:
    try:
        source = read_text(os.path.join(root, rel))
    except ReadError as exc:
        return rel, None, f"unreadable: {exc}"

    errors = []
    for suffix in (".mjs", ".cjs"):
        handle, temp_path = tempfile.mkstemp(suffix=suffix)
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as fh:
                fh.write(source)
            code, output = _run([node, "--check", temp_path])
        finally:
            try:
                os.unlink(temp_path)
            except OSError:
                pass
        if code == 0:
            return None  # parses in at least one module mode
        errors.append(output)

    output = errors[0]
    match = NODE_LINE.search(output)
    line = int(match.group(1)) if match else None
    detail = next((ln for ln in output.splitlines()
                   if "Error" in ln), "syntax error").strip()
    return rel, line, detail


def run(args) -> Report:
    report = Report("syntax_check")
    root = args.path
    php = find_php()
    node = find_node()

    jobs = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        if php:
            for rel in iter_files([".php"], root):
                report.scanned += 1
                jobs.append(pool.submit(check_php, php, root, rel))
        else:
            print("note: php not found (set AUDIT_PHP) - PHP syntax not checked",
                  file=sys.stderr)
        if node:
            for rel in iter_files([".js"], root):
                report.scanned += 1
                jobs.append(pool.submit(check_js, node, root, rel))
        else:
            print("note: node not found (set AUDIT_NODE) - JS syntax not checked",
                  file=sys.stderr)

    for job in jobs:
        result = job.result()
        if result:
            rel, line, message = result
            if message.startswith("unreadable: "):
                report.unread(rel, message.removeprefix("unreadable: "))
                continue
            rule = "PHP_SYNTAX" if rel.endswith(".php") else "JS_SYNTAX"
            report.add(rel, line, rule, message)
    return report


if __name__ == "__main__":
    cli(run, "Syntax-check PHP (php -l) and JS (node --check).")
