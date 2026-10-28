"""Tests for tasks_done.py, through its command line.

Each check holds one promise the docstring makes: finished items leave task.md with their
continuation lines and land verbatim in the month's archive, an item with an open sub-item stays
while a finished sub-item of an open item moves, a second run moves nothing and appends to the same
archive, CRLF survives, and --check exits 1 exactly when finished tasks remain.
Prints one line per check and `N/N ok` last; exit 1 on any failure.
"""
import datetime
import subprocess
import sys
import tempfile
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
results: list = []

TASKS = """# P — Current task queue

## Active tasks

**A phase.** Its note stays.
- [x] Done one: first line
  and its continuation.
- [ ] Open one.
- [x] Done parent with an open child
  - [ ] the open child
- [ ] Open parent
  - [x] finished child
  - [ ] open child
- [X] Done two.
"""


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append(bool(ok))
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f": {detail}"))


def tool(root: Path, *args: str) -> tuple:
    p = subprocess.run([sys.executable, str(TOOLS / "tasks_done.py"), "--path", str(root), *args],
                       capture_output=True)
    return p.returncode, (p.stdout + p.stderr).decode("utf-8", "replace")


def project(text: str, newline: str = "\n") -> Path:
    root = Path(tempfile.mkdtemp())
    (root / ".docs").mkdir()
    (root / ".docs" / "task.md").write_bytes(text.replace("\n", newline).encode("utf-8"))
    return root


archive_rel = Path(".docs", "reference", "archive", f"{datetime.date.today():%Y-%m}", "tasks-done.md")

root = project(TASKS)
code, out = tool(root, "--check")
check("--check exits 1 with finished tasks", code == 1 and "3 finished" in out, out)
check("--check changes nothing", (root / ".docs" / "task.md").read_text(encoding="utf-8") == TASKS)

code, out = tool(root)
left = (root / ".docs" / "task.md").read_text(encoding="utf-8")
archive = (root / archive_rel).read_text(encoding="utf-8") if (root / archive_rel).is_file() else ""
check("moves the three finished items", code == 0 and "moved 3" in out, out)
check("finished items and continuations leave task.md",
      "Done one" not in left and "its continuation" not in left and "Done two" not in left
      and "finished child" not in left, left)
check("open items, an open child's parent and notes stay",
      all(s in left for s in ("Open one.", "Done parent with an open child", "the open child",
                              "Open parent", "open child", "**A phase.**")), left)
check("the archive holds them verbatim under today's date",
      f"## {datetime.date.today().isoformat()}" in archive and "- [x] Done one: first line\n  and its continuation."
      in archive and "- [x] finished child" in archive and "- [X] Done two." in archive, archive)
check("the reminder names the changelog", "changelog.md" in out, out)

code, out = tool(root)
check("a second run moves nothing", code == 0 and "none finished" in out, out)
code, out = tool(root, "--check")
check("--check exits 0 once clean", code == 0, out)

(root / ".docs" / "task.md").write_text(left + "- [x] Later.\n", encoding="utf-8")
tool(root)
again = (root / archive_rel).read_text(encoding="utf-8")
check("a later run appends to the same archive", again.startswith(archive) and "- [x] Later." in again
      and again.count("# Finished tasks") == 1, again)

crlf = project(TASKS, "\r\n")
tool(crlf)
data = (crlf / ".docs" / "task.md").read_bytes()
check("CRLF survives", b"\r\n" in data and b"\n" not in data.replace(b"\r\n", b""), repr(data[:80]))

code, out = tool(Path(tempfile.mkdtemp()))
check("no task.md is operational", code == 2, out)

print(f"{sum(results)}/{len(results)} ok")
sys.exit(0 if all(results) else 1)
