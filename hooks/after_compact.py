#!/usr/bin/env python3
"""SessionStart hook (matcher `compact`): after a compaction, point the session back at its docs.

Sessions no longer hand over to a fresh chat (owner, 2026-09-30): automatic compaction at the 400k
window handles their size. A compaction summary is lossy and chosen by the model, so this hook adds
one notice naming the working documents that exist in the session's `.docs/`, the same files a fresh
session would read after a handover; without a `.docs/` in the session folder, a general reminder.
Silent for any other start.

It also restores, verbatim, the session's last message written before the compaction (owner,
2026-10-01): the summary paraphrases or drops it, and it is usually the state the owner is reacting
to. Nothing the session writes lands after the compaction marker before this hook runs, so it is in
the transcript. Only a message that ENDED a turn counts (`stop_reason` "end_turn"): automatic
compaction mostly lands mid-turn (64 of 76 real ones), where the last text is narration before tool
calls that already ran ("Let me first remove…"), which would read as an open question to the owner.

It must never break a session start: any failure exits 0 silently.
"""
import json
import sys
from pathlib import Path

DOCS = ("implementation_plan.md", "task.md", "handover.md", "roadmap.md")
# The budgets live in the audit suite's doc_hygiene.py (one source). Oversized working files were
# re-read for weeks although the lifecycle rules said to prune them (2026-10-01), so every
# compaction now names them.
AUDIT = Path.home() / ".claude" / "skills" / "asdev-web-audit" / "scripts"


def budget_note(cwd):
    try:
        sys.path.insert(0, str(AUDIT))
        from doc_hygiene import over_budget
        found = over_budget(str(cwd))
    except Exception:  # suite missing or broken: the docs notice still stands
        return ""
    if not found:
        return ""
    lines = "\n".join(f"- {rel}: {over} — {how}" for rel, over, how in found)
    return ("\n\nOver their size budget, read again and again by you and every agent — trim them at "
            "the next phase boundary (the phase-completion routine's trim step), not now mid-task:\n"
            + lines)
# Final messages measured 2026-10-01: median ~700 characters, longest 3,260.
REPLY_CAP = 6000
# Transcripts reach tens of MB; the last reply is almost always in the final stretch.
TAIL_BYTES = 2_000_000


def last_reply(transcript):
    """Text of the last main-chat message that ended a turn, or None. Its blocks share one id."""
    path = Path(transcript)
    size = path.stat().st_size
    for start in (max(0, size - TAIL_BYTES), 0):
        with path.open("rb") as fh:
            fh.seek(start)
            lines = fh.read().decode("utf-8", "replace").splitlines()
        if start:
            lines = lines[1:]  # the first line of a tail may be cut in half
        reply_id, texts = None, []
        for line in lines:
            if '"assistant"' not in line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if rec.get("type") != "assistant" or rec.get("isSidechain"):
                continue
            msg = rec.get("message") or {}
            if msg.get("stop_reason") != "end_turn":
                continue
            parts = [c.get("text", "") for c in msg.get("content") or []
                     if isinstance(c, dict) and c.get("type") == "text" and c.get("text", "").strip()]
            if not parts:
                continue
            if msg.get("id") != reply_id:
                reply_id, texts = msg.get("id"), []
            texts += parts
        if texts:
            return "\n\n".join(texts)
        if not start:
            return None
    return None


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
            + " — the files are the record; where they and the summary disagree, the files win."
            + budget_note(event["cwd"]))


def with_reply(text, event):
    try:
        reply = last_reply(event["transcript_path"])
    except Exception:  # no transcript, unreadable or odd: the docs notice still stands
        return text
    if not reply:
        return text
    if len(reply) > REPLY_CAP:
        reply = reply[:REPLY_CAP] + f"\n[… cut at {REPLY_CAP} characters]"
    return (text + "\n\nYour last message to the owner before the compaction, verbatim — the owner "
            "may be replying to it:\n<<<\n" + reply + "\n>>>")


def main():
    try:
        event = json.load(sys.stdin)
        text = notice(event)
        if text:
            text = with_reply(text, event)
        if text:
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart",
                                                     "additionalContext": text}}))
    except Exception:  # a broken hook must never block the session it starts
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
