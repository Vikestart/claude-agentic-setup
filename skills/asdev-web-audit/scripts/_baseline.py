"""Reviewed-exception support for the aggregate asdev-web-audit gate.

Entries match one exact scanner finding by scanner, rule, file, and source-line
context. Line numbers are informational and may drift. Invalid entries never
suppress findings; stale entries are advisory and are only assessed inside the
active Git scope.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

from _common import Report, ReadError, in_scope, read_text, scope_active

BASELINE_NAME = ".audit-baseline.json"
RULE_ALIASES = {
    "DANGEROUS_FUNCTIONS": "DANGEROUS_FUNC",
}


def _normal(value: str) -> str:
    return " ".join(value.split())


def _path(value: str) -> str:
    value = value.replace("\\", "/")
    while value.startswith("./"):
        value = value[2:]
    return value.lstrip("/")


def _rule(value: str) -> str:
    return RULE_ALIASES.get(value, value)


@dataclass
class Entry:
    scanner: str
    rule: str
    file: str
    context: str
    reason: str
    index: int
    invalid: str | None = None
    matched: bool = False

    @property
    def key(self) -> tuple[str, str, str, str]:
        return self.scanner, _rule(self.rule), _path(self.file), _normal(self.context)


def load(root: str) -> tuple[list[Entry], str | None]:
    path = os.path.join(root, BASELINE_NAME)
    if not os.path.isfile(path):
        return [], None
    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        return [], str(exc)
    rows = payload.get("entries") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        return [], "top-level 'entries' must be a list"

    entries: list[Entry] = []
    for index, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            entries.append(Entry("", "", "", "", "", index,
                                 "entry must be an object"))
            continue
        values = {name: row.get(name) for name in
                  ("scanner", "rule", "file", "context", "reason")}
        missing = next((name for name in ("scanner", "rule", "file", "context")
                        if not isinstance(values[name], str)
                        or not values[name].strip()), None)
        invalid = f"missing or empty '{missing}'" if missing else None
        if not invalid and "*" in str(values["file"]):
            invalid = "file contains a wildcard; name one exact file"
        reason = values["reason"]
        if not invalid and (not isinstance(reason, str) or not reason.strip()):
            invalid = "no written reason for acceptance"
        if (not invalid and isinstance(reason, str)
                and reason.strip().upper().startswith("TODO")):
            invalid = "reason is still a TODO placeholder"
        entries.append(Entry(
            str(values["scanner"] or ""), str(values["rule"] or ""),
            str(values["file"] or ""), str(values["context"] or ""),
            str(reason or ""), index, invalid,
        ))
    return entries, None


def _finding_context(root: str, item: dict) -> str:
    line = item.get("line")
    rel = str(item.get("file") or "")
    if isinstance(line, int) and line > 0 and rel and rel != "-":
        try:
            lines = read_text(os.path.join(root, rel)).splitlines()
            if line <= len(lines):
                return _normal(lines[line - 1])
        except ReadError:
            pass
    return _normal(str(item.get("message") or ""))


def apply(reports: list[tuple[Report, bool]], root: str) -> tuple[int, list[Report]]:
    """Suppress reviewed findings and return accepted count plus diagnostics."""
    entries, load_error = load(root)
    blocking = Report("audit_baseline")
    advisory = Report("audit_baseline", advisory=True)
    if load_error:
        blocking.add(BASELINE_NAME, None, "BASELINE_INVALID", load_error)
        return 0, [(blocking, True)]

    valid: dict[tuple[str, str, str, str], list[Entry]] = {}
    for entry in entries:
        if entry.invalid:
            blocking.add(BASELINE_NAME, None, "BASELINE_INVALID",
                         f"entry {entry.index}: {entry.invalid}")
            continue
        valid.setdefault(entry.key, []).append(entry)

    accepted = 0
    for report, _ in reports:
        remaining = []
        for item in report.items:
            key = (
                report.tool,
                _rule(str(item.get("rule") or "")),
                _path(str(item.get("file") or "")),
                _finding_context(root, item),
            )
            matches = valid.get(key)
            if not matches:
                remaining.append(item)
                continue
            for entry in matches:
                entry.matched = True
            accepted += 1
            report.accepted += 1
        report.items = remaining

    for entry in entries:
        if entry.invalid or entry.matched:
            continue
        if scope_active() and not in_scope(_path(entry.file)):
            continue
        advisory.add(BASELINE_NAME, None, "BASELINE_STALE",
                     f"entry {entry.index}: [{entry.rule}] {_path(entry.file)}")

    diagnostics: list[tuple[Report, bool]] = []
    if blocking.items:
        diagnostics.append((blocking, True))
    if advisory.items:
        diagnostics.append((advisory, False))
    return accepted, diagnostics
