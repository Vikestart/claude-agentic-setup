"""Checks context_window.py: a raise lands in the project's settings.local.json and is put back
exactly, a sibling session's end does not cut another's raise short, a hand-edited value is left
alone, and a crashed session's raise is cleaned up only once its transcript has gone quiet.
Run after any change to the script: python test_context_window.py"""
import json, os, pathlib, subprocess, sys, tempfile, time
script = pathlib.Path(__file__).with_name("context_window.py")
root = pathlib.Path(tempfile.mkdtemp(prefix="ctxwin-"))
projects = root / "projects"
state = root / "state.json"
results = []


def run(args, session, project, stdin=None):
    env = {**os.environ, "CONTEXT_WINDOW_STATE": str(state), "CLAUDE_PROJECTS_ROOT": str(projects),
           "CLAUDE_CODE_SESSION_ID": session, "CLAUDE_PROJECT_DIR": str(project)}
    r = subprocess.run([sys.executable, str(script), *args], input=stdin, capture_output=True,
                       text=True, env=env, timeout=20)
    return r.returncode, r.stdout.strip()


def hook(event, session, project):
    return run(["--hook"], session, project, json.dumps({"hook_event_name": event, "session_id": session}))


def settings(project):
    p = project / ".claude" / "settings.local.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def check(name, ok, detail=""):
    results.append(ok)
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f" -- {detail}"))


def project(name, initial=None):
    p = root / name
    (p / ".claude").mkdir(parents=True)
    if initial is not None:
        (p / ".claude" / "settings.local.json").write_text(json.dumps(initial), encoding="utf-8")
    return p


# 1. No file before: raise creates it, the session's end removes it again.
a = project("a")
code, out = run(["raise"], "s1", a)
check("raise writes 1M", code == 0 and settings(a) == {"autoCompactWindow": 1_000_000}, out)
hook("SessionEnd", "s1", a)
check("session end removes a file it created", settings(a) is None, str(settings(a)))

# 2. Other keys and a previous value survive the round trip.
b = project("b", {"permissions": {"allow": ["x"]}, "autoCompactWindow": 300_000})
run(["raise", "600000"], "s2", b)
hook("SessionEnd", "s2", b)
check("previous value and other keys put back",
      settings(b) == {"permissions": {"allow": ["x"]}, "autoCompactWindow": 300_000}, str(settings(b)))

# 3. Two sessions in one project: the first to end must not cut the other's raise short, and the
#    last must restore what was there before the FIRST raise, not the sibling's 1M.
c = project("c", {"autoCompactWindow": 400_000})
run(["raise"], "s3", c)
run(["raise"], "s4", c)
hook("SessionEnd", "s3", c)
check("sibling end keeps the raise", (settings(c) or {}).get("autoCompactWindow") == 1_000_000, str(settings(c)))
hook("SessionEnd", "s4", c)
check("last end restores the pre-raise value", settings(c) == {"autoCompactWindow": 400_000}, str(settings(c)))

# 4. A value changed by hand after the raise is left alone.
d = project("d")
run(["raise"], "s5", d)
(d / ".claude" / "settings.local.json").write_text(json.dumps({"autoCompactWindow": 700_000}), encoding="utf-8")
hook("SessionEnd", "s5", d)
check("hand-edited value left alone", settings(d) == {"autoCompactWindow": 700_000}, str(settings(d)))

# 5. A crashed session: restored at the next session start only once its transcript is quiet.
e = project("e")
run(["raise"], "s6", e)
transcript = projects / "proj" / "s6.jsonl"
transcript.parent.mkdir(parents=True)
transcript.write_text("{}\n", encoding="utf-8")
hook("SessionStart", "s7", e)
check("a live session's raise survives another's start",
      (settings(e) or {}).get("autoCompactWindow") == 1_000_000, str(settings(e)))
old = time.time() - 7 * 3600
os.utime(transcript, (old, old))
hook("SessionStart", "s7", e)
check("a quiet session's raise is cleaned up", settings(e) is None, str(settings(e)))

# 6. Refusals and a hook that never fails.
code, out = run(["raise", "50000"], "s8", a)
check("out-of-range size refused", code == 1 and "refused" in out, out)
code, _ = run(["--hook"], "s9", a, stdin="not json")
check("hook swallows bad input", code == 0)

print(f"{sum(results)}/{len(results)} ok")
sys.exit(0 if all(results) else 1)
