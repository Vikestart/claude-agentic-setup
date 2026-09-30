"""Run a command with its output in a log, and print one line.

WHY THIS EXISTS. Every line a command prints into a session is re-read on every later turn.
Measured 2026-09-30: one Nebulingo builder made 441 shell calls whose test output landed in its
context, and re-reading that history was ~90% of its 31M-token cost. A suite needs one verdict
line in the context, not its whole output; the full output belongs in a file you can open if the
verdict is red.

USAGE

    quiet.py -- python scripts/run_tests.py
    quiet.py --summary "passed|failed" -- php tests/run.php
    quiet.py --shell -- "npm test && npm run lint"      (one string, run by bash)

Without --shell no shell is involved: the arguments are the command, and the program is found on
PATH the way a shell would find it (npm.cmd included). With --shell the ONE string after -- runs
under bash — Git Bash on Windows, never cmd.exe, whose quoting silently changes what runs (a
`python -c '...'` string exits 0 having done nothing), and never WSL's bash in System32.

Prints:  exit=<code> | <summary line> | <seconds>s | log=<path>
and, only when the command failed, its last --tail lines.

The summary line is the last output line matching --summary, or the last non-empty line.
quiet.py exits with the command's own exit code (124 on timeout, 127 if it could not start), so
it can stand in for the command anywhere an exit code is the verdict. A timeout kills the whole
process tree, so a battery cannot keep resetting a database after quiet.py has returned. Under `falsify.py`, wrap
falsify itself (`quiet.py -- python falsify.py ...`) rather than the suite: falsify matches its
`expect` text against the suite's full output, which quiet.py deliberately does not print.
falsify's last line counts its warnings, so they survive into the one-line summary.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

SUMMARY_MAX = 200


def default_log(cmd: list[str]) -> Path:
    # Outside the project on purpose: a log inside the repo is one more untracked file to trip
    # the audit gate, and nothing about it belongs in git.
    slug = re.sub(r"[^A-Za-z0-9]+", "-", " ".join(cmd))[:40].strip("-") or "cmd"
    folder = Path(tempfile.gettempdir()) / "quiet"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / f"{datetime.now():%Y%m%d-%H%M%S-%f}-{os.getpid()}-{slug}.log"


def pick_summary(lines: list[str], pattern: str | None) -> str:
    if pattern:
        rx = re.compile(pattern)
        for line in reversed(lines):
            if rx.search(line):
                return line.strip()
    for line in reversed(lines):
        if line.strip():
            return line.strip()
    return "(no output)"


def find_bash() -> str | None:
    git_bash = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Git" / "bin" / "bash.exe"
    for candidate in (shutil.which("bash"), str(git_bash)):
        if not candidate or not os.path.isfile(candidate):
            continue
        low = candidate.lower().replace("/", "\\")
        if os.name == "nt" and ("\\system32\\" in low or "\\windowsapps\\" in low):
            continue  # WSL's bash: a different machine, with none of this project's tools
        return candidate
    return None


def resolve(cmd: list[str], use_shell: bool) -> list[str] | str:
    """The argv to start, or a string saying why nothing can start."""
    if use_shell:
        bash = find_bash()
        if not bash:
            return "no bash found for --shell (install Git for Windows, or drop --shell)"
        return [bash, "-c", cmd[0]]
    exe = shutil.which(cmd[0])
    if not exe:
        hint = " (a whole command in one string needs --shell)" if len(cmd) == 1 and " " in cmd[0] else ""
        return f"program not found: {cmd[0]}{hint}"
    return [exe, *cmd[1:]]


def kill_tree(proc: subprocess.Popen) -> None:
    if os.name == "nt":
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except OSError:
            proc.kill()


def run(cmd: list[str], log: Path, timeout: float | None, use_shell: bool) -> int:
    argv = resolve(cmd, use_shell)
    with log.open("wb") as out:
        if isinstance(argv, str):
            out.write(f"quiet.py: could not start: {argv}\n".encode("utf-8"))
            return 127
        try:
            proc = subprocess.Popen(argv, stdout=out, stderr=subprocess.STDOUT,
                                    stdin=subprocess.DEVNULL, start_new_session=os.name != "nt")
        except OSError as exc:
            out.write(f"quiet.py: could not start: {exc}\n".encode("utf-8"))
            return 127
        try:
            return proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            # Killing only the direct child left a battery running and writing to the database
            # after quiet.py had already reported the timeout.
            kill_tree(proc)
            proc.wait()
            out.write(f"\nquiet.py: killed after {timeout}s timeout (whole process tree)\n".encode("utf-8"))
            return 124


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if "--" not in argv:
        print("usage: quiet.py [--summary REGEX] [--tail N] [--log PATH] [--timeout S] [--shell] -- <cmd>",
              file=sys.stderr)
        return 2
    split = argv.index("--")
    ap = argparse.ArgumentParser(prog="quiet.py", description=__doc__.split("\n\n")[0])
    ap.add_argument("--summary", help="regex; the last matching output line is the summary")
    ap.add_argument("--tail", type=int, default=20, help="lines shown on failure (default 20)")
    ap.add_argument("--log", type=Path, help="log file (default: a new file under the temp dir)")
    ap.add_argument("--timeout", type=float, help="kill the command after this many seconds")
    ap.add_argument("--shell", action="store_true", help="run the one string after -- under bash")
    args = ap.parse_args(argv[:split])
    cmd = argv[split + 1:]
    if not cmd:
        print("quiet.py: no command after --", file=sys.stderr)
        return 2
    if args.shell and len(cmd) != 1:
        print("quiet.py: --shell takes exactly one string after --", file=sys.stderr)
        return 2

    log = args.log or default_log(cmd)
    log.parent.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    code = run(cmd, log, args.timeout, args.shell)
    elapsed = time.monotonic() - start

    # Decode with replacement: a suite printing cp1252 or raw bytes must not crash the one line
    # that reports it.
    lines = log.read_bytes().decode("utf-8", errors="replace").splitlines()
    summary = pick_summary(lines, args.summary)
    if len(summary) > SUMMARY_MAX:
        summary = summary[:SUMMARY_MAX - 1] + "…"

    # The console may be cp1252; the log path or summary must never crash the report.
    try:
        sys.stdout.reconfigure(errors="replace")
    except (AttributeError, ValueError):
        pass
    print(f"exit={code} | {summary} | {elapsed:.1f}s | log={log}")
    if code != 0 and args.tail > 0:
        tail = [line for line in lines if line.strip()][-args.tail:]
        print("\n".join(tail))
    return code


if __name__ == "__main__":
    sys.exit(main())
