"""Run every read-only auditor in one pass and print one compact report.

Why this exists: running separate scripts meant repeated process starts, tree
walks, and banner blocks. This runs them in one process, shares the file index
and text cache between tools, and prints one
summary, which matters when the reader is an agent paying for every line in its
context window.

Blocking vs advisory
--------------------
Blocking tools (security, house style, a11y, broken assets) report defects and
set the exit code. Advisory tools (file size, unused CSS) report judgement calls
that need a human eye; their details are summarised as counts unless you pass
--advisory, and they never fail the run on their own.

    python scripts/audit_all.py --changed            # usual completion gate
    python scripts/audit_all.py --changed --advisory # include soft findings
    python scripts/audit_all.py --changed -q         # counts only
"""

from __future__ import annotations

import importlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _common import apply_scope, base_parser, scope_label  # noqa: E402
from _baseline import apply as apply_baseline  # noqa: E402

# (module name, blocking?)
TOOLS = [
    ("syntax_check", True),
    ("security_audit", True),
    ("lint_rules", True),
    ("convention_audit", True),
    ("a11y_audit", True),
    ("link_checker", True),
    ("token_analyzer", False),
    ("unused_css_detector", False),
    ("doc_hygiene", False),
]


class _ToolArgs:
    """Per-tool args: the sub-reports are rendered by this script, not by them."""

    def __init__(self, path: str, cap: int):
        self.path = path
        self.json = False
        self.quiet = False
        self.max = cap


def main() -> None:
    parser = base_parser("Run all web auditors and print one compact report.")
    parser.add_argument("--advisory", action="store_true",
                        help="show advisory findings in full, not just counts")
    parser.set_defaults(max=5)
    args = parser.parse_args()
    args.path = os.path.abspath(args.path)
    apply_scope(args, args.path)

    tool_args = _ToolArgs(args.path, args.max)
    reports: list[tuple[object, bool]] = []
    tool_errors: list[dict[str, str]] = []
    for name, blocking in TOOLS:
        try:
            module = importlib.import_module(name)
            report = module.run(tool_args)
        except Exception as exc:  # a broken auditor must not hide the others
            tool_errors.append({"tool": name, "error": str(exc)})
            continue
        reports.append((report, blocking))

    accepted, baseline_reports = apply_baseline(reports, args.path)
    reports.extend(baseline_reports)

    blocking_total = sum(len(r.items) + len(r.unreadable)
                         for r, blocking in reports if blocking)
    advisory_total = sum(len(r.items) for r, b in reports if not b)
    scanned = max((r.scanned for r, _ in reports), default=0)
    fatal_total = blocking_total + len(tool_errors)

    if args.json:
        import json
        print(json.dumps({
            "blocking": blocking_total,
            "advisory": advisory_total,
            "accepted": accepted,
            "errors": tool_errors,
            "tools": [{"tool": r.tool, "blocking": b, "findings": r.items,
                       "unreadable": r.unreadable, "accepted": r.accepted}
                      for r, b in reports],
        }))
        sys.exit(1 if fatal_total else 0)

    print(f"=== audit: {blocking_total} blocking, {advisory_total} advisory "
          f"({accepted} reviewed; {scope_label()}, ~{scanned} files scanned) ===")
    if not args.quiet:
        for report, blocking in reports:
            issue_count = len(report.items) + len(report.unreadable)
            mark = "!" if (blocking and issue_count) else " "
            tag = "" if blocking else "  (advisory)"
            accepted_tag = f"  ({report.accepted} reviewed)" if report.accepted else ""
            print(f" {mark} {report.tool:<20} {issue_count:>4}{tag}{accepted_tag}")

    for error in tool_errors:
        print(f" ! {error['tool']:<20} ERROR  {error['error']}")

    if not args.quiet:
        for report, blocking in reports:
            if not report.items and not report.unreadable:
                continue
            if not blocking and not args.advisory:
                continue
            print()
            report.emit(_ToolArgs(args.path, args.max))

    if advisory_total and not args.advisory and not args.quiet:
        print("\nAdvisory findings hidden; re-run with --advisory to see them.")
    if tool_errors:
        print("\nThe aggregate is incomplete because an auditor failed; this is blocking.")
    if blocking_total and not args.quiet:
        print("\nBlocking findings must be fixed at the root cause, not suppressed.")
    if fatal_total and args.quiet:
        print("Re-run without -q for scanner and finding details.")

    sys.exit(1 if fatal_total else 0)


if __name__ == "__main__":
    main()
