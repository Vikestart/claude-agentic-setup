#!/usr/bin/env python3
"""Let a session widen its own auto-compaction window, and put it back without anyone remembering.

The shared settings compact every session at 400k, a backstop behind the ~250k context hook. A main
session that truly needs more — the owner declined a handover and the work would not survive a
summary — raises it for its own project, and says so in one line:

    python "$HOME/.claude/hooks/context_window.py" raise           # 1M
    python "$HOME/.claude/hooks/context_window.py" raise 600000
    python "$HOME/.claude/hooks/context_window.py" restore

`raise` writes `autoCompactWindow` into the project's `.claude/settings.local.json` (Claude Code
reloads settings files in a running session) and records the session and the value it replaced
in ~/.claude/context-raises.json. As a SessionEnd hook this script restores the value when that
session ends; as a SessionStart hook it also restores raises whose session has written nothing
for STALE_HOURS (one that ended without the hook — a crash, a closed app). Sessions raising the
same project share one restore: the last to end puts back what was there before the first. A value
changed by hand since the raise is left alone.

Environment: CONTEXT_WINDOW_STATE (marker file), CLAUDE_PROJECTS_ROOT (transcripts), both for tests.
"""
import json, os, subprocess, sys, time
from pathlib import Path

KEY = "autoCompactWindow"
LOW, HIGH, DEFAULT = 100_000, 1_000_000, 1_000_000
STALE_HOURS = 6
HOME = Path.home() / ".claude"
STATE = Path(os.environ.get("CONTEXT_WINDOW_STATE") or HOME / "context-raises.json")
PROJECTS = Path(os.environ.get("CLAUDE_PROJECTS_ROOT") or HOME / "projects")


def load(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def project_root():
    if os.environ.get("CLAUDE_PROJECT_DIR"):
        return Path(os.environ["CLAUDE_PROJECT_DIR"]).resolve()
    try:
        top = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, timeout=5)
        if top.returncode == 0 and top.stdout.strip():
            return Path(top.stdout.strip()).resolve()
    except (OSError, subprocess.SubprocessError):
        pass
    return Path.cwd().resolve()


def settings_file(project):
    return Path(project) / ".claude" / "settings.local.json"


def raise_window(session, tokens):
    if not LOW <= tokens <= HIGH:
        return f"refused: {tokens} is outside {LOW}-{HIGH}"
    markers = load(STATE, {})
    project = str(project_root())
    path = settings_file(project)
    settings = load(path, {})
    mine = markers.get(session)
    if mine and mine["project"] != project:
        return f"refused: this session already raised {mine['project']}; restore it first"
    # The value to put back comes from before the FIRST raise of this project, not from a
    # sibling session's raise — otherwise the last session to end would restore 1M forever.
    first = next((m for m in markers.values() if m["project"] == project), None)
    base = first or {"had_key": KEY in settings, "previous": settings.get(KEY), "had_file": path.exists()}
    markers[session] = {"project": project, "value": tokens, "had_key": base["had_key"],
                        "previous": base["previous"], "had_file": base["had_file"]}
    for m in markers.values():
        if m["project"] == project:
            m["value"] = tokens
    settings[KEY] = tokens
    save(path, settings)
    save(STATE, markers)
    return f"raised {KEY} to {tokens:,} for {project}; restored when this session ends"


def restore(session):
    markers = load(STATE, {})
    m = markers.pop(session, None)
    if not m:
        return "nothing to restore for this session"
    others = [s for s, o in markers.items() if o["project"] == m["project"]]
    save(STATE, markers)
    if others:
        return f"kept: {len(others)} other session(s) still use the raise"
    path = settings_file(m["project"])
    settings = load(path, {})
    if settings.get(KEY) != m["value"]:
        return f"left alone: {KEY} was changed since the raise"
    if m["had_key"]:
        settings[KEY] = m["previous"]
    else:
        settings.pop(KEY, None)
    if not settings and not m["had_file"]:
        path.unlink(missing_ok=True)
    else:
        save(path, settings)
    return f"restored {KEY} for {m['project']}"


def stale(session):
    hits = list(PROJECTS.glob(f"*/{session}.jsonl"))
    newest = max((p.stat().st_mtime for p in hits), default=0)
    return time.time() - newest > STALE_HOURS * 3600


def hook():
    # A hook must never break a session start or end: any failure is swallowed.
    try:
        event = json.load(sys.stdin)
        session = event.get("session_id") or ""
        if event.get("hook_event_name") == "SessionEnd":
            restore(session)
        elif event.get("hook_event_name") == "SessionStart":
            for other in list(load(STATE, {})):
                if other != session and stale(other):
                    restore(other)
    except Exception:
        pass
    return 0


def main(argv):
    if argv[:1] == ["--hook"]:
        return hook()
    session = os.environ.get("CLAUDE_CODE_SESSION_ID")
    if not session or not argv or argv[0] not in ("raise", "restore"):
        print("usage: context_window.py raise [TOKENS] | restore   (run inside a Claude Code session)")
        return 2
    if argv[0] == "raise":
        try:
            tokens = int(argv[1]) if len(argv) > 1 else DEFAULT
        except ValueError:
            print(f"refused: {argv[1]!r} is not a token count")
            return 2
        out = raise_window(session, tokens)
    else:
        out = restore(session)
    print(out)
    return 1 if out.startswith("refused") else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
