#!/usr/bin/env python3
"""PostToolUse hook: tell a subagent when its context passes the ceiling.

Cost grows with context size × turns (measured 2026-09-30 in Nebulingo, Framvis and Tilspire: the
largest single costs were threads at 500k–960k context, re-read on every turn). An agent past ~250k
should hand back, but a model cannot see its own context size — this hook can. It reads the newest
`usage` record of the agent's transcript and, past the ceiling, adds one short notice. It notices
again only after another STEP of growth, so it never nags.

Hooks receive the MAIN session's `transcript_path`; inside a subagent they also receive `agent_id`,
and that agent's transcript is `<session>/subagents/agent-<agent_id>.jsonl` beside it.

The main chat gets no notice (owner, 2026-09-30): it never asks about a fresh chat or `/compact`.
Automatic compaction (`autoCompactWindow` 400k) handles its size, and `after_compact.py` points it
back at the working docs afterwards (`reference/setup-architecture.md`).

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
    """True when a notice is due: past the ceiling, and first time or another STEP since the last."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    state = STATE_DIR / (hashlib.sha1(key.encode("utf-8")).hexdigest()[:16] + ".txt")
    try:
        last = int(state.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        last = 0
    if tokens < LIMIT or (last and tokens < last + STEP):
        return False
    state.write_text(str(tokens), encoding="utf-8")
    return True


def message(tokens):
    return (f"Context guard: your context is ~{tokens // 1000}k tokens, past the ~{LIMIT // 1000}k "
            "ceiling. Every further turn re-reads all of it. Finish the current step, then hand back: "
            "what is done, what is left, and the exact next step.")


def main():
    try:
        event = json.load(sys.stdin)
        agent = event.get("agent_id")
        if not agent:
            return 0
        path = Path(event["transcript_path"]).with_suffix("") / "subagents" / f"agent-{agent}.jsonl"
        tokens = context_size(path)
        if tokens is not None and should_notify(str(path), tokens):
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse",
                                                     "additionalContext": message(tokens)}}))
    except Exception:  # a broken guard must never block the tool call it follows
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
