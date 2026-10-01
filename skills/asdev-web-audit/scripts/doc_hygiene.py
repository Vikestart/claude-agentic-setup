"""Keep working/tracking docs lean and correctly located.

Advisory by design - these are judgement calls about your own notes, never
defects in shipped code. It exists because a bloated plan is re-read on almost
every turn: a 28KB implementation_plan.md read 15 times in one session is
~450KB of context spent on stale content that already shipped.

Checks:
  * working docs sitting in the project root instead of .docs/
  * .docs/ that is neither ignored nor intentionally tracked
  * working files over their size BUDGET (plan, task, walkthrough, roadmap, changelog, the
    project's AGENTS.md / CLAUDE.md) - trimmed at every phase completion and handover; the
    after-compact hook names them too (`over_budget`, below)
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

# Size budgets, the one source for this check and the after-compact hook. Measured 2026-10-01:
# Tilspire's roadmap 101 kB and plan 47 kB, Nebulingo's changelog 112 kB and task 70 kB, xampp-pulse's
# walkthrough 57 kB — each re-read again and again by the main chat and every agent, though the
# lifecycle rules already said to prune them; nothing checked.
BUDGET_KB = {
    ".docs/implementation_plan.md": 30,  # one phase; cleared at completion
    ".docs/task.md": 15,                  # that phase's tasks only
    ".docs/walkthrough.md": 15,           # the last phase only
    ".docs/roadmap.md": 25,               # outcomes, never tasks or implementation detail
    ".docs/changelog.md": 25,             # one line per phase; older blocks rotate out
    "AGENTS.md": 20,                      # re-read on every turn (asdev-conventions)
    "CLAUDE.md": 20,
}
BUDGET_LINES = {".docs/changelog.md": 100, "AGENTS.md": 100, "CLAUDE.md": 100}
TRIM_HOW = {
    ".docs/implementation_plan.md": "keep only the active phase; durable facts go to .docs/reference/",
    ".docs/task.md": "keep only the current phase's tasks; open follow-ups become roadmap outcomes",
    ".docs/walkthrough.md": "replace it with the last completed phase only",
    ".docs/roadmap.md": "delete shipped items, merge duplicates, move detail into the plan when promoted",
    ".docs/changelog.md": "rotate the oldest block into a dated .docs/reference/ archive",
    "AGENTS.md": "move occasional detail to .docs/reference/ and leave a one-line pointer",
    "CLAUDE.md": "move occasional detail to .docs/reference/ and leave a one-line pointer",
}


def over_budget(root: str) -> list:
    """(relative path, what is over, how to trim) for each working file past its budget."""
    found = []
    for rel in sorted(set(BUDGET_KB) | set(BUDGET_LINES)):
        full = os.path.join(root, *rel.split("/"))
        if not os.path.isfile(full):
            continue
        kb = os.path.getsize(full) / 1024.0
        over = []
        if rel in BUDGET_KB and kb > BUDGET_KB[rel]:
            over.append(f"{kb:.0f} kB of {BUDGET_KB[rel]}")
        if rel in BUDGET_LINES:
            with open(full, encoding="utf-8", errors="replace") as fh:
                n = sum(1 for _ in fh)
            if n > BUDGET_LINES[rel]:
                over.append(f"{n} lines of {BUDGET_LINES[rel]}")
        if over:
            found.append((rel, ", ".join(over), TRIM_HOW[rel]))
    return found
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

    for rel, over, how in over_budget(root):
        if not scope_active() or in_scope(rel):
            report.add(rel, None, "OVER_BUDGET", f"{over} - {how}")

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
