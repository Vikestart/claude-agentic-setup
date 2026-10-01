"""Accessibility checks for HTML and PHP templates.

Covers the failures that are both common and statically visible: unlabelled
images and controls, missing document language, icon-only links that read as
nothing to a screen reader, and images without dimensions (which cause layout
shift). Contrast and focus order need a real browser - use Lighthouse or the
DevTools a11y pane for those.

Run from a project root. See _common.py for shared behaviour and .auditignore.
"""

from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _common import Report, ReadError, cli, iter_files, read_text  # noqa: E402

IMG_TAG = re.compile(r"<img\b([^>]*)>", re.IGNORECASE)
# Not after another `<`: a PHP heredoc opener `<<<HTML` is no tag (it flagged a fixture, 2026-10-01).
HTML_TAG = re.compile(r"(?<!<)<html\b([^>]*)>", re.IGNORECASE)
ANCHOR = re.compile(r"<a\b([^>]*)>(.*?)</a>", re.IGNORECASE | re.DOTALL)
BUTTON = re.compile(r"<button\b([^>]*)>(.*?)</button>", re.IGNORECASE | re.DOTALL)
INPUT_TAG = re.compile(r"<input\b([^>]*)>", re.IGNORECASE)
LABEL_FOR = re.compile(r"<label\b[^>]*\bfor\s*=\s*[\"']([^\"']+)[\"']", re.IGNORECASE)
TABINDEX = re.compile(r"tabindex\s*=\s*[\"']?([0-9]+)", re.IGNORECASE)
TAGS = re.compile(r"<[^>]+>")

ATTR = lambda name: re.compile(rf"\b{name}\s*=", re.IGNORECASE)  # noqa: E731
HAS_ALT = ATTR("alt")
HAS_LANG = ATTR("lang")
HAS_WIDTH = ATTR("width")
HAS_HEIGHT = ATTR("height")
HAS_ID = ATTR("id")
HAS_ARIA_LABEL = re.compile(r"\baria-label(?:ledby)?\s*=|\btitle\s*=", re.IGNORECASE)
HAS_ARIA_HIDDEN = re.compile(r"\baria-hidden\s*=\s*[\"']true", re.IGNORECASE)

SELF_LABELLING_INPUTS = {"hidden", "submit", "button", "reset", "image"}
INPUT_TYPE = re.compile(r"\btype\s*=\s*[\"']([^\"']+)[\"']", re.IGNORECASE)


def _line_at(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def _visible_text(inner: str) -> str:
    """Inner text with tags removed. PHP echo tags count as content."""
    if "<?" in inner:
        return "php"
    return TAGS.sub("", inner).replace("&nbsp;", " ").strip()


def run(args) -> Report:
    report = Report("a11y_audit")
    root = args.path

    for rel in iter_files([".html", ".htm", ".php"], root):
        try:
            text = read_text(os.path.join(root, rel))
        except ReadError as exc:
            report.unread(rel, str(exc))
            continue
        report.scanned += 1
        labelled_ids = set(LABEL_FOR.findall(text))

        for match in HTML_TAG.finditer(text):
            if not HAS_LANG.search(match.group(1)):
                report.add(rel, _line_at(text, match.start()), "HTML_NO_LANG",
                           "<html> has no lang attribute")

        for match in IMG_TAG.finditer(text):
            attrs = match.group(1)
            line = _line_at(text, match.start())
            if not HAS_ALT.search(attrs):
                report.add(rel, line, "IMG_NO_ALT",
                           "<img> has no alt attribute (use alt=\"\" if decorative)")
            if not (HAS_WIDTH.search(attrs) and HAS_HEIGHT.search(attrs)):
                report.add(rel, line, "IMG_NO_DIMS",
                           "<img> has no width/height; causes layout shift")

        for regex, rule, what in ((ANCHOR, "LINK_NO_TEXT", "link"),
                                  (BUTTON, "BUTTON_NO_TEXT", "button")):
            for match in regex.finditer(text):
                attrs, inner = match.group(1), match.group(2)
                if _visible_text(inner):
                    continue
                if HAS_ARIA_LABEL.search(attrs):
                    continue
                report.add(rel, _line_at(text, match.start()), rule,
                           f"icon-only or empty {what} with no accessible name "
                           "(add aria-label)")

        for match in INPUT_TAG.finditer(text):
            attrs = match.group(1)
            type_match = INPUT_TYPE.search(attrs)
            input_type = (type_match.group(1).lower() if type_match else "text")
            if input_type in SELF_LABELLING_INPUTS:
                continue
            if HAS_ARIA_LABEL.search(attrs) or HAS_ARIA_HIDDEN.search(attrs):
                continue
            id_match = re.search(r"\bid\s*=\s*[\"']([^\"']+)[\"']", attrs,
                                 re.IGNORECASE)
            if id_match and id_match.group(1) in labelled_ids:
                continue
            report.add(rel, _line_at(text, match.start()), "INPUT_NO_LABEL",
                       f"<input type={input_type}> has no <label for> or aria-label")

        for match in TABINDEX.finditer(text):
            if int(match.group(1)) > 0:
                report.add(rel, _line_at(text, match.start()), "POSITIVE_TABINDEX",
                           "positive tabindex fights natural focus order")

    return report


if __name__ == "__main__":
    cli(run, "Check templates for common accessibility failures.")
