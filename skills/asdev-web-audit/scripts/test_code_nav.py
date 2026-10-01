#!/usr/bin/env python3
"""Fixture tests for code_map.py and code_show.py.

WHY THIS EXISTS. A map that is wrong by a few lines is worse than none: an agent trusts the
range, prints half a function and edits it. Every item in the fixtures under fixtures/code_nav/
carries `<start:KIND:NAME>` / `<end:KIND:NAME>` markers, and the expected ranges are read from
them — so moving a line in a fixture moves the expectation with it. An item the scripts find
without a marker fails as spurious (a class inside a heredoc, a function in a docblock).

    python $HOME/.claude/skills/asdev-web-audit/scripts/test_code_nav.py

Prints one line per check and `N/N ok` last; exit 1 on any failure.
"""
from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures" / "code_nav"
sys.path.insert(0, str(HERE))
import code_map  # noqa: E402

MARK = re.compile(r"<(start|end):([a-z]+):([^>]+)>")
results: list = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append(bool(ok))
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f": {detail}"))


def run(script: str, *args: str) -> "tuple[int, str]":
    p = subprocess.run([sys.executable, str(HERE / script), *args], capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    return p.returncode, p.stdout + p.stderr


def markers(path: Path) -> dict:
    exp: dict = {}
    for i, line in enumerate(path.read_text(encoding="utf-8").split("\n"), 1):
        for m in MARK.finditer(line):
            exp.setdefault((m.group(2), m.group(3)), {})[m.group(1)] = i
    return exp


def line_of(path: Path, needle: str) -> int:
    for i, line in enumerate(path.read_text(encoding="utf-8").split("\n"), 1):
        if needle in line:
            return i
    raise AssertionError(f"fixture {path.name} has no line containing {needle!r}")


def key_of(it, exp: dict) -> tuple:
    if it.kind in ("block", "banner"):
        for kind, name in exp:
            if kind == it.kind and it.name.startswith(name):
                return kind, name
    return it.kind, it.name


def test_ranges(lang: str, path: Path) -> None:
    exp = markers(path)
    fm = code_map.load(path)
    got: dict = {}
    for it in fm.items:
        k = key_of(it, exp)
        if k in got:
            check(f"{lang} duplicate {k[0]} {k[1]}", False, f"lines {got[k]} and {it.start}-{it.end}")
        got[k] = (it.start, it.end)
    for (kind, name), se in sorted(exp.items()):
        want, have = (se.get("start"), se.get("end")), got.get((kind, name))
        detail = (f"expected {want[0]}-{want[1]}, got {have[0]}-{have[1]}" if have
                  else f"expected {want[0]}-{want[1]}, not found")
        check(f"{lang} range {kind} {name}", have == want, detail)
    spurious = [k for k in got if k not in exp]
    for k in spurious:
        check(f"{lang} spurious {k[0]} {k[1]}", False, f"lines {got[k][0]}-{got[k][1]}, no marker")
    if not spurious:
        check(f"{lang} no spurious items", True)


def numbered(out: str) -> list:
    return [int(m.group(1)) for m in re.finditer(r"^\s*(\d+)  ", out, re.M)]


def test_show(php: Path, js: Path, py: Path) -> None:
    exp = markers(php)
    s1, e1 = exp[("function", "brace_in_string")]["start"], exp[("function", "brace_in_string")]["end"]
    s2, e2 = exp[("method", "Shape::count")]["start"], exp[("method", "Shape::count")]["end"]
    code, out = run("code_show.py", str(php), "brace_in_string", "Shape::count")
    check("show two targets in one call", code == 0 and "=== brace_in_string (function)" in out
          and "=== Shape::count (method)" in out, out[:300])
    check("show prints exactly the lines of each target",
          numbered(out) == list(range(s1, e1 + 1)) + list(range(s2, e2 + 1)), str(numbered(out)))

    code, out = run("code_show.py", str(php), "Shape.count")
    check("show accepts either separator", code == 0 and "=== Shape::count (method)" in out, out[:200])

    code, out = run("code_show.py", str(php), "brace_in_string", "--context", "2")
    check("show --context widens the range", numbered(out) == list(range(s1 - 2, e1 + 3)), str(numbered(out)))

    code, out = run("code_show.py", str(php), f"@{line_of(php, 'return $fn($y)')}")
    check("show @LINE picks the innermost item", code == 0 and "=== $cb (closure)" in out, out[:200])

    code, out = run("code_show.py", str(php), "run")
    check("show ambiguous target lists candidates and exits 1", code == 1 and "ambiguous" in out
          and "Shape::run" in out and "Runner::run" in out and "===" not in out, out[:300])
    code, out = run("code_show.py", str(php), "run", "--all")
    check("show --all prints every candidate", code == 0 and out.count("=== ") == 2, out[:300])

    code, out = run("code_show.py", str(php), "brace_in_strng")
    check("show unknown target lists close names", code == 1 and "unknown target" in out
          and "brace_in_string" in out, out[:300])

    code, out = run("code_show.py", str(php), "brace_in_string", "no_such_thing_here")
    check("show prints the found target even when another is unknown",
          code == 1 and "=== brace_in_string" in out and "unknown target" in out, out[:300])

    code, out = run("code_show.py", str(php), "second test PARAGRAPH")
    check("show block by label substring", code == 0 and "(block)" in out
          and "Second test paragraph" in out, out[:200])
    code, out = run("code_show.py", str(php), "second check name")
    check("show block by the check name inside it", code == 0 and "Second test paragraph" in out, out[:200])

    code, out = run("code_show.py", str(js), "render")
    check("show js exact name wins over a method's short name",
          code == 0 and "=== render (function)" in out and "Widget.render" not in out, out[:200])
    code, out = run("code_show.py", str(js), "Widget::render")
    check("show js qualified method", code == 0 and "=== Widget.render (method)" in out, out[:200])
    code, out = run("code_show.py", str(py), "deep")
    check("show py bare method name", code == 0 and "=== Outer.Inner.deep (method)" in out, out[:200])

    for script in ("code_show.py", "code_map.py"):
        extra = ["x"] if script == "code_show.py" else []
        code, out = run(script, str(FIX / "missing.php"), *extra)
        check(f"{script} missing file exits 2", code == 2 and "no such file" in out, out[:200])
        code, out = run(script, str(HERE / "run_audit.sh"), *extra)
        check(f"{script} unsupported extension exits 2", code == 2 and "unsupported extension" in out, out[:200])


def test_map_cli(php: Path) -> None:
    code, out = run("code_map.py", str(php), "--match", "brace")
    rows = [ln for ln in out.splitlines()[1:] if re.match(r"\s*\d+-\d+", ln)]
    check("map --match filters by name", code == 0 and len(rows) == 3
          and all("brace_in_" in r for r in rows), out[:300])
    code, out = run("code_map.py", str(php), "--match", "second check")
    check("map --match finds a block by its check name", "<- check 'second check name'" in out, out[:300])

    fm = code_map.load(php)
    code, out = run("code_map.py", str(php), "--min-lines", "10")
    rows = [ln for ln in out.splitlines()[1:] if re.match(r"\s*\d+-\d+", ln)]
    want = sum(1 for it in fm.items if it.size >= 10)
    check("map --min-lines drops short items", len(rows) == want and want > 0, f"{len(rows)} rows, want {want}")
    check("map first line counts items per kind", out.splitlines()[0].startswith(f"{php.name}: "), out[:120])

    with tempfile.TemporaryDirectory() as tmp:
        big = Path(tmp) / "big.php"
        n = code_map.LIST_LIMIT + 50
        big.write_text("<?php\n" + "".join(f"// Test number {i}\ncheck('case {i}', true);\n" for i in range(n)),
                       encoding="utf-8")
        code, out = run("code_map.py", str(big))
        rows = [ln for ln in out.splitlines() if re.match(r"\s*\d+-\d+", ln)]
        check("map over the limit hides blocks and hints --match",
              code == 0 and "--match" in out and f"{n} block" in out and not rows, out[:300])
        code, out = run("code_map.py", str(big), "--match", f"number {n - 1}$")
        rows = [ln for ln in out.splitlines() if re.match(r"\s*\d+-\d+", ln)]
        check("map over the limit still finds a block by --match", len(rows) == 1, out[:300])


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    php, js, py = FIX / "sample.php", FIX / "sample.js", FIX / "sample.py"
    test_ranges("php", php)
    test_ranges("js", js)
    test_ranges("py", py)
    tags = [it.tags for it in code_map.load(php).items if it.name.startswith("Second test paragraph")]
    check("php block collects its check names", tags == [["second check name"]], str(tags))
    test_show(php, js, py)
    test_map_cli(php)
    print(f"{sum(results)}/{len(results)} ok")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
