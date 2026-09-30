"""Keep working/tracking docs lean and correctly located.

Advisory by design - these are judgement calls about your own notes, never
defects in shipped code. It exists because a bloated plan is re-read on almost
every turn: a 28KB implementation_plan.md read 15 times in one session is
~450KB of context spent on stale content that already shipped.

Checks:
  * working docs sitting in the project root instead of .docs/
  * .docs/ that is neither ignored nor intentionally tracked
  * oversized trackers (plan/task) - prune shipped sections per the lifecycle rule
  * shipped/done sections still present in the plan (delete-on-ship drift)
  * changelog entries that have grown from "1-2 concise lines" into paragraphs

.docs/reference/ is deliberately exempt from the size and shipped-marker
checks: reference docs are durable project knowledge, updated but never
pruned. Applying delete-on-ship to them would destroy knowledge.

Run from a project root. Supports --changed / --since like the other tools.
"""

from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _common import (  # noqa: E402
    Report, ReadError, cli, git_ignored, git_tracked, in_scope, read_text,
    scope_active, scope_contains_prefix,
)

# Trackers: pruned on ship, so they should stay small.
TRACKERS = {"implementation_plan.md", "task.md", "walkthrough.md"}
# Any working doc that belongs in .docs/ rather than the project root.
WORKING = TRACKERS | {"changelog.md", "roadmap.md"}
WORKING_RE = re.compile(r"^(?:project_audit|.*_design|.*_audit)[\w-]*\.md$", re.I)

TRACKER_MAX_KB = 15.0
CHANGELOG_LINE_MAX = 400          # chars; a "1-2 line summary" is well under this
SHIPPED = re.compile(
    r"^\s{0,3}#{1,6}.*(?:\bshipped\b|\bcomplete[d]?\b|\bdone\b|✅)|^\s*status:\s*(?:shipped|done|complete)",
    re.I | re.M,
)


def _is_working_doc(name: str) -> bool:
    return name in WORKING or bool(WORKING_RE.match(name))


def run(args) -> Report:
    report = Report("doc_hygiene", advisory=True)
    root = args.path
    docs = os.path.join(root, ".docs")

    # 1. Working docs stranded in the project root.
    try:
        entries = sorted(os.listdir(root))
    except OSError:
        return report
    for name in entries:
        if not name.lower().endswith(".md"):
            continue
        # Agent-instruction files live in the project root by convention;
        # README ships with the code.
        if name in ("GEMINI.md", "AGENTS.md", "README.md"):
            continue
        if (os.path.isfile(os.path.join(root, name)) and _is_working_doc(name)
                and (not scope_active() or in_scope(name))):
            report.add(name, None, "DOC_NOT_IN_DOCS",
                       "working doc in the project root - move it to .docs/ "
                       "(one gitignore rule covers the whole folder)")

    if not os.path.isdir(docs):
        return report

    # 2. .docs/ is ignored by default, but the global policy permits deliberate
    # tracking in a private repository with server-side Markdown/.docs denial.
    # Flag only the ambiguous state: neither ignored nor already tracked.
    docs_relevant = (not scope_active() or scope_contains_prefix(".docs")
                     or in_scope(".gitignore"))
    if docs_relevant:
        ignored = git_ignored(root, ".docs")
        tracked = git_tracked(root, ".docs")
        if ignored is False and tracked is False:
            report.add(
                ".docs", None, "DOCS_POLICY_UNSET",
                ".docs/ is neither ignored nor tracked; add it to .gitignore, "
                "or intentionally track it only after confirming a private "
                "remote and production Markdown/.docs denial",
            )

    # 3/4/5. Per-file checks. reference/ is exempt by design.
    for dirpath, dirnames, filenames in os.walk(docs):
        rel_dir = os.path.relpath(dirpath, root).replace(os.sep, "/")
        if "reference" in rel_dir.split("/"):
            continue
        dirnames[:] = [d for d in dirnames if d != "reference"]
        for name in sorted(filenames):
            if not name.lower().endswith(".md"):
                continue
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            if scope_active() and not in_scope(rel):
                continue
            report.scanned += 1
            try:
                text = read_text(full)
            except ReadError as exc:
                report.unread(rel, str(exc))
                continue

            if name in TRACKERS:
                kb = os.path.getsize(full) / 1024.0
                if kb > TRACKER_MAX_KB:
                    report.add(rel, None, "TRACKER_BLOATED",
                               f"{kb:.0f}KB - prune shipped sections; this file "
                               "is re-read constantly")
                hits = SHIPPED.findall(text)
                if hits:
                    report.add(rel, None, "SHIPPED_STILL_IN_PLAN",
                               f"{len(hits)} section(s) look shipped/done - "
                               "delete them and leave 1-2 lines in changelog.md")

            if name == "changelog.md":
                long_lines = [i for i, ln in enumerate(text.splitlines(), 1)
                              if len(ln) > CHANGELOG_LINE_MAX]
                if long_lines:
                    report.add(rel, long_lines[0], "CHANGELOG_VERBOSE",
                               f"{len(long_lines)} entr(y/ies) over "
                               f"{CHANGELOG_LINE_MAX} chars - the rule is a "
                               "concise 1-2 line summary per shipped phase")
    return report


if __name__ == "__main__":
    cli(run, "Check working/tracking docs are lean and correctly located.")
