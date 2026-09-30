"""Flag source files that have grown past the point of being easy to work on.

Oversized files cost review attention and context window alike: a 40 KB module
is read in full to change one function. The thresholds encode the house rule
that JS past ~15 KB should be split into ES modules and views past ~10 KB into
partials.

Defaults (override per project with .token-limits.json in the project root):

    {"assets/js": {"size_kb": 25, "lines": 500, "ext": [".js"]}}

Run from a project root. See _common.py for shared behaviour and .auditignore.
"""

from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _common import (  # noqa: E402
    Report, ReadError, cli, is_fragment_path, iter_files, read_text,
)

DEFAULTS = {
    "js": {"size_kb": 15.0, "lines": 300, "ext": (".js", ".ts")},
    "css": {"size_kb": 10.0, "lines": 200, "ext": (".css",)},
    "backend": {"size_kb": 15.0, "lines": 300, "ext": (".php", ".py", ".go")},
    "views": {"size_kb": 10.0, "lines": 200, "ext": (".html", ".htm")},
}

ALL_EXTS = (".js", ".ts", ".css", ".php", ".py", ".go", ".html", ".htm")

def comment_ratio(text: str, ext: str) -> float:
    """Share of lines that are comment — reported as CONTEXT on an already-oversized file, never
    as a finding of its own.

    A file being mostly prose is not a defect. Measured across this codebase's first-party tree,
    the longest comments are the most valuable ones (a lock namespace that stalled a deploy for
    900 s; a webhook that acknowledged work it never did) and only ~1.3% of comment lines were
    mechanically removable. So this number answers only the question you already have once a file
    is too big: split the code, or move the documentation to `.docs/reference/`?

    Counted LINE BY LINE, not by matching `/* ... */` across the file: a regex with `DOTALL` still
    swallowed everything after a line-initial `/*` that was inside a template literal, reporting a
    315-line source file as "99% comment lines". A line-based count cannot run away like that.
    """
    lines = text.splitlines()
    if len(lines) < 2:
        return 0.0
    hash_langs = (".php", ".py")
    n = 0
    for line in lines:
        s = line.strip()
        if not s:
            continue
        # A leading `*` is a block-comment continuation only when a space or the close follows.
        # `*{margin:0}` and `*,*::before` are universal selectors — counting them scored an ordinary
        # CSS reset sheet at 67% comments.
        if s.startswith(("/*", "*/", "//", "<!--", "-->")) or s == "*" or s.startswith("* "):
            n += 1
        elif ext.lower() in hash_langs and s.startswith("#") and not s.startswith("#["):
            n += 1
    return min(n / len(lines), 1.0)


def load_custom(root: str):
    path = os.path.join(root, ".token-limits.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict):
            print("warning: ignoring .token-limits.json (top level must be an object)",
                  file=sys.stderr)
            return None
        return data
    except (OSError, ValueError) as exc:
        print(f"warning: ignoring .token-limits.json ({exc})", file=sys.stderr)
        return None


def classify(rel: str) -> dict | None:
    ext = os.path.splitext(rel)[1]
    if ext in (".js", ".ts"):
        return DEFAULTS["js"]
    if ext == ".css":
        return DEFAULTS["css"]
    if ext in (".html", ".htm"):
        return DEFAULTS["views"]
    if ext == ".php":
        # A PHP fragment is a template; a PHP file elsewhere is logic.
        return DEFAULTS["views"] if is_fragment_path(rel) else DEFAULTS["backend"]
    if ext in (".py", ".go"):
        return DEFAULTS["backend"]
    return None


def check(report: Report, root: str, rel: str, rule: dict) -> None:
    path = os.path.join(root, rel)
    try:
        text = read_text(path)
    except ReadError as exc:
        report.unread(rel, str(exc))
        return
    report.scanned += 1

    size_kb = os.path.getsize(path) / 1024.0
    lines = text.count("\n") + 1
    limit_kb = float(rule.get("size_kb", 9999))
    limit_lines = int(rule.get("lines", 999999))

    reasons = []
    if size_kb > limit_kb:
        reasons.append(f"{size_kb:.1f}KB > {limit_kb}KB")
    if lines > limit_lines:
        reasons.append(f"{lines} lines > {limit_lines}")
    if reasons:
        ratio = comment_ratio(text, os.path.splitext(rel)[1])
        report.add(rel, None, "OVERSIZED",
                   f"{' & '.join(reasons)} ({ratio * 100:.0f}% comment lines)")


def run(args) -> Report:
    report = Report("token_analyzer", advisory=True)
    root = args.path
    custom = load_custom(root)

    if custom:
        rules: list[tuple[str, dict, set[str]]] = []
        all_exts: set[str] = set()
        for folder, rule in custom.items():
            if not isinstance(rule, dict):
                print(f"warning: ignoring token rule '{folder}' (not an object)",
                      file=sys.stderr)
                continue
            folder = str(folder).replace("\\", "/").strip("/")
            exts = rule.get("ext", [])
            if isinstance(exts, str):
                exts = [exts]
            exts = {str(ext).lower() for ext in exts if str(ext).startswith(".")}
            if not exts:
                continue
            rules.append((folder, rule, exts))
            all_exts.update(exts)

        # Iterate from the project root so Git scope paths and reported paths
        # stay project-relative. The previous folder-root walk compared
        # `app.js` with a scope containing `assets/js/app.js` and scanned zero.
        for rel in iter_files(tuple(all_exts), root):
            matches = [item for item in rules
                       if (not item[0] or rel == item[0]
                           or rel.startswith(item[0] + "/"))
                       and any(rel.lower().endswith(ext) for ext in item[2])]
            if not matches:
                continue
            _, rule, _ = max(matches, key=lambda item: len(item[0]))
            check(report, root, rel, rule)
    else:
        for rel in iter_files(ALL_EXTS, root):
            rule = classify(rel)
            if rule:
                check(report, root, rel, rule)

    return report


if __name__ == "__main__":
    cli(run, "Flag oversized source files (advisory).")
