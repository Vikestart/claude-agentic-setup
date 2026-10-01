#!/usr/bin/env python3
"""A temporary, per-project context limit for the NEXT session, set and cleared by the handover.

WHY THIS EXISTS. The shared settings cap every main session at `autoCompactWindow` 330000, which
compacts at ~300k (~33k below the window). A phase known to need more gets a project-level override instead, written into
`<project>/.claude/settings.local.json`; a NEW session there obeys it (probed 2026-09-30: 600000
compacted at 95%, ~570k). Settings load at session start, so an override set at the end of
session N applies to N+1, and N+1's handover clears it again unless the next phase qualifies.

The override is only temporary if this script set it: a private ledger in `~/.claude` records
what it wrote. An `autoCompactWindow` the ledger does not know is a person's deliberate setting and
is never changed or removed.

USAGE (from the project root, or with --project)
    context_override.py status
    context_override.py set 600000 --reason "phase 12 rewrites the importer in one pass"
    context_override.py clear

Exit codes: 0 done, 1 refused (a deliberate setting is in the way, or a value out of range).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

KEY = "autoCompactWindow"
SHARED_SETTINGS = Path(__file__).resolve().parents[3] / "settings" / "shared-settings.json"
# Above Opus's window there is nothing to reach.
MAX_VALUE = 1_000_000


def shared_cap() -> int:
    """At or below the cap the setup applies there is nothing to raise."""
    return int(json.loads(SHARED_SETTINGS.read_text(encoding="utf-8"))["set"][KEY])


def read_json(path: Path) -> tuple[dict, str]:
    """The file's object and its line break, so a rewrite keeps a CRLF file CRLF."""
    if not path.is_file():
        return {}, "\n"
    raw = path.read_bytes().decode("utf-8-sig")
    return (json.loads(raw) if raw.strip() else {}), ("\r\n" if "\r\n" in raw else "\n")


def write_json(path: Path, data: dict, nl: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(data, indent=2, ensure_ascii=False) + "\n").replace("\n", nl).encode("utf-8"))


def project_key(project: Path) -> str:
    # One project, one entry, whichever spelling (case, junction) the caller used.
    return str(project.resolve()).lower()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("action", choices=("status", "set", "clear"))
    ap.add_argument("value", nargs="?", type=int)
    ap.add_argument("--reason", default="")
    ap.add_argument("--project", type=Path, default=Path.cwd())
    ap.add_argument("--ledger", type=Path, default=Path.home() / ".claude" / "context-overrides.json")
    a = ap.parse_args(argv)

    settings_path = a.project / ".claude" / "settings.local.json"
    settings, nl = read_json(settings_path)
    ledger, ledger_nl = read_json(a.ledger)
    pkey = project_key(a.project)
    entry = ledger.get(pkey)
    current = settings.get(KEY)
    ours = entry is not None and current == entry["value"]

    if a.action == "status":
        if current is None:
            print("none: the shared cap applies")
        elif ours:
            print(f"temporary: {current} (set {entry['set']}: {entry['reason']})")
        else:
            print(f"deliberate: {current} (not set by this script; left alone)")
        return 0

    if a.action == "set":
        if a.value is None or not a.reason.strip():
            ap.error("set needs a value and --reason")
        floor = shared_cap()
        if not floor < a.value <= MAX_VALUE:
            print(f"refused: {a.value} must be above the shared cap {floor:,} and at most {MAX_VALUE:,}")
            return 1
        if current is not None and not ours:
            print(f"refused: a deliberate {KEY} of {current} is set; not overriding it")
            return 1
        created = entry["created_file"] if ours else not settings_path.is_file()
        settings[KEY] = a.value
        write_json(settings_path, settings, nl)
        ledger[pkey] = {"value": a.value, "reason": a.reason.strip(), "set": date.today().isoformat(),
                        "created_file": created}
        write_json(a.ledger, ledger, ledger_nl)
        print(f"set: {a.value} for the next session in {a.project} (compacts ~30k below it)")
        return 0

    # clear
    if entry is None:
        print("nothing to clear" + ("" if current is None else f"; the deliberate {current} stays"))
        return 0
    if ours:
        del settings[KEY]
        if not settings and entry["created_file"]:
            settings_path.unlink()
        else:
            write_json(settings_path, settings, nl)
        print(f"cleared: {entry['value']}; the next session gets the shared cap")
    else:
        # Someone changed or removed the value since: whatever is there now is theirs.
        print("ledger entry dropped; the setting was changed by hand since, so it stays")
    del ledger[pkey]
    if ledger:
        write_json(a.ledger, ledger, ledger_nl)
    else:
        a.ledger.unlink()
    return 0


if __name__ == "__main__":
    sys.exit(main())
