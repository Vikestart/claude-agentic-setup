#!/usr/bin/env python3
"""PostToolUse hook: tell a session or subagent when its context passes the ceiling.

Cost grows with context size × turns (measured 2026-09-30 in Nebulingo, Framvis and Tilspire: the
largest single costs were threads at 500k–960k context, re-read on every turn). The rule is to hand
back or hand over past ~250k, but a model cannot see its own context size — this hook can. It reads
the newest `usage` record of the transcript it belongs to and, past the ceiling, adds one short
notice to the conversation. It notices again only after another STEP of growth, so it never nags.

Hooks receive the MAIN session's `transcript_path`; inside a subagent they also receive `agent_id`,
and that agent's transcript is `<session>/subagents/agent-<agent_id>.jsonl` beside it.

Environment: CONTEXT_GUARD_LIMIT (default 250000), CONTEXT_GUARD_STEP (default 50000).
It must never break a tool call: any failure exits 0 silently.
"""
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

def env_int(name, default):
    try:
        return int(os.environ.get(name, default))
    except ValueError:  # a typo in the setting must not turn the hook into an error on every call
        return default


LIMIT = env_int("CONTEXT_GUARD_LIMIT", 250000)
STEP = env_int("CONTEXT_GUARD_STEP", 50000)
TAIL_BYTES = 512 * 1024
STATE_DIR = Path(os.environ.get("CONTEXT_GUARD_STATE", Path(tempfile.gettempdir()) / "context_guard"))


def transcript_for(event):
    main = Path(event["transcript_path"])
    agent = event.get("agent_id")
    if agent:
        return main.with_suffix("") / "subagents" / f"agent-{agent}.jsonl", True
    return main, False


def context_size(path):
    """Tokens in the context at the newest assistant response: fresh input plus cache read and write."""
    with path.open("rb") as fh:
        fh.seek(0, os.SEEK_END)
        size = fh.tell()
        fh.seek(max(0, size - TAIL_BYTES))
        tail = fh.read().decode("utf-8", errors="replace")
    for line in reversed(tail.splitlines()):
        if '"usage"' not in line:
            continue
        try:
            usage = json.loads(line)["message"]["usage"]
        except (ValueError, KeyError, TypeError):
            continue  # the first line of the tail is usually cut mid-record
        return (usage.get("input_tokens", 0) + usage.get("cache_read_input_tokens", 0)
                + usage.get("cache_creation_input_tokens", 0))
    return None


def should_notify(key, tokens):
    """None for silence, else True for the first notice and False for a repeat."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    state = STATE_DIR / (hashlib.sha1(key.encode("utf-8")).hexdigest()[:16] + ".txt")
    try:
        last = int(state.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        last = 0
    # A compaction continues in the same transcript at a much smaller size. Without this reset the
    # remembered peak (959k in one real Framvis chat) would silence the hook for the rest of it.
    if last and tokens < last - STEP:
        state.unlink(missing_ok=True)
        last = 0
    if tokens < LIMIT or (last and tokens < last + STEP):
        return None
    state.write_text(str(tokens), encoding="utf-8")
    return not last


def message(tokens, is_agent, first):
    k = f"~{tokens // 1000}k"
    if is_agent:
        return (f"Context guard: your context is {k} tokens, past the ~{LIMIT // 1000}k ceiling. "
                "Every further turn re-reads all of it. Finish the current step, then hand back: "
                "what is done, what is left, and the exact next step.")
    if first:
        return (f"Context guard: this session's context is {k} tokens, past the ~{LIMIT // 1000}k "
                "ceiling. Finish the current step, then ask the owner once whether to hand over to a "
                "fresh chat (CLAUDE.md §1, Handover).")
    # The rule is to ask ONCE: a repeat is information, never a second question.
    return (f"Context guard: context now {k} tokens. If the owner already declined a handover, do "
            "not ask again; keep reads small and finish the current phase. Auto-compaction will "
            "summarise this session at the shared cap; if this work would not survive a summary, "
            "raise the window yourself with `python ~/.claude/hooks/context_window.py raise` and say "
            "so in one line — it is restored when the session ends.")


def main():
    try:
        event = json.load(sys.stdin)
        path, is_agent = transcript_for(event)
        tokens = context_size(path)
        if tokens is None:
            return 0
        first = should_notify(str(path), tokens)
        if first is None:
            return 0
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse",
                                                 "additionalContext": message(tokens, is_agent, first)}}))
    except Exception:  # a broken guard must never block the tool call it follows
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
