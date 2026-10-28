"""Tests for docs_init.py, through its command line and its importable `missing()`.

Each check holds one promise the docstring makes: an empty folder gets the whole skeleton and a
second run creates nothing, no existing byte is ever overwritten, a CLAUDE.md without the import
is reported and edited only under --link (once), a CLAUDE.md with its own rules gets no AGENTS.md
skeleton, and --check exits 1 exactly when something is missing.
Prints one line per check and `N/N ok` last; exit 1 on any failure.
"""
import subprocess
import sys
import tempfile
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import docs_init  # noqa: E402

TARGETS = [target for target, _ in docs_init.FILES]
results: list = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append(bool(ok))
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f": {detail}"))


def tool(root: Path, *args: str) -> tuple:
    p = subprocess.run([sys.executable, str(TOOLS / "docs_init.py"), "--path", str(root), *args],
                       capture_output=True)
    return p.returncode, (p.stdout + p.stderr).decode("utf-8", "replace")


def snapshot(root: Path) -> dict:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def test_empty(tmp: Path) -> None:
    code, out = tool(tmp, "--check")
    check("--check on an empty folder exits 1 and writes nothing",
          code == 1 and "MISSING AGENTS.md" in out and not any(tmp.iterdir()), out)
    check("missing() names the three top-level gaps",
          docs_init.missing(tmp) == ["AGENTS.md", "CLAUDE.md", ".docs/ (working documents and reference/)"],
          repr(docs_init.missing(tmp)))
    code, out = tool(tmp)
    created = [l.split(" ", 1)[1] for l in out.splitlines() if l.startswith("created ")]
    check("an empty folder gets every item", code == 0 and created == TARGETS, out)
    check("CLAUDE.md is exactly the import", (tmp / "CLAUDE.md").read_bytes() == b"@AGENTS.md\n")
    agents = (tmp / "AGENTS.md").read_text(encoding="utf-8")
    check("templates are rendered with the folder name",
          agents.startswith(f"# {tmp.resolve().name} ") and "<Project>" not in agents, agents[:120])
    check("missing() is empty when complete", docs_init.missing(tmp) == [], repr(docs_init.missing(tmp)))
    before = snapshot(tmp)
    code, out = tool(tmp)
    check("a second run creates nothing and changes nothing",
          code == 0 and "created" not in out and snapshot(tmp) == before, out)
    code, out = tool(tmp, "--check")
    check("--check on a complete repo exits 0", code == 0 and "ok - complete" in out, out)


def test_partial(tmp: Path) -> None:
    (tmp / ".docs").mkdir()
    (tmp / "AGENTS.md").write_bytes(b"# mine\r\n")
    (tmp / ".docs" / "task.md").write_bytes(b"\xef\xbb\xbfmy tasks\n")
    check("missing() lists absent .docs files one by one",
          ".docs/roadmap.md" in docs_init.missing(tmp) and ".docs/task.md" not in docs_init.missing(tmp)
          and ".docs/changelog.md" in docs_init.missing(tmp), repr(docs_init.missing(tmp)))
    code, out = tool(tmp)
    check("existing files are never overwritten (byte-compare)",
          (tmp / "AGENTS.md").read_bytes() == b"# mine\r\n"
          and (tmp / ".docs" / "task.md").read_bytes() == b"\xef\xbb\xbfmy tasks\n"
          and "created .docs/task.md" not in out and "created .docs/roadmap.md" in out, out)


def test_claude_rules(tmp: Path) -> None:
    body = b"# Rules\r\n\r\n- be careful\r\n"
    (tmp / "CLAUDE.md").write_bytes(body)
    gaps = docs_init.missing(tmp)
    check("a CLAUDE.md with its own rules: missing() says to move them and to import",
          "AGENTS.md (move CLAUDE.md's rules into it)" in gaps and "the @AGENTS.md import in CLAUDE.md" in gaps,
          repr(gaps))
    code, out = tool(tmp)
    check("without --link the CLAUDE.md is reported, not edited, and no AGENTS.md skeleton appears",
          code == 1 and "WRONG   CLAUDE.md" in out and "TODO    AGENTS.md" in out
          and (tmp / "CLAUDE.md").read_bytes() == body and not (tmp / "AGENTS.md").exists(), out)
    code, out = tool(tmp, "--link")
    check("--link prepends the import and a blank line in the file's own endings",
          (tmp / "CLAUDE.md").read_bytes() == b"@AGENTS.md\r\n\r\n" + body and "linked" in out, out)
    code, out = tool(tmp, "--link")
    check("a second --link adds nothing",
          (tmp / "CLAUDE.md").read_bytes() == b"@AGENTS.md\r\n\r\n" + body and "linked" not in out, out)
    check("still exit 1 while AGENTS.md is missing", code == 1 and "AGENTS.md (move" in out, out)


def test_bare_claude(tmp: Path) -> None:
    (tmp / "CLAUDE.md").write_bytes(b"\xef\xbb\xbf\n")
    code, out = tool(tmp, "--link")
    check("an empty CLAUDE.md gets the AGENTS.md skeleton and, under --link, the import after its BOM",
          code == 0 and "created AGENTS.md" in out
          and (tmp / "CLAUDE.md").read_bytes() == b"\xef\xbb\xbf@AGENTS.md\n\n\n", out)


def test_operational(tmp: Path) -> None:
    code, out = tool(tmp / "absent")
    check("a missing --path exits 2", code == 2, out)
    code, out = tool(tmp, "--check", "--link")
    check("--check and --link together are refused", code == 2, out)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    for test in (test_empty, test_partial, test_claude_rules, test_bare_claude, test_operational):
        with tempfile.TemporaryDirectory() as d:
            test(Path(d))
    print(f"{sum(results)}/{len(results)} ok (ok={sum(results)})")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
