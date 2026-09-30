"""Find local asset references that point at files which do not exist.

Scope is deliberately narrow: only references that carry a file extension
(.css, .js, .webp, .woff2 ...) are checked. Extensionless hrefs are SPA routes,
not files on disk, and flagging them produced noise that trained everyone to
ignore this tool.

Root-absolute paths (`/assets/app.css`) are ambiguous under XAMPP: the web root
may be htdocs while the project sits in a subdirectory. Each candidate is
therefore resolved against the project root *and* against the parent, and a hit
either way counts as fine - a false "broken" is worse than a missed one here.

Run from a project root. See _common.py for shared behaviour and .auditignore.
"""

from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _common import Report, ReadError, cli, iter_files, read_text  # noqa: E402

ATTR_REF = re.compile(r"(?:src|href|poster|data-src)\s*=\s*[\"']([^\"']+)[\"']",
                      re.IGNORECASE)
CSS_URL = re.compile(r"url\(\s*[\"']?([^\"')]+)[\"']?\s*\)", re.IGNORECASE)
SRCSET = re.compile(r"srcset\s*=\s*[\"']([^\"']+)[\"']", re.IGNORECASE)

SKIP_PREFIX = ("http://", "https://", "//", "#", "mailto:", "tel:", "data:",
               "javascript:", "blob:", "<?", "{{", "{%", "?")
DYNAMIC = re.compile(r"\$\{|<\?|\{\{|%s|\$\w")


def _candidates(link: str, rel_file: str, root: str) -> list[str]:
    clean = link.split("?")[0].split("#")[0]
    if not clean:
        return []
    if clean.startswith("/"):
        stripped = clean.lstrip("/")
        return [
            os.path.join(root, stripped),
            # Project served from a subdirectory of the web root.
            os.path.join(root, os.pardir, stripped),
        ]
    return [os.path.join(root, os.path.dirname(rel_file), clean)]


def run(args) -> Report:
    report = Report("link_checker")
    root = args.path

    for rel in iter_files([".html", ".htm", ".php", ".js", ".ts", ".css"], root):
        try:
            text = read_text(os.path.join(root, rel))
        except ReadError as exc:
            report.unread(rel, str(exc))
            continue
        report.scanned += 1
        is_css = rel.endswith(".css")

        for num, line in enumerate(text.splitlines(), 1):
            links: list[str] = []
            if is_css:
                links += CSS_URL.findall(line)
            else:
                links += ATTR_REF.findall(line)
                for value in SRCSET.findall(line):
                    links += [part.strip().split(" ")[0]
                              for part in value.split(",") if part.strip()]

            for link in links:
                link = link.strip()
                if not link or link.startswith(SKIP_PREFIX) or DYNAMIC.search(link):
                    continue
                clean = link.split("?")[0].split("#")[0]
                # No extension => an SPA route, not a file. Not our business.
                if not os.path.splitext(clean)[1]:
                    continue
                paths = _candidates(link, rel, root)
                if not paths:
                    continue
                if any(os.path.exists(os.path.normpath(p)) for p in paths):
                    continue
                report.add(rel, num, "BROKEN_ASSET", f"'{link}' does not exist")

    return report


if __name__ == "__main__":
    cli(run, "Check local asset references resolve to real files.")
