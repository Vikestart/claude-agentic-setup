"""Checks the post-compaction hook (after_compact.py): it names exactly the working docs present,
a general reminder without them, and silence for other starts and bad input.
Run after any change to the hook: python test_after_compact.py"""
import atexit, json, shutil, subprocess, sys, tempfile, pathlib
hook = pathlib.Path(__file__).with_name("after_compact.py")
DOCS = ("implementation_plan.md", "task.md", "handover.md", "roadmap.md")
root = pathlib.Path(tempfile.mkdtemp(prefix="aftercompact-"))
atexit.register(shutil.rmtree, root, ignore_errors=True)


def call(raw):
    r = subprocess.run([sys.executable, str(hook)], input=raw, capture_output=True, text=True)
    assert r.returncode == 0 and not r.stderr, (r.returncode, r.stderr)
    return json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"] if r.stdout.strip() else ""


def event(cwd, source="compact"):
    return json.dumps({"hook_event_name": "SessionStart", "source": source, "cwd": str(cwd)})


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

print(f"{sum(results)}/{len(results)} ok")
sys.exit(0 if all(results) else 1)
