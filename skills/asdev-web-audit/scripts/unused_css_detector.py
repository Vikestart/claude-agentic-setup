"""Report CSS classes and IDs that appear unreferenced in a web project.

Advisory by design. The predecessor tested usage with a bare word-boundary
search over raw file text, so a class counted as "used" if its name appeared in
any comment, variable or unrelated string - it almost never reported anything.
This version collects real usage sites instead:

  * class="..." / className="..." attribute tokens
  * id="..." attributes
  * tokens inside JS/PHP string literals (covers querySelector('.x'),
    classList.add('x'), and class lists built in template strings)

That is still a heuristic. Classes assembled at runtime (`'btn-' + kind`) cannot
be seen statically, so the tool reports when it detects dynamic class handling
and you should treat every hit as "worth checking", never as proof.

Run from a project root. See _common.py for shared behaviour and .auditignore.
"""

from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _common import (  # noqa: E402
    Report, ReadError, cli, iter_files, read_text, strip_block_comments,
)

CLASS_ATTR = re.compile(r"class(?:Name)?\s*=\s*[\"']([^\"']*)[\"']", re.IGNORECASE)
ID_ATTR = re.compile(r"\bid\s*=\s*[\"']([^\"']*)[\"']", re.IGNORECASE)
STRING_LITERAL = re.compile(r"[\"'`]([^\"'`\n]{1,300})[\"'`]")
SELECTOR_TOKEN = re.compile(r"[.#]?([A-Za-z_][\w-]*)")
DYNAMIC_CLASS = re.compile(
    r"classList\.(?:add|remove|toggle)\s*\(\s*[^\"'`)]"   # classList.add(variable)
    r"|class(?:Name)?\s*=\s*[^\"'\n;]*\$\{"               # className = `...${x}`
    r"|class=\"[^\"]*\$\{"                                # class="...${x}"
    r"|class=\"[^\"]*<\?"                                 # class="<?= $x ?>"
)

# Selectors that exist for the browser or for other tooling, not for markup.
IGNORED_NAMES = {
    "root", "html", "body", "hidden", "sr-only", "visually-hidden",
    "no-js", "js", "is-loading", "active", "open", "show", "hide",
}


def collect_used_tokens(root: str, report: Report) -> tuple[set[str], bool]:
    """Return every identifier that looks like it names a class or id in use."""
    used: set[str] = set()
    dynamic = False

    # Usage is whole-project context even when only changed CSS is the finding
    # target. Scoping this corpus made unchanged markup disappear and produced
    # false UNUSED_CLASS findings in --changed/--staged runs.
    for rel in iter_files([".html", ".htm", ".php", ".js", ".ts"], root,
                          respect_scope=False):
        try:
            text = read_text(os.path.join(root, rel))
        except ReadError as exc:
            report.unread(rel, str(exc))
            continue

        if DYNAMIC_CLASS.search(text):
            dynamic = True

        for value in CLASS_ATTR.findall(text):
            used.update(value.split())
        for value in ID_ATTR.findall(text):
            used.add(value.strip())
        # String literals catch selector queries and class lists built in JS.
        for value in STRING_LITERAL.findall(text):
            for token in SELECTOR_TOKEN.findall(value):
                used.add(token)

    return used, dynamic


def extract_selectors(text: str) -> tuple[set[str], set[str]]:
    classes: set[str] = set()
    ids: set[str] = set()
    text = strip_block_comments(text)
    for chunk in text.split("}"):
        if "{" not in chunk:
            continue
        selector_group = chunk.split("{")[0]
        for selector in selector_group.split(","):
            selector = selector.strip()
            if not selector or selector.startswith("@"):
                continue
            for prefix, name in re.findall(r"([.#])([A-Za-z_][\w-]*)", selector):
                (classes if prefix == "." else ids).add(name)
    return classes, ids


def run(args) -> Report:
    report = Report("unused_css", advisory=True)
    root = args.path
    used, dynamic = collect_used_tokens(root, report)

    for rel in iter_files([".css"], root):
        try:
            text = read_text(os.path.join(root, rel))
        except ReadError as exc:
            report.unread(rel, str(exc))
            continue
        report.scanned += 1
        classes, ids = extract_selectors(text)

        for name in sorted(classes - used - IGNORED_NAMES):
            report.add(rel, None, "UNUSED_CLASS", f".{name}")
        for name in sorted(ids - used - IGNORED_NAMES):
            report.add(rel, None, "UNUSED_ID", f"#{name}")

    if dynamic and report.items:
        report.add("-", None, "DYNAMIC_CLASSES_PRESENT",
                   "this project builds class names at runtime; verify each hit "
                   "against the JS before deleting anything")
    return report


if __name__ == "__main__":
    cli(run, "Find CSS selectors with no apparent usage (advisory).")
