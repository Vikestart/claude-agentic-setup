"""Checks the context hook (context_guard.py) against synthetic transcripts: silent for the main
chat, and for a subagent when it must stay silent, when it must add its notice, and that it finds
the subagent's own transcript.
Run after any change to the hook: python test_context_guard.py"""
import json, os, subprocess, sys, tempfile, pathlib
hook = pathlib.Path(__file__).with_name("context_guard.py")
root = pathlib.Path(tempfile.mkdtemp(prefix="ctxguard-"))
env = {**os.environ, "CONTEXT_GUARD_LIMIT": "250000", "CONTEXT_GUARD_STEP": "50000",
       "CONTEXT_GUARD_STATE": str(root / "state")}


def record(tokens, rid):
    return json.dumps({"requestId": rid, "message": {"role": "assistant", "usage": {
        "input_tokens": 10, "cache_read_input_tokens": tokens - 110, "cache_creation_input_tokens": 100}}})


def write(path, sizes, junk_first=False, partial_last=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ['{"cut mid-record "usage": {'] if junk_first else []
    lines += [record(s, f"r{i}") for i, s in enumerate(sizes)]
    lines.append(json.dumps({"type": "user", "message": {"role": "user", "content": "tool result"}}))
    if partial_last:
        lines.append('{"requestId": "r9", "message": {"usage": {"input_tok')
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def call(main, agent=None):
    event = {"hook_event_name": "PostToolUse", "transcript_path": str(main), "tool_name": "Bash"}
    if agent:
        event["agent_id"] = agent
    r = subprocess.run([sys.executable, str(hook)], input=json.dumps(event), capture_output=True,
                       text=True, env=env)
    assert r.returncode == 0 and not r.stderr, (r.returncode, r.stderr)
    return json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"] if r.stdout.strip() else ""


results = []
def check(name, cond):
    results.append(cond)
    if not cond:
        print("FAIL", name)

main = root / "proj" / "sess1.jsonl"
write(main, [120000, 260000, 405000])
check("main chat past 250k and 400k: silent (compaction handles it)", call(main) == "")

agent = main.with_suffix("") / "subagents" / "agent-abc123.jsonl"
write(agent, [100000, 180000])
check("subagent below the ceiling: silent", call(main, "abc123") == "")
write(agent, [100000, 260000], junk_first=True)
amsg = call(main, "abc123")
check("subagent past the ceiling: reads its own transcript, hand back", "260k" in amsg and "hand back" in amsg)
write(agent, [260000, 290000])
check("subagent under STEP more growth: silent", call(main, "abc123") == "")
write(agent, [260000, 311000])
check("subagent STEP more growth: notice again", "311k" in call(main, "abc123"))

agent2 = main.with_suffix("") / "subagents" / "agent-def456.jsonl"
write(agent2, [300000], partial_last=True)
check("half-written newest line: skipped, last complete record read", "300k" in call(main, "def456"))

check("missing transcript: silent, exit 0", call(root / "nope" / "x.jsonl", "zzz") == "")

bad = subprocess.run([sys.executable, str(hook)], input=json.dumps(
    {"transcript_path": str(root / "proj" / "sess3.jsonl"), "agent_id": "q"}), capture_output=True, text=True,
    env={**env, "CONTEXT_GUARD_LIMIT": "250k"})
check("a mistyped setting falls back to the default and should stay silent",
      bad.returncode == 0 and not bad.stderr)

print(f"{sum(results)}/{len(results)} ok")
sys.exit(0 if all(results) else 1)
