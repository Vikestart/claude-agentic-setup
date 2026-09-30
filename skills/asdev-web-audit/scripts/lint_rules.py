"""House-style linter for web projects.

Enforces the conventions that are otherwise only written down in prose:
  * CSS: no space after ':' ; single-line rules stay space-free; rules with
    fewer than 6 properties stay on one line; media queries live at the bottom;
    an icon is never display:block (its glyph layers tear apart).
  * Views: fragments carry no page boilerplate and no inline <style>/<script>.
  * Markup: no inline event handlers (onclick=...) anywhere.
  * No leftover debug output shipped to production.

Run from a project root. See _common.py for shared behaviour and .auditignore.
"""

from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _common import (  # noqa: E402
    Report, ReadError, cli, is_comment_line, is_fragment_path, iter_files,
    mask_strings, read_text, strip_block_comments,
)

# At-rules whose bodies contain normal rules worth linting. @keyframes is
# excluded: its `from{}`/`50%{}` steps are legitimately short and multi-line.
NESTED_AT_RULES = ("@media", "@supports", "@layer", "@container")

FLEX_GRID_HINTS = (
    "display:flex", "display:grid", "display:inline-flex", "display:inline-grid",
    "grid-template", "flex-direction", "grid-area", "place-items",
)

# A FontAwesome duotone icon is TWO stacked glyph layers (`::before` plus an absolutely
# positioned `::after`). `display:block` pins the secondary layer to the box edge, which tears
# the layers apart AND un-centers the glyph — the root cause of every "icon looks broken /
# off-center" report so far. A standalone icon is `inline-block` inside a `text-align:center`
# parent: the parent centers the box, the layers stay aligned.
# A FontAwesome CLASS in the selector is proof the target is a glyph. Anchored on the dot: a bare
# `\bfa-` also matched any kebab class merely containing the letters (`.info-fa-badge`).
ICON_CLASS_RE = re.compile(r"\.fa[bdlrs]?-|\.fa[bdlrs]\b")
# A bare `<i>` element selector is only PROBABLY a glyph: `<i>` is also used as a lightweight
# box for bar charts, signal meters and skeleton placeholders, which are legitimately block.
# Those are shapes, not text — they set a background AND an explicit size, which a glyph
# (sized by font-size, painted as text) never does. Measured against the real stylesheets:
# without this discriminator the rule produced three false positives and zero true ones.
ICON_ELEMENT_RE = re.compile(r"(?:^|[\s>+~,])i(?=[\s.:\[,]|$)")
SHAPE_BODY_RE = re.compile(r"(?:^|;)background[a-z-]*:")
SIZED_BODY_RE = re.compile(
    r"(?:^|;)(?:min-|max-)?(?:width|height|block-size|inline-size):|(?:^|;)aspect-ratio:")
DISPLAY_BLOCK_RE = re.compile(r"(?:^|;)display:block(?:[;!]|$)")

BOILERPLATE_TAGS = ("html", "head", "body")
ASSET_TAGS = ("<style", "<script")

INLINE_HANDLER_RE = re.compile(r"\son[a-z]{3,}\s*=\s*[\"']", re.IGNORECASE)
ANCHOR_RE = re.compile(r"<a\b[^>]*>", re.IGNORECASE)
HREF_RE = re.compile(r"href=[\"']([^\"']*)[\"']", re.IGNORECASE)
EXTERNAL_HREF = ("http://", "https://", "//", "#", "mailto:", "tel:",
                 "javascript:", "<?", "{{", "{%")


def _line_of(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def parse_blocks(text: str, line_offset: int = 0) -> list[dict]:
    """Return top-level `{...}` blocks as {selector, body, start, end}.

    Strings are masked first so a brace inside content:"{" cannot desync the
    parser. Only depth-0 blocks are returned; callers recurse for at-rules.
    """
    masked = mask_strings(text)
    blocks: list[dict] = []
    depth = 0
    sel_start = 0
    selector = ""
    body_start = 0
    sel_line = 1

    for i, ch in enumerate(masked):
        if ch == "{":
            if depth == 0:
                raw_selector = masked[sel_start:i]
                selector = raw_selector.strip()
                # Measure from the selector's first real character. sel_start
                # sits just after the previous '}', so the newline and indent
                # between rules belong to no one - counting from there made
                # every single-line rule look like it spanned two.
                lead = len(raw_selector) - len(raw_selector.lstrip())
                body_start = i + 1
                sel_line = _line_of(masked, sel_start + lead) + line_offset
            depth += 1
        elif ch == "}":
            if depth == 0:
                sel_start = i + 1
                continue
            depth -= 1
            if depth == 0:
                blocks.append({
                    "selector": selector,
                    "body": text[body_start:i],
                    "start": sel_line,
                    "end": _line_of(masked, i) + line_offset,
                    "body_start_line": _line_of(masked, body_start) + line_offset,
                })
                sel_start = i + 1
    return blocks


def _all_rule_blocks(text: str, line_offset: int = 0) -> list[dict]:
    """Flatten top-level blocks plus rules nested inside @media/@supports/etc."""
    out: list[dict] = []
    for block in parse_blocks(text, line_offset):
        sel = block["selector"].lstrip()
        if sel.startswith("@"):
            if sel.lower().startswith(NESTED_AT_RULES):
                out.extend(_all_rule_blocks(block["body"],
                                            block["body_start_line"] - 1))
            continue
        out.append(block)
    return out


def lint_css(report: Report, root: str) -> None:
    for rel in iter_files([".css"], root):
        path = os.path.join(root, rel)
        try:
            raw = read_text(path)
        except ReadError as exc:
            report.unread(rel, str(exc))
            continue
        report.scanned += 1
        text = strip_block_comments(raw)

        for num, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            if not stripped or stripped.startswith("@import"):
                continue
            masked = mask_strings(line)

            if re.search(r":[ \t]", masked):
                report.add(rel, num, "CSS_SPACE_COLON",
                           "space after ':' (write color:#fff;)")

            # A complete one-line rule must be space-free between declarations.
            # Multi-line bodies may group pairs like `top:0; left:0;`.
            if "{" in masked and "}" in masked and re.search(r";[ \t]\S", masked):
                report.add(rel, num, "CSS_SPACE_SEMI",
                           "space between properties on a one-line rule")

        # Rules under 6 properties belong on one line unless they lay out
        # flex/grid, which is the one case the house style allows to breathe.
        for block in _all_rule_blocks(text):
            body = block["body"]
            decls = [d for d in body.split(";") if d.strip()]
            if not decls or len(decls) >= 6:
                continue
            if block["end"] == block["start"]:
                continue
            compact = re.sub(r"\s+", "", body).lower()
            if any(hint in compact for hint in FLEX_GRID_HINTS):
                continue
            report.add(rel, block["start"], "CSS_MULTILINE",
                       f"{len(decls)} properties split over "
                       f"{block['end'] - block['start'] + 1} lines "
                       f"(<6 belongs on one line)")

        # An icon must never be display:block — see ICON_CLASS_RE / ICON_ELEMENT_RE above.
        for block in _all_rule_blocks(text):
            selector = block["selector"].strip().lower()
            is_glyph = ICON_CLASS_RE.search(selector)
            if not is_glyph and not ICON_ELEMENT_RE.search(selector):
                continue
            compact = re.sub(r"\s+", "", block["body"]).lower()
            sized, painted = SIZED_BODY_RE.search(compact), SHAPE_BODY_RE.search(compact)
            # BOTH signals means a drawn shape whatever the selector looks like — a real glyph is
            # text and never sets its own box size and background together. This arm also covers
            # selectors the class regex over-claims as glyphs, such as `.far-left`.
            if sized and painted:
                continue
            # For a bare `<i>`, either signal alone is enough: the house style puts a bar's colour
            # on a parent rule or an inline custom prop, so `.chart .bar i{height:100%}` has size
            # and no background and is still a shape.
            if not is_glyph and (sized or painted):
                continue
            if DISPLAY_BLOCK_RE.search(compact):
                report.add(rel, block["start"], "CSS_ICON_BLOCK",
                           f"'{block['selector'].strip()[:40]}' sets display:block on an icon "
                           "(use inline-block in a text-align:center parent)")

        # Media queries belong at the very bottom of the sheet.
        top = parse_blocks(text)
        first_media = next(
            (i for i, b in enumerate(top)
             if b["selector"].lstrip().lower().startswith("@media")), None)
        if first_media is not None:
            after = [b for b in top[first_media + 1:]
                     if not b["selector"].lstrip().startswith("@")]
            if after:
                report.add(rel, after[0]["start"], "CSS_MEDIA_ORDER",
                           f"rule '{after[0]['selector'][:40]}' appears after a "
                           f"@media block (media queries go at the bottom)")


def lint_views(report: Report, root: str) -> None:
    html_like = iter_files([".php", ".html", ".htm"], root)

    # Only demand data-link if the project actually drives an SPA with it.
    uses_data_link = False
    # This is project context, not a finding target. Under --changed/--staged
    # the router may be unchanged while a changed fragment still needs the rule.
    for rel in iter_files([".js", ".ts"], root, respect_scope=False):
        try:
            if "data-link" in read_text(os.path.join(root, rel)):
                uses_data_link = True
                break
        except ReadError:
            continue

    for rel in html_like:
        path = os.path.join(root, rel)
        try:
            raw = read_text(path)
        except ReadError as exc:
            report.unread(rel, str(exc))
            continue
        report.scanned += 1
        fragment = is_fragment_path(rel)
        lowered = raw.lower()

        if fragment:
            for tag in BOILERPLATE_TAGS:
                if re.search(rf"</?{tag}(?:\s|>)", lowered):
                    report.add(rel, None, "VIEW_BOILERPLATE",
                               f"fragment contains page tag '<{tag}>'")
            for tag in ASSET_TAGS:
                if tag in lowered:
                    report.add(rel, None, "VIEW_ASSET_TAG",
                               f"fragment contains inline '{tag}' "
                               "(styles belong in a sheet, scripts in a module)")

        for num, line in enumerate(raw.splitlines(), 1):
            if INLINE_HANDLER_RE.search(line):
                report.add(rel, num, "INLINE_HANDLER",
                           "inline event handler; use event delegation instead")

            if uses_data_link and fragment:
                for tag in ANCHOR_RE.findall(line):
                    if "data-link" in tag.lower():
                        continue
                    match = HREF_RE.search(tag)
                    if not match:
                        continue
                    href = match.group(1).strip()
                    if href and not href.startswith(EXTERNAL_HREF):
                        report.add(rel, num, "VIEW_SPA_LINK",
                                   f"internal link '{href}' missing data-link")


def lint_debug(report: Report, root: str) -> None:
    patterns = {
        ".js": [(re.compile(r"\bconsole\.(log|debug|trace)\s*\("), "console.{0}()"),
                (re.compile(r"^\s*debugger\s*;?\s*$"), "debugger statement")],
        ".php": [(re.compile(r"\bvar_dump\s*\("), "var_dump()"),
                 (re.compile(r"\bprint_r\s*\("), "print_r()"),
                 (re.compile(r"\bdd\s*\("), "dd()")],
    }
    patterns[".ts"] = patterns[".js"]

    for rel in iter_files([".js", ".ts", ".php"], root):
        ext = os.path.splitext(rel)[1]
        rules = patterns.get(ext, [])
        path = os.path.join(root, rel)
        try:
            raw = read_text(path)
        except ReadError as exc:
            report.unread(rel, str(exc))
            continue
        report.scanned += 1
        for num, line in enumerate(raw.splitlines(), 1):
            stripped = line.strip()
            if is_comment_line(stripped, ext):
                continue
            for regex, label in rules:
                match = regex.search(line)
                if match:
                    name = label.format(*match.groups()) if match.groups() else label
                    report.add(rel, num, "DEBUG_LEFTOVER", f"leftover {name}")


def run(args) -> Report:
    report = Report("lint_rules")
    root = args.path
    lint_views(report, root)
    lint_css(report, root)
    lint_debug(report, root)
    return report


if __name__ == "__main__":
    cli(run, "Lint web projects against the house style.")
