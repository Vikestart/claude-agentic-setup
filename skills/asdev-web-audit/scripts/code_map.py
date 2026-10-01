#!/usr/bin/env python3
"""Outline of a PHP, JS or Python file, with line ranges, so an agent can find what it needs
without paging through it.

WHY THIS EXISTS. Measured 2026-10-01: subagents in the owner's PHP projects spent most of their
context on file dumps while navigating huge files — tilspire `tests/run.php` (27k lines) was read
in slices 80+ times, nebulingo `includes/lesson_authoring.php` (15k lines, 288 functions) the
same way. One map call, then `code_show.py` for exactly the item needed, replaces those slices.

What is mapped: classes, interfaces, traits, enums, functions, methods (`Class::method` in PHP,
`Class.method` in JS and Python) and closures or arrow functions assigned to a name. Brace
matching skips strings, PHP heredoc/nowdoc and inline HTML, JS template literals (with `${…}`
nesting) and regex literals, and comments; Python uses indentation. Top-level code is mapped too:
a column-0 comment paragraph followed by code starts a BLOCK labelled by its first line (that is
how run.php separates its tests), and banner comments (`// === Title ===`, `# --- Title`) start a
BANNER section that runs to the next banner.

    python $HOME/.claude/skills/asdev-web-audit/scripts/code_map.py includes/lesson_authoring.php
    python $HOME/.claude/skills/asdev-web-audit/scripts/code_map.py tests/run.php --match "store audit"
    python $HOME/.claude/skills/asdev-web-audit/scripts/code_map.py assets/js/app.js --min-lines 40

--match searches names, block and banner labels, and the names given to check()/test()/it()/
describe() calls inside a block. Over 200 items without --match, blocks are counted but not listed.
Exit 0; 2 for a missing file or an unsupported extension (.php .js .mjs .py). Read-only.
"""
from __future__ import annotations

import argparse
import bisect
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

LANGS = {".php": "php", ".js": "js", ".mjs": "js", ".py": "py"}
LIST_LIMIT = 200
LABEL_MAX = 80
CLASS_KINDS = ("class", "interface", "trait", "enum")
CODE_KINDS = CLASS_KINDS + ("function", "method", "closure")
# Order among items with the same range: the wider concept first, so it becomes the parent.
KIND_RANK = {"banner": 0, "block": 1, "class": 2, "interface": 2, "trait": 2, "enum": 2,
             "function": 3, "method": 3, "def": 3, "closure": 4}
TEST_CALL_RE = re.compile(r"""\b(?:check|test|it|describe)\(\s*(['"])((?:\\.|(?!\1).)*)\1""")


class MapError(Exception):
    """A file that cannot be mapped at all: missing, or an unsupported extension (exit 2)."""


@dataclass
class Item:
    kind: str
    name: str
    start: int
    end: int
    tags: list = field(default_factory=list)
    depth: int = 0
    parent: "Item | None" = None

    @property
    def size(self) -> int:
        return self.end - self.start + 1


# ---- scanners: (start, end, kind) spans to blank out; kind c=comment s=string x=not code ----

_SQ = re.compile(r"[^'\\]*(?:\\.[^'\\]*)*'", re.S)
_DQ = re.compile(r'[^"\\]*(?:\\.[^"\\]*)*"', re.S)
_BQ = re.compile(r"[^`\\]*(?:\\.[^`\\]*)*`", re.S)
# JS and Python quotes end at the line unless the newline is escaped.
_SQ_LINE = re.compile(r"[^'\\\n]*(?:\\(?:.|\n)[^'\\\n]*)*'?")
_DQ_LINE = re.compile(r'[^"\\\n]*(?:\\(?:.|\n)[^"\\\n]*)*"?')


def _close(rx: re.Pattern, text: str, i: int) -> int:
    m = rx.match(text, i)
    return m.end() if m else len(text)


def _line_end(text: str, i: int) -> int:
    e = text.find("\n", i)
    return len(text) if e < 0 else e


_PHP_OPEN = re.compile(r"<\?(?:php\b|=|(?!xml))", re.I)
_PHP_TOK = re.compile(r"\?>|'|\"|`|//|#(?!\[)|/\*|<<<")
_HEREDOC = re.compile(r"<<<[ \t]*(['\"]?)([A-Za-z_]\w*)\1[ \t]*\r?\n")


def scan_php(text: str) -> list:
    spans, n, i = [], len(text), 0
    while i < n:
        m = _PHP_OPEN.search(text, i)
        if not m:
            spans.append((i, n, "x"))
            break
        if m.start() > i:
            spans.append((i, m.start(), "x"))
        i = m.end()
        while i < n:
            t = _PHP_TOK.search(text, i)
            if not t:
                i = n
                break
            s, tok = t.start(), t.group()
            if tok == "?>":
                i = t.end()
                break
            if tok == "'":
                e, kind = _close(_SQ, text, s + 1), "s"
            elif tok == '"':
                e, kind = _close(_DQ, text, s + 1), "s"
            elif tok == "`":
                e, kind = _close(_BQ, text, s + 1), "s"
            elif tok == "/*":
                e = text.find("*/", s + 2)
                e, kind = (n if e < 0 else e + 2), "c"
            elif tok == "<<<":
                h = _HEREDOC.match(text, s)
                if not h:
                    i = t.end()
                    continue
                # PHP 7.3+: the closing identifier may be indented and followed by anything
                # that is not an identifier character.
                c = re.compile(r"^[ \t]*" + h.group(2) + r"\b", re.M).search(text, h.end())
                e, kind = (c.end() if c else n), "s"
            else:
                e = _line_end(text, s)
                q = text.find("?>", s, e)  # `?>` ends a line comment in PHP
                e, kind = (q if q >= 0 else e), "c"
            spans.append((s, e, kind))
            i = e
    return spans


_JS_TOK = re.compile(r"'|\"|`|//|/\*|/|\{|\}")
_TPL = re.compile(r"[^`\\$]*(?:(?:\\.|\$(?!\{))[^`\\$]*)*", re.S)
_REGEX_AFTER_WORDS = {"return", "typeof", "case", "do", "else", "in", "of", "new", "delete",
                      "void", "throw", "instanceof", "yield", "await"}


def _tpl(text: str, s: int, spans: list, stack: list) -> int:
    """Scan template text from the backtick or the `}` that closed an interpolation at `s`."""
    q = _TPL.match(text, s + 1).end()
    if q >= len(text):
        spans.append((s, len(text), "s"))
        return len(text)
    if text[q] == "`":
        spans.append((s, q + 1, "s"))
        return q + 1
    spans.append((s, q + 2, "s"))  # up to and including `${`
    stack.append("t")
    return q + 2


def _regex_allowed(text: str, s: int) -> bool:
    j = s - 1
    while j >= 0 and text[j] in " \t\r\n":
        j -= 1
    if j < 0:
        return True
    c = text[j]
    if c in ")]}'\"`":
        return False
    if c.isalnum() or c in "_$":
        k = j
        while k >= 0 and (text[k].isalnum() or text[k] in "_$"):
            k -= 1
        return text[k + 1:j + 1] in _REGEX_AFTER_WORDS
    return True


def _regex_end(text: str, s: int) -> "int | None":
    k, n, in_class = s + 1, len(text), False
    while k < n:
        ch = text[k]
        if ch == "\\":
            k += 2
            continue
        if ch == "\n":
            return None
        if in_class:
            in_class = ch != "]"
        elif ch == "[":
            in_class = True
        elif ch == "/":
            k += 1
            while k < n and (text[k].isalnum() or text[k] == "_"):
                k += 1
            return k
        k += 1
    return None


def scan_js(text: str) -> list:
    spans, n, i, stack = [], len(text), 0, []
    if text.startswith("#!"):
        i = _line_end(text, 0)
        spans.append((0, i, "c"))
    while i < n:
        t = _JS_TOK.search(text, i)
        if not t:
            break
        s, tok = t.start(), t.group()
        if tok == "{":
            stack.append("b")
            i = s + 1
        elif tok == "}":
            if stack and stack[-1] == "t":
                stack.pop()
                i = _tpl(text, s, spans, stack)
            else:
                if stack:
                    stack.pop()
                i = s + 1
        elif tok == "`":
            i = _tpl(text, s, spans, stack)
        elif tok in ("'", '"'):
            e = _close(_SQ_LINE if tok == "'" else _DQ_LINE, text, s + 1)
            spans.append((s, e, "s"))
            i = e
        elif tok == "//":
            e = _line_end(text, s)
            spans.append((s, e, "c"))
            i = e
        elif tok == "/*":
            e = text.find("*/", s + 2)
            e = n if e < 0 else e + 2
            spans.append((s, e, "c"))
            i = e
        else:
            e = _regex_end(text, s) if _regex_allowed(text, s) else None
            if e:
                spans.append((s, e, "s"))
                i = e
            else:
                i = s + 1
    return spans


_PY_TOK = re.compile(r"#|'''|\"\"\"|'|\"")


def _triple_end(text: str, i: int, q: str) -> int:
    while True:
        e = text.find(q, i)
        if e < 0:
            return len(text)
        k = e - 1
        while k >= i and text[k] == "\\":
            k -= 1
        if (e - 1 - k) % 2 == 0:
            return e + 3
        i = e + 1


def scan_py(text: str) -> list:
    spans, n, i = [], len(text), 0
    while i < n:
        t = _PY_TOK.search(text, i)
        if not t:
            break
        s, tok = t.start(), t.group()
        if tok == "#":
            e, kind = _line_end(text, s), "c"
        elif len(tok) == 3:
            e, kind = _triple_end(text, s + 3, tok), "s"
        else:
            e, kind = _close(_SQ_LINE if tok == "'" else _DQ_LINE, text, s + 1), "s"
        spans.append((s, e, kind))
        i = e
    return spans


SCANNERS = {"php": scan_php, "js": scan_js, "py": scan_py}


def blank_out(text: str, spans: list) -> str:
    out, last = [], 0
    for s, e, _ in spans:
        out.append(text[last:s])
        out.append("\n".join(" " * len(part) for part in text[s:e].split("\n")))
        last = e
    out.append(text[last:])
    return "".join(out)


# ---- brace structure ----

class Braces:
    def __init__(self, cleaned: str):
        self.pos, self.inner, self.depth, self.close = [], [], [], {}
        stack: list = []
        for m in re.finditer(r"[{}]", cleaned):
            p = m.start()
            if cleaned[p] == "{":
                stack.append(p)
            elif stack:
                self.close[stack.pop()] = p
            self.pos.append(p)
            self.inner.append(stack[-1] if stack else -1)
            self.depth.append(len(stack))
        for p in stack:
            self.close[p] = len(cleaned) - 1

    def enclosing(self, p: int) -> int:
        """Innermost `{` open at position p (strictly before it), or -1."""
        k = bisect.bisect_left(self.pos, p)
        return self.inner[k - 1] if k else -1

    def depth_at(self, p: int) -> int:
        k = bisect.bisect_left(self.pos, p)
        return self.depth[k - 1] if k else 0


def _paren_end(cleaned: str, p: int) -> int:
    depth = 0
    for m in re.compile(r"[()]").finditer(cleaned, p):
        depth += 1 if m.group() == "(" else -1
        if depth == 0:
            return m.start()
    return len(cleaned) - 1


_BODY_OR_END = re.compile(r"[{;]")


def _body_end(cleaned: str, br: Braces, p: int) -> "tuple[int, int] | None":
    """From p (just past a declaration's parameters) to its `{` body: (open, close), or for a
    body-less declaration (`abstract function f();`) the `;` as both."""
    m = _BODY_OR_END.search(cleaned, p)
    if not m:
        return None
    if m.group() == ";":
        return m.start(), m.start()
    return m.start(), br.close.get(m.start(), len(cleaned) - 1)


def _expr_end(cleaned: str, p: int) -> int:
    """End of an expression body (`fn () => …`, `x => …`): the `;` at nesting 0, a closing
    bracket of the enclosing scope, or the end of a line that does not continue."""
    depth, n = 0, len(cleaned)
    i = p
    while i < n:
        ch = cleaned[i]
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
            if depth < 0:
                return i - 1
        elif depth == 0 and (ch == ";" or ch == ","):
            return i
        elif depth == 0 and ch == "\n":
            before = cleaned[p:i].rstrip()
            after = cleaned[i + 1:i + 200].lstrip()
            if before and before[-1] not in "=+-*/%&|?:,(.<>!" and (not after or after[0] not in ".?:+-*/%&|"):
                return i - 1
        i += 1
    return n - 1


def _strip_marker(line: str) -> str:
    s = re.sub(r"^\s*(?://+|#+|/\*+|\*+)\s?", "", line).rstrip()
    if s.endswith("*/"):
        s = s[:-2].rstrip()
    return s.strip()


def _label(text: str) -> str:
    return text if len(text) <= LABEL_MAX else text[:LABEL_MAX - 3] + "..."


_FILL = r"([=\-#*~_])\1{2,}"
_BANNER = re.compile(r"(?://+|#|/\*)\s*" + _FILL + r"(.*)$")


def banner_label(stripped: str) -> "str | None":
    """'' for a pure rule line, the title for `// === Title ===`, None for any other line."""
    m = _BANNER.match(stripped)
    if not m:
        return None
    rest = m.group(2).strip()
    if rest.endswith("*/"):
        rest = rest[:-2].rstrip()
    return re.sub(r"\s*" + _FILL + r"\s*$", "", rest).strip(" \t=-#*~_")


# ---- item finders per language ----

_PHP_CLASS = re.compile(r"(?<![\w$\\:>])(?:(?:abstract|final|readonly)\s+)*\b(class|interface|trait|enum)\s+([A-Za-z_]\w*)")
_PHP_ANON = re.compile(r"\bnew\s+class\b")
_PHP_FUNC = re.compile(r"(?<![\w$>:])function\b\s*&?\s*([A-Za-z_]\w*)\s*\(")
_PHP_CLOSURE = re.compile(r"(\$[A-Za-z_]\w*(?:(?:->|::)\$?[A-Za-z_]\w*)*)\s*=(?![=>])\s*(?:static\s+)?(function|fn)\b\s*&?\s*\(")


def _php_items(cleaned: str, br: Braces) -> list:
    """(kind, name, start_pos, end_pos, body_open)"""
    found = []
    for m in _PHP_CLASS.finditer(cleaned):
        if re.search(r"\bnew\s*$", cleaned[max(0, m.start() - 20):m.start()]):
            continue
        b = _body_end(cleaned, br, m.end())
        if b and b[0] != b[1]:
            found.append([m.group(1), m.group(2), m.start(), b[1], b[0]])
    for m in _PHP_ANON.finditer(cleaned):
        q = m.end()
        if re.match(r"\s*\(", cleaned[q:q + 50]):
            q = _paren_end(cleaned, cleaned.index("(", q)) + 1
        b = _body_end(cleaned, br, q)
        if b and b[0] != b[1]:
            found.append(["class", "class@anonymous", m.start(), b[1], b[0]])
    for m in _PHP_FUNC.finditer(cleaned):
        b = _body_end(cleaned, br, _paren_end(cleaned, m.end() - 1) + 1)
        if b:
            found.append(["function", m.group(1), m.start(), b[1], b[0]])
    for m in _PHP_CLOSURE.finditer(cleaned):
        q = _paren_end(cleaned, m.end() - 1) + 1
        if m.group(2) == "fn":
            end = _expr_end(cleaned, q)
            found.append(["closure", m.group(1), m.start(), end, -1])
        else:
            b = _body_end(cleaned, br, q)
            if b and b[0] != b[1]:
                found.append(["closure", m.group(1), m.start(), b[1], b[0]])
    return found


_JS_CLASS = re.compile(r"(?<![\w$.])class\s+([A-Za-z_$][\w$]*)")
_JS_FUNC = re.compile(r"(?<![\w$.])function\b\s*\*?\s*([A-Za-z_$][\w$]*)\s*\(")
_JS_ASSIGN = re.compile(r"(?<![\w$.#])((?:[A-Za-z_$][\w$]*)(?:\.#?[A-Za-z_$][\w$]*)*)\s*=(?![=>])\s*(?:async\s+)?"
                        r"(function\b\s*\*?\s*[\w$]*\s*\(|(?:\([^()]*(?:\([^()]*\)[^()]*)*\)|[A-Za-z_$][\w$]*)\s*=>)")
_JS_METHOD = re.compile(r"^[ \t]*(?:(?:static|async|get|set|override|public|private|protected|readonly)[ \t]+)*"
                        r"\*?[ \t]*(#?[A-Za-z_$][\w$]*)[ \t]*\(", re.M)
_JS_FIELD = re.compile(r"^[ \t]*(?:static[ \t]+)?(#?[A-Za-z_$][\w$]*)[ \t]*=(?![=>])[ \t]*(?:async[ \t]+)?"
                       r"(?:\([^()]*(?:\([^()]*\)[^()]*)*\)|[A-Za-z_$][\w$]*)[ \t]*=>", re.M)
_JS_KEYWORDS = {"if", "for", "while", "switch", "catch", "function", "return", "with", "do", "else"}


def _js_arrow_body(cleaned: str, br: Braces, p: int) -> "tuple[int, int]":
    """p is just past `=>`: a `{` body, or an expression body."""
    q = p
    while q < len(cleaned) and cleaned[q] in " \t\r\n":
        q += 1
    if q < len(cleaned) and cleaned[q] == "{":
        return q, br.close.get(q, len(cleaned) - 1)
    return -1, _expr_end(cleaned, q)


def _js_items(cleaned: str, br: Braces) -> list:
    found, bodies = [], set()
    classes = []
    for m in _JS_CLASS.finditer(cleaned):
        b = _body_end(cleaned, br, m.end())
        if b and b[0] != b[1]:
            found.append(["class", m.group(1), m.start(), b[1], b[0]])
            classes.append((m.group(1), b[0], b[1]))
    class_bodies = {o for _, o, _ in classes}
    for m in _JS_ASSIGN.finditer(cleaned):
        if br.enclosing(m.start()) in class_bodies:
            continue  # a class field: listed as a method below
        if m.group(2).startswith("function"):
            b = _body_end(cleaned, br, _paren_end(cleaned, m.end() - 1) + 1)
            if not b or b[0] == b[1]:
                continue
            open_, end = b
        else:
            open_, end = _js_arrow_body(cleaned, br, m.end())
        found.append(["closure", m.group(1), m.start(), end, open_])
        if open_ >= 0:
            bodies.add(open_)
    for m in _JS_FUNC.finditer(cleaned):
        b = _body_end(cleaned, br, _paren_end(cleaned, m.end() - 1) + 1)
        if b and b[0] != b[1] and b[0] not in bodies:
            found.append(["function", m.group(1), m.start(), b[1], b[0]])
    for cname, o, c in classes:
        for m in _JS_METHOD.finditer(cleaned, o + 1, c):
            name = m.group(1)
            if name in _JS_KEYWORDS or br.enclosing(m.start(1)) != o:
                continue
            q = _paren_end(cleaned, m.end() - 1) + 1
            rest = cleaned[q:q + 200].lstrip()
            if rest.startswith("{"):
                open_ = cleaned.index("{", q)
                found.append(["method", f"{cname}.{name}", m.start(1), br.close.get(open_, c), open_])
        for m in _JS_FIELD.finditer(cleaned, o + 1, c):
            if br.enclosing(m.start(1)) != o:
                continue
            open_, end = _js_arrow_body(cleaned, br, m.end())
            found.append(["method", f"{cname}.{m.group(1)}", m.start(1), end, open_])
    return found


# ---- the map ----

@dataclass
class FileMap:
    path: Path
    lang: str
    lines: list
    items: list


def _indent(s: str) -> int:
    return len(s.expandtabs(4)) - len(s.expandtabs(4).lstrip())


def load(path: "str | Path") -> FileMap:
    path = Path(path)
    lang = LANGS.get(path.suffix.lower())
    if not path.is_file():
        raise MapError(f"no such file: {path}")
    if not lang:
        raise MapError(f"unsupported extension '{path.suffix}' for {path} (supported: "
                       + " ".join(sorted(LANGS)) + ")")
    # newline="" keeps a lone CR from becoming a line break, so line numbers match grep's.
    with path.open(encoding="utf-8", errors="replace", newline="") as fh:
        text = fh.read().lstrip("﻿")
    spans = SCANNERS[lang](text)
    cleaned = blank_out(text, spans)
    lines = text.split("\n")
    clines = cleaned.split("\n")
    starts = [0]
    for m in re.finditer("\n", text):
        starts.append(m.end())

    def line_of(p: int) -> int:
        return bisect.bisect_right(starts, p)

    # What each line starts in: the span covering its first non-space character, if any.
    state, inside = [None] * len(lines), [False] * len(lines)
    span_col0 = [False] * len(lines)
    k = 0
    for i, ln in enumerate(lines):
        pos = starts[i] + (len(ln) - len(ln.lstrip()))
        while k < len(spans) and spans[k][1] <= pos:
            k += 1
        if k < len(spans) and spans[k][0] <= pos < spans[k][1]:
            s, _, kind = spans[k]
            state[i] = kind
            inside[i] = s < starts[i]
            span_col0[i] = s == starts[line_of(s) - 1]

    items: list = []
    br = None
    if lang == "py":
        items = _py_items(lines, clines, state, inside)
    else:
        br = Braces(cleaned)
        raw = _php_items(cleaned, br) if lang == "php" else _js_items(cleaned, br)
        seen = set()
        for kind, name, s, e, body in raw:
            key = (s, body if body >= 0 else e)
            if key in seen:
                continue
            seen.add(key)
            it = Item(kind, name, line_of(s), line_of(max(s, e)))
            it._body = body  # type: ignore[attr-defined]
            it._span = (s, max(s, e))  # type: ignore[attr-defined]
            items.append(it)
        _nest(items, key=lambda it: it._span)
        if lang == "php":
            for it in items:
                p = it.parent
                if it.kind == "function" and p and p.kind in CLASS_KINDS and br.enclosing(it._span[0]) == p._body:
                    it.kind, it.name = "method", f"{p.name}::{it.name}"

    top_depth = [0] * len(lines)
    if br:
        for i in range(len(lines)):
            top_depth[i] = br.depth_at(starts[i])
    in_item = [False] * (len(lines) + 2)
    decl_starts = set()
    for it in items:
        # Only declarations: a closure or `new class` inside a test chunk belongs to that chunk.
        if it.parent is None and it.kind in CLASS_KINDS + ("function",) and it.name != "class@anonymous":
            for ln in range(it.start, it.end + 1):
                in_item[ln] = True
            lead = it.start
            while lead > 1 and re.match(r"\s*(@|#\[)", lines[lead - 2]):
                lead -= 1
            decl_starts.add(lead)
    items += _sections(lang, lines, clines, state, inside, span_col0, top_depth, in_item, decl_starts, items)
    for it in items:
        it.parent = None
    _nest(items, key=lambda it: (it.start, it.end))
    items.sort(key=lambda it: (it.start, -it.end, KIND_RANK[it.kind]))
    return FileMap(path, lang, lines, items)


def _nest(items: list, key) -> None:
    """Parent = the smallest item whose span contains this one."""
    order = sorted(items, key=lambda it: (key(it)[0], -key(it)[1], KIND_RANK[it.kind]))
    stack: list = []
    for it in order:
        s, e = key(it)
        while stack and not (key(stack[-1])[0] <= s and e <= key(stack[-1])[1]):
            stack.pop()
        it.parent = stack[-1] if stack else None
        it.depth = len(stack)
        stack.append(it)


_PY_DEF = re.compile(r"^([ \t]*)(?:async[ \t]+)?(def|class)[ \t]+([A-Za-z_]\w*)")


def _py_items(lines: list, clines: list, state: list, inside: list) -> list:
    found = []
    n = len(lines)
    for i, cl in enumerate(clines):
        m = _PY_DEF.match(cl)
        if not m:
            continue
        ind = _indent(m.group(1))
        # A multi-line signature: skip to the line where its brackets balance.
        bal, j = 0, i
        while j < n:
            bal += sum(clines[j].count(c) for c in "([{") - sum(clines[j].count(c) for c in ")]}")
            if bal <= 0:
                break
            j += 1
        last, j = j, j + 1
        while j < n:
            cl2 = clines[j]
            if cl2.strip() and not inside[j] and _indent(cl2) <= ind:
                break
            if lines[j].strip() and (cl2.strip() or _indent(lines[j]) > ind or inside[j]):
                last = j
            j += 1
        found.append(Item(m.group(2), m.group(3), i + 1, last + 1))
    _nest(found, key=lambda it: (it.start, it.end))
    for it in sorted(found, key=lambda it: it.depth):
        p = it.parent
        if p and p.kind == "class":
            if it.kind == "def":
                it.kind = "method"
            it.name = f"{p.name}.{it.name}"
        if it.kind == "def":
            it.kind = "function"
    return found


def _sections(lang, lines, clines, state, inside, span_col0, top_depth, in_item, decl_starts, items) -> list:
    n = len(lines)

    def is_comment(i: int) -> bool:
        return bool(lines[i].strip()) and not clines[i].strip() and state[i] == "c"

    def col0(i: int) -> bool:
        return is_comment(i) and (not lines[i][:1].isspace() or (inside[i] and span_col0[i]))

    def top(i: int) -> bool:
        return top_depth[i] == 0 and not in_item[i + 1]

    # Banners, at any depth: a pure rule line takes its title from the next comment line.
    banners, rule_lines = [], set()
    i = 0
    while i < n:
        if is_comment(i) and not inside[i]:
            lab = banner_label(lines[i].strip())
            if lab is not None:
                start = i
                if lab == "" and i + 1 < n and is_comment(i + 1) and banner_label(lines[i + 1].strip()) is None:
                    lab = _strip_marker(lines[i + 1])
                    rule_lines.add(i + 1)
                    if i + 2 < n and is_comment(i + 2) and banner_label(lines[i + 2].strip()) == "":
                        rule_lines.add(i + 2)
                        i += 1
                    i += 1
                rule_lines.add(start)
                if lab:
                    banners.append((start, lab))
        i += 1

    containing = {}

    def scope(i: int) -> "tuple[int, int]":
        """(nesting, last line) of the innermost code item containing 0-based line i."""
        if i not in containing:
            best = None
            for it in items:
                if it.start <= i + 1 <= it.end and (best is None or it.size < best.size):
                    best = it
            containing[i] = (best.depth + 1, best.end - 1) if best else (0, n - 1)
        return containing[i]

    out = []
    for idx, (start, lab) in enumerate(banners):
        lvl, limit = scope(start)
        end = limit
        for s2, _ in banners[idx + 1:]:
            if s2 > limit:
                break
            if scope(s2)[0] <= lvl:
                end = s2 - 1
                break
        while end > start and not lines[end].strip():
            end -= 1
        out.append(Item("banner", _label(lab), start + 1, end + 1))

    # Blocks: column-0 comment paragraphs at the top level, followed by top-level code.
    paragraphs = []
    i = 0
    while i < n:
        if col0(i) and top(i) and i not in rule_lines:
            j = i
            while j + 1 < n and col0(j + 1) and top(j + 1) and (j + 1) not in rule_lines:
                j += 1
            paragraphs.append((i, j))
            i = j + 1
        else:
            i += 1
    # A banner inside a class or function does not cut a top-level block.
    boundaries = {p[0] for p in paragraphs} | {s for s, _ in banners if top(s)}
    boundaries |= {d - 1 for d in decl_starts} | {r for r in rule_lines if top(r)}
    starts_blocks = []
    for a, b in paragraphs:
        j = b + 1
        while j < n and not lines[j].strip():
            j += 1
        if j >= n or j in rule_lines or is_comment(j) or j in {d - 1 for d in decl_starts}:
            continue
        if top(j) and state[j] != "c":
            starts_blocks.append((a, b))
    bounds = sorted(boundaries)
    for a, b in starts_blocks:
        k = bisect.bisect_right(bounds, a)
        end = bounds[k] - 1 if k < len(bounds) else n - 1
        while end > b and not lines[end].strip():
            end -= 1
        text = ""
        for ln in range(a, b + 1):
            text = _strip_marker(lines[ln])
            if text:
                break
        tags = [m.group(2) for ln in range(b + 1, end + 1) for m in TEST_CALL_RE.finditer(lines[ln])]
        out.append(Item("block", _label(text or "(comment)"), a + 1, end + 1, tags=tags))
    return out


# ---- output ----

def describe(it: Item) -> str:
    return f'"{it.name}"' if it.kind in ("block", "banner") else it.name


def format_item(it: Item, width: int, note: str = "") -> str:
    rng = f"{it.start}-{it.end}"
    return f"{rng:>{width}} {it.size:>6}  {it.kind:<9} {'  ' * it.depth}{describe(it)}{note}"


def counts_line(fm: FileMap) -> str:
    counts: dict = {}
    for it in fm.items:
        counts[it.kind] = counts.get(it.kind, 0) + 1
    order = ["class", "interface", "trait", "enum", "function", "method", "closure", "banner", "block"]
    parts = [f"{counts[k]} {k}{'es' if k == 'class' and counts[k] != 1 else ('' if counts[k] == 1 else 's')}"
             for k in order if k in counts]
    return f"{fm.path.name}: {len(fm.lines)} lines; " + (", ".join(parts) if parts else "no items")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file")
    ap.add_argument("--match", help="case-insensitive regex over names, labels and check names")
    ap.add_argument("--min-lines", type=int, default=0, help="only items at least this long")
    ap.add_argument("--all", action="store_true", help="list blocks too when over the limit")
    a = ap.parse_args()
    try:
        fm = load(a.file)
    except MapError as e:
        print(f"code_map: {e}", file=sys.stderr)
        return 2
    try:
        rx = re.compile(a.match, re.I) if a.match else None
    except re.error as e:
        print(f"code_map: bad --match regex: {e}", file=sys.stderr)
        return 2
    rows = []
    for it in fm.items:
        if it.size < a.min_lines:
            continue
        note = ""
        if rx:
            if not rx.search(it.name):
                tag = next((t for t in it.tags if rx.search(t)), None)
                if tag is None:
                    continue
                note = f"  <- check '{_label(tag)}'"
        rows.append((it, note))
    print(counts_line(fm))
    if not rx and not a.all and len(rows) > LIST_LIMIT:
        hidden = sum(1 for it, _ in rows if it.kind in ("block", "closure"))
        rows = [r for r in rows if r[0].kind not in ("block", "closure")]
        if hidden:
            print(f"{len(rows) + hidden} items: {hidden} blocks and closures not listed - use "
                  f"--match REGEX (names, labels, check names), or --all")
    if rx and not rows:
        print(f"nothing matches {a.match!r}")
    width = max((len(f"{it.start}-{it.end}") for it, _ in rows), default=3)
    for it, note in rows:
        print(format_item(it, width, note))
    return 0


if __name__ == "__main__":
    sys.exit(main())
