#!/usr/bin/env python3
"""SessionStart hook (matcher `compact`): after a compaction, point the session back at its docs.

Sessions no longer hand over to a fresh chat (owner, 2026-09-30): automatic compaction at the 400k
window handles their size. A compaction summary is lossy and chosen by the model, so this hook adds
one notice naming the working documents that exist in the session's `.docs/`, the same files a fresh
session would read after a handover; without a `.docs/` in the session folder, a general reminder.
Silent for any other start.

It must never break a session start: any failure exits 0 silently.
"""
import json
import sys
from pathlib import Path

DOCS = ("implementation_plan.md", "task.md", "handover.md", "roadmap.md")


def notice(event):
    if event.get("source") != "compact":
        return None
    docs = Path(event["cwd"]) / ".docs"
    present = [f".docs/{name}" for name in DOCS if (docs / name).is_file()]
    if not present:
        # Sessions started at the htdocs root work in a project one level down, whose docs this
        # hook cannot know — remind in general terms rather than say nothing.
        return ("Context was just compacted. Before continuing, re-read the .docs/ working files "
                "(implementation_plan.md, task.md) of the project you are working in, if it has "
                "them — where they and the summary disagree, the files win.")
    return ("Context was just compacted. Before continuing, re-read " + ", ".join(present)
            + " — the files are the record; where they and the summary disagree, the files win.")


def main():
    try:
        text = notice(json.load(sys.stdin))
        if text:
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart",
                                                     "additionalContext": text}}))
    except Exception:  # a broken hook must never block the session it starts
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
