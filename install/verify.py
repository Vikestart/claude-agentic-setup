"""Run every check the shared setup has; one line each, exit 1 if any fails.

Paths go through ~/.claude, not the repo folder, so a pass proves what a session actually sees
through the links. Full output of each check goes to a log; only a failure's tail is printed.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HOME = Path.home() / ".claude"
REPO = Path(__file__).resolve().parent.parent
AUDIT = HOME / "skills" / "asdev-web-audit" / "scripts"


def checks(gate_roots: list[Path]) -> list[tuple[str, list[str], str]]:
    py = sys.executable
    found = [
        ("web-audit self-test", [py, str(AUDIT / "self_test.py")], ""),
        ("blueprints self-test", [py, str(HOME / "skills" / "asdev-blueprints" / "scripts" / "self_test.py")], ""),
        ("harness parity", [py, str(AUDIT / "harness_parity.py")], ""),
        ("AGENTS.md in sync", [py, str(AUDIT / "sync_agents_md.py"), "--check"], ""),
        ("credentials guard tests", [py, str(HOME / "hooks" / "test_guard_credentials.py")], r"^\d+/\d+ ok"),
        ("context guard tests", [py, str(HOME / "hooks" / "test_context_guard.py")], r"^\d+/\d+ ok"),
        ("context window tests", [py, str(HOME / "hooks" / "test_context_window.py")], r"^\d+/\d+ ok"),
    ]
    setup_tests = REPO / "install" / "test_setup.py"
    if setup_tests.is_file():
        found.append(("setup tests", [py, str(setup_tests)], r"^(Ran \d+ tests?|OK|FAILED).*"))
    for root in gate_roots:
        found.append((f"gate {root}", [py, str(AUDIT / "audit_all.py"), "-q", "--path", str(root)],
                      r"=== audit: .*"))
    return found


def last_line(text: str, pattern: str) -> str:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if pattern:
        hits = [ln for ln in lines if re.search(pattern, ln)]
        if hits:
            return hits[-1]
    return lines[-1] if lines else "(no output)"


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--gate", action="append", type=Path, default=[],
                    help="extra folder for the audit gate (repeatable); the default set is always run")
    args = ap.parse_args()

    gate_roots = [HOME / "hooks", *sorted(HOME.joinpath("skills").glob("asdev-*")), *args.gate]
    log_dir = Path(tempfile.mkdtemp(prefix="setup-verify-"))
    failed = 0
    for name, argv, pattern in checks(gate_roots):
        start = time.monotonic()
        proc = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", errors="replace")
        output = proc.stdout + proc.stderr
        log = log_dir / (re.sub(r"[^\w.-]+", "_", name)[:80] + ".log")
        log.write_text(output, encoding="utf-8")
        ok = proc.returncode == 0
        failed += not ok
        print(f"{'PASS' if ok else 'FAIL'}  {name}: {last_line(output, pattern)}  "
              f"({time.monotonic() - start:.1f}s)")
        if not ok:
            for ln in output.splitlines()[-15:]:
                print(f"      {ln}")
    print(f"{'OK' if not failed else 'FAILED'}: {failed} of {len(checks(gate_roots))} checks failed; logs in {log_dir}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
