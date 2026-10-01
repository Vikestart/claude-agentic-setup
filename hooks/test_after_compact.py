"""Checks the post-compaction hook (after_compact.py): it names exactly the working docs present,
a general reminder without them, silence for other starts and bad input, and the session's last
message before the compaction restored verbatim.
Run after any change to the hook: python test_after_compact.py"""
import atexit, json, shutil, subprocess, sys, tempfile, pathlib
hook = pathlib.Path(__file__).with_name("after_compact.py")
DOCS = ("implementation_plan.md", "task.md", "handover.md", "roadmap.md")
root = pathlib.Path(tempfile.mkdtemp(prefix="aftercompact-"))
atexit.register(shutil.rmtree, root, ignore_errors=True)


def call(raw, env=None):
    r = subprocess.run([sys.executable, str(hook)], input=raw, capture_output=True, text=True, env=env)
    assert r.returncode == 0 and not r.stderr, (r.returncode, r.stderr)
    return json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"] if r.stdout.strip() else ""


def event(cwd, source="compact", transcript=None):
    data = {"hook_event_name": "SessionStart", "source": source, "cwd": str(cwd)}
    if transcript is not None:
        data["transcript_path"] = str(transcript)
    return json.dumps(data)


def say(mid, *blocks, sidechain=False, stop="end_turn"):
    content = [{"type": "text", "text": b} if isinstance(b, str) else b for b in blocks]
    return {"type": "assistant", "isSidechain": sidechain,
            "message": {"id": mid, "content": content, "stop_reason": stop}}


def transcript(name, records, filler=0):
    path = root / name
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        for rec in records:
            fh.write(json.dumps(rec) + "\n")
        for _ in range(filler):  # user lines after the reply push it out of the tail window
            fh.write(json.dumps({"type": "user", "message": {"content": "x" * 1000}}) + "\n")
    return path


results = []
def check(name, cond):
    results.append(cond)
    if not cond:
        print("FAIL", name)

proj = root / "proj"
(proj / ".docs").mkdir(parents=True)
for name in ("implementation_plan.md", "roadmap.md"):
    (proj / ".docs" / name).write_text("x", encoding="utf-8")
(proj / ".docs" / "task.md").mkdir()  # a folder with a doc's name is not a doc
present = [f".docs/{n}" for n in DOCS if (proj / ".docs" / n).is_file()]
msg = call(event(proj))
named = [f".docs/{n}" for n in DOCS if f".docs/{n}" in msg]
check("after a compaction: names exactly the docs present", named == present and "compacted" in msg)

for source in ("startup", "resume", "clear"):
    check(f"{source}: silent", call(event(proj, source)) == "")
general = call(event(root / "elsewhere"))
check("no .docs folder: general reminder, no file named", "compacted" in general and ".docs/implementation_plan.md" not in general)
empty = root / "empty"
(empty / ".docs").mkdir(parents=True)
check("empty .docs folder: general reminder", call(event(empty)) == general)
check("malformed input: silent, exit 0", call("{not json") == "")
check("missing cwd: silent, exit 0", call(json.dumps({"source": "compact"})) == "")

tool = {"type": "tool_use", "id": "t", "name": "Bash", "input": {}}
convo = transcript("convo.jsonl", [
    {"type": "user", "message": {"content": "go"}},
    say("m1", "OLD REPLY"),
    say("m2", tool),
    say("m4", "FINAL ONE"), say("m4", tool), say("m4", "  "), say("m4", "FINAL TWO"),
    say("m5", "AGENT TEXT", sidechain=True),
    {"type": "user", "message": {"content": "next request"}},
    say("m6", "MID NARRATION", stop="tool_use"), say("m6", tool, stop="tool_use"),
    {"type": "system", "subtype": "compact_boundary"},
    {"type": "user", "isCompactSummary": True, "message": {"content": "summary"}},
])
got = call(event(proj, transcript=convo))
check("last reply: every text block of the last message, in order",
      "FINAL ONE\n\nFINAL TWO" in got and present[0] in got)
check("last reply: an earlier message and a subagent's text are left out",
      "OLD REPLY" not in got and "AGENT TEXT" not in got)
check("last reply: narration in an unfinished turn is not the reply", "MID NARRATION" not in got)
check("startup with a transcript: still silent", call(event(proj, "startup", convo)) == "")

far = transcript("far.jsonl", [say("m1", "EARLY REPLY")], filler=2200)
check("last reply beyond the tail window: found by the full read",
      "EARLY REPLY" in call(event(proj, transcript=far)))

long = transcript("long.jsonl", [say("m1", "y" * 7000)])
cut = call(event(proj, transcript=long))
check("a reply over the cap is cut and says so", "y" * 6000 in cut and "y" * 6001 not in cut and "cut at" in cut)

docs_only = call(event(proj))
check("no transcript path: the docs notice alone", call(event(proj, transcript=root / "missing.jsonl")) == docs_only
      and "verbatim" not in docs_only)
check("a transcript with no reply: the docs notice alone",
      call(event(proj, transcript=transcript("none.jsonl", [say("m1", tool)]))) == docs_only)
fat = root / "fat"
(fat / ".docs").mkdir(parents=True)
(fat / ".docs" / "task.md").write_text("x" * 40_000, encoding="utf-8")
(fat / ".docs" / "roadmap.md").write_text("x" * 100, encoding="utf-8")
fat_msg = call(event(fat))
check("an oversized working file is named with its trim rule, a lean one is not",
      ".docs/task.md: 39 kB of 15" in fat_msg and ".docs/roadmap.md:" not in fat_msg)
check("all files within budget: no budget note", "size budget" not in call(event(proj)))
import os, re
config = root / "config"
memory = config / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(fat.resolve())) / "memory"
memory.mkdir(parents=True)
(memory / "MEMORY.md").write_bytes(b"- x\n" * 2500)
mem_msg = call(event(fat), env={**os.environ, "CLAUDE_CONFIG_DIR": str(config)})
check("an oversized memory index is named, a lean one is not",
      "MEMORY.md: 10 kB of 6" in mem_msg and "MEMORY.md" not in fat_msg)
check("only mid-turn text: the docs notice alone", call(event(proj, transcript=transcript(
      "mid.jsonl", [say("m1", "NARRATION", stop="tool_use")]))) == docs_only)

print(f"{sum(results)}/{len(results)} ok")
sys.exit(0 if all(results) else 1)
