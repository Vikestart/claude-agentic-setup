"""File-hygiene sweep: the checks that have actually broken things (from the work setup, 2026-10-30).

    python hygiene.py <path> [--floor 3.10] [--quiet]

Checks, per file:
  BOM          PowerShell 5.1's `Out-File -Encoding utf8` / `Set-Content -Encoding utf8` add one.
               A BOM in a .py file makes ast.parse fail; in a commit-message file it lands an
               invisible character in the commit subject.
  floor        Parses .py against the supported Python floor, not the installed interpreter.
  f-string \\   A backslash inside an f-string replacement field is a SyntaxError before 3.12 —
               and `ast.parse(feature_version=...)` does NOT catch it, so it needs its own scan.
               This has shipped twice.
  endings      Mixed CRLF/LF inside one file, and stray CR not part of a CRLF (a real CR once
               got written into a file by backslash-escaping through a shell heredoc). Reports
               only; crlf.py repairs.
  whitespace   Trailing whitespace and hard tabs.

Exit: 0 clean - 1 findings - 2 operational.
"""
import argparse
import ast
import re
import sys
from pathlib import Path

SKIP_DIRS = {".git", "__pycache__", "node_modules", ".ruff_cache", ".pytest_cache", "backups"}


def fstring_backslash_line(text: str) -> int | None:
    """First line where a backslash sits inside an f-string replacement field, or None.

    Tokenize rather than regex. A regex over source cannot tell an actual f-string from the TEXT
    of one quoted inside an ordinary string — and a file that documents this very trap in its own
    test data then reports a false positive. (That happened on the first version of this script.)
    Python >= 3.12 emits FSTRING_START/MIDDLE/END; earlier versions hand back one STRING token, so
    both shapes are handled.
    """
    import io
    import tokenize
    try:
        toks = list(tokenize.generate_tokens(io.StringIO(text).readline))
    except (tokenize.TokenError, SyntaxError, IndentationError):
        return None
    fstart = getattr(tokenize, "FSTRING_START", None)
    if fstart is not None:
        depth = 0
        for t in toks:
            if t.type == fstart:
                depth += 1
            elif depth and t.type == getattr(tokenize, "FSTRING_END", -1):
                depth -= 1
            elif depth and t.type == tokenize.STRING and "\\" in t.string:
                return t.start[0]
        return None
    for t in toks:                                    # pre-3.12: one STRING token per f-string
        if t.type != tokenize.STRING:
            continue
        prefix = t.string[:3].lower()
        if "f" not in prefix.split('"')[0].split("'")[0]:
            continue
        body = t.string
        i, in_field = 0, False
        while i < len(body):
            c = body[i]
            if c == "{":
                in_field = not (i + 1 < len(body) and body[i + 1] == "{")
                i += 1 if in_field else 2
                continue
            if c == "}":
                in_field = False
            elif c == "\\" and in_field:
                return t.start[0]
            i += 1
    return None


def parse_floor(s: str) -> tuple:
    try:
        major, minor = s.split(".")
        return int(major), int(minor)
    except ValueError:
        raise SystemExit(f"error: --floor wants MAJOR.MINOR, got {s!r}")


def check(path: Path, floor: tuple) -> list:
    out = []
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        out.append("BOM")
    crlf, cr = raw.count(b"\r\n"), raw.count(b"\r")
    lf = raw.count(b"\n") - crlf
    if cr - crlf:
        out.append(f"{cr - crlf} stray CR (not part of CRLF)")
    if crlf and lf:
        out.append(f"mixed endings ({crlf} CRLF, {lf} LF)")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        return out + [f"not valid UTF-8: {exc}"]
    repl = chr(0xFFFD)          # by codepoint, so this file does not contain what it looks for
    if repl in text:
        out.append(f"{text.count(repl)} replacement char(s) — likely mojibake")
    for n, line in enumerate(text.splitlines(), 1):
        if line.rstrip() != line:
            out.append(f"trailing whitespace L{n}")
            break
    if "\t" in text and path.suffix == ".py":
        out.append("hard tab(s)")
    if path.suffix == ".py":
        try:
            ast.parse(text, feature_version=floor)
        except SyntaxError as exc:
            out.append(f"does not parse on {floor[0]}.{floor[1]}: {exc.msg} (L{exc.lineno})")
        hit = fstring_backslash_line(text)
        if hit:
            out.append(f"backslash inside an f-string field L{hit} — SyntaxError before 3.12")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Sweep files for the encoding/syntax traps that bite here.")
    ap.add_argument("path")
    ap.add_argument("--floor", default="3.10", help="Python floor to parse against (default 3.10)")
    ap.add_argument("--quiet", action="store_true", help="totals only")
    a = ap.parse_args()

    root = Path(a.path).expanduser().resolve()
    floor = parse_floor(a.floor)
    if root.is_file():
        files = [root]
    elif root.is_dir():
        files = [p for p in sorted(root.rglob("*"))
                 if p.is_file() and p.suffix in {".py", ".md", ".json", ".txt"}
                 and not SKIP_DIRS & set(p.parts)]
    else:
        print(f"error: no such path: {root}", file=sys.stderr)
        return 2
    if not files:
        print(f"error: nothing to scan under {root}", file=sys.stderr)
        return 2

    bad = 0
    for f in files:
        issues = check(f, floor)
        if issues:
            bad += 1
            if not a.quiet:
                print(f"  {f.relative_to(root) if root.is_dir() else f.name}")
                for i in issues:
                    print(f"      {i}")
    print(f"\n{len(files)} files scanned, {bad} with findings"
          f" (floor {floor[0]}.{floor[1]})")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
