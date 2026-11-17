#!/usr/bin/env python3
"""Tests for brain.py (setup, migrate, check) and doc_hygiene's use of it, on throwaway git repos.

Every git call here uses its own git config and every run its own Claude config folder, so nothing
touches a real repo, the person's git settings or their memory folders.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
BRAIN = HERE / "brain.py"
root = Path(tempfile.mkdtemp(prefix="brain-test-")).resolve()
results = []

gitconfig = root / "gitconfig"
# An empty excludes file too: Claude Code adds settings.local.json to the person's global git
# ignore, which would make every "is it ignored" check here pass without setup doing anything.
(root / "excludes").write_text("", encoding="utf-8")
gitconfig.write_text("[user]\n\tname = t\n\temail = t@example.invalid\n[init]\n\tdefaultBranch = main\n"
                     "[core]\n\tautocrlf = false\n\texcludesFile = " + (root / "excludes").as_posix() + "\n",
                     encoding="utf-8")
for name in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
    os.environ.pop(name, None)
os.environ.update(GIT_CONFIG_GLOBAL=str(gitconfig), GIT_CONFIG_NOSYSTEM="1",
                  CLAUDE_CONFIG_DIR=str(root / "config"))
sys.path.insert(0, str(HERE))
import brain as brain_module  # noqa: E402


def check(name, cond):
    results.append(bool(cond))
    print(("ok   " if cond else "FAIL ") + name)


def git(cwd, *args):
    done = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True)
    if done.returncode:
        raise RuntimeError(f"git {' '.join(args)}: {done.stderr}")
    return done.stdout


def ignored(cwd, rel):
    return subprocess.run(["git", "-C", str(cwd), "check-ignore", "-q", rel]).returncode == 0


def brain(command, project, *extra):
    done = subprocess.run([sys.executable, str(BRAIN), command, "--project", str(project), "--json", *extra],
                          capture_output=True, text=True, encoding="utf-8")
    try:
        data = json.loads(done.stdout)
    except ValueError:
        data = {"raw": done.stdout + done.stderr}
    return done.returncode, data


def step(data, name):
    return next((s for s in data.get("steps", []) if s["step"] == name), {})


def failed(data):
    return {s["step"] for s in data.get("steps", []) if not s["ok"]}


def repo(name):
    path = root / name
    (path / ".docs").mkdir(parents=True)
    git(path, "init", "-q")
    (path / ".docs" / "roadmap.md").write_text("# Roadmap\n", encoding="utf-8")
    git(path, "add", "-A")
    git(path, "commit", "-qm", "init")
    return path


def old_memory(path):
    folder = root / "config" / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(path)) / "memory"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


NOTE = "---\nname: {name}\ndescription: d\nmetadata:\n  type: {kind}\n---\n\n{body}\n"


def note(folder, name, body="a fact", kind="project"):
    (folder / f"{name}.md").write_text(NOTE.format(name=name, body=body, kind=kind), encoding="utf-8")


def setting_of(folder):
    return Path(json.loads((folder / ".claude" / "settings.local.json").read_text(encoding="utf-8"))
                ["autoMemoryDirectory"])


try:
    # ---- setup
    a = repo("a")
    settings = a / ".claude" / "settings.local.json"
    settings.parent.mkdir()
    settings.write_bytes(b'{\r\n  "autoCompactWindow": 600000,\r\n  "permissions": {"allow": ["Bash(x)"]}\r\n}\r\n')
    code, data = brain("setup", a)
    kept = json.loads(settings.read_text(encoding="utf-8"))
    check("setup points memory at the repo's brain and keeps every other key",
          code == 0 and setting_of(a) == a / ".docs" / "brain"
          and kept.get("autoCompactWindow") == 600000 and kept.get("permissions") == {"allow": ["Bash(x)"]})
    raw = settings.read_bytes()
    check("setup keeps a CRLF settings file CRLF", b"\r\n" in raw and b"\n" not in raw.replace(b"\r\n", b""))
    check("setup git-ignores the settings file and Obsidian's folder",
          ignored(a, ".claude/settings.local.json") and ignored(a, ".docs/.obsidian/workspace.json"))
    check("setup makes the index merge with merge=union",
          git(a, "check-attr", "merge", "--", ".docs/brain/MEMORY.md").strip().endswith(": union"))
    check("setup reports that the setting is new", data.get("newly_set") is True)
    code, data = brain("setup", a)
    check("a second setup changes nothing and passes",
          code == 0 and data.get("newly_set") is False
          and (a / ".gitignore").read_text(encoding="utf-8").count("settings.local.json") == 1)

    b = repo("b")
    elsewhere = b / ".claude" / "settings.local.json"
    elsewhere.parent.mkdir()
    elsewhere.write_text(json.dumps({"autoMemoryDirectory": "D:\\elsewhere"}), encoding="utf-8")
    code, data = brain("setup", b)
    check("setup refuses to replace a setting that points elsewhere",
          code == 1 and "setting" in failed(data) and setting_of(b) == Path("D:\\elsewhere"))

    plain = root / "plain"
    plain.mkdir()
    nodocs = root / "nodocs"
    nodocs.mkdir()
    git(nodocs, "init", "-q")
    codes = [brain(c, p)[0] for c in ("setup", "migrate", "check") for p in (plain, nodocs, root / "missing")]
    check("no git repo, no .docs/ or no folder at all: every command skips with exit 3", codes == [3] * 9)

    # The worktree starts from the first commit, so its own .gitignore lacks the rule setup added.
    wt = root / "a-wt"
    git(a, "worktree", "add", "-q", str(wt), "-b", "wt")
    code, data = brain("setup", wt)
    check("a worktree session points at the main repo's brain, not its own copy",
          code == 0 and setting_of(wt) == a / ".docs" / "brain")
    check("a worktree whose branch lacks the ignore rule still ignores its settings file",
          ignored(wt, ".claude/settings.local.json"))
    sub = a / "app" / "admin"
    sub.mkdir(parents=True)
    code, data = brain("setup", sub)
    check("a subfolder session gets its own setting, pointing at the repo's brain, and ignored",
          code == 0 and setting_of(sub) == a / ".docs" / "brain"
          and ignored(a, "app/admin/.claude/settings.local.json"))

    # ---- migrate
    c = repo("c")
    mem = old_memory(c)
    note(mem, "alpha")
    note(mem, "beta", "old beta")
    (mem / "MEMORY.md").write_text("# Memory Index\n\n- [Alpha](alpha.md) — a\n- [Beta](beta.md) — b\n",
                                   encoding="utf-8")
    code, data = brain("migrate", c)
    check("migrate refuses before setup, and leaves the old folder alone",
          code == 1 and "setting" in failed(data) and (mem / "alpha.md").is_file())
    brain("setup", c)
    cb = c / ".docs" / "brain"
    note(cb, "beta", "reviewed beta")
    (cb / "MEMORY.md").write_text("# Brain\n\n- [Beta](beta.md) — b\n", encoding="utf-8")
    before = {p.name: p.read_bytes() for p in mem.iterdir()}
    code, data = brain("migrate", c, "--stamp", "20261117-100000")
    check("migrate copies new notes in", code == 0 and (cb / "alpha.md").read_bytes() == before["alpha.md"])
    check("migrate never overwrites: a clashing note arrives under a new name, reported",
          "reviewed beta" in (cb / "beta.md").read_text(encoding="utf-8")
          and (cb / "beta-migrated-20261117-100000.md").read_bytes() == before["beta.md"]
          and step(data, "clash").get("warn"))
    index = (cb / "MEMORY.md").read_text(encoding="utf-8")
    check("the index gains the old lines, the clash's pointing at its new name, with no doubles",
          "- [Alpha](alpha.md) — a" in index and "- [Beta](beta-migrated-20261117-100000.md) — b" in index
          and index.count("[Beta](beta.md)") == 1 and "# Memory Index" not in index)
    moved = mem.with_name("memory.migrated-20261117-100000")
    check("the old folder is renamed, not deleted, with every file intact",
          not mem.exists() and {p.name: p.read_bytes() for p in moved.iterdir()} == before)

    # The harness recreated the old folder (a session that predates setup), after a review.
    note(old_memory(c), "alpha", "alpha again, changed")
    note(cb, "alpha", "alpha reviewed")
    code, data = brain("migrate", c, "--stamp", "20261117-100000")
    check("a re-run keeps the reviewed note and brings the recreated one in beside it",
          code == 0 and "alpha reviewed" in (cb / "alpha.md").read_text(encoding="utf-8")
          and "alpha again" in (cb / "alpha-migrated-20261117-100000.md").read_text(encoding="utf-8"))
    check("a re-run in the same second renames the old folder uniquely",
          moved.is_dir() and mem.with_name("memory.migrated-20261117-100000-2").is_dir())

    gone = old_memory(root / "gone")
    note(gone, "lonely")
    code, data = brain("migrate", root / "gone")
    check("migrate refuses a project folder that does not exist, and leaves its notes alone",
          code == 3 and (gone / "lonely.md").is_file())

    # A copy that does not match: the old folder must stay where it is.
    e = repo("e")
    brain("setup", e)
    note(old_memory(e), "gamma")
    real_copy = brain_module.shutil.copy2
    brain_module.shutil.copy2 = lambda src, dest: Path(dest).write_bytes(b"corrupt")
    try:
        out, _, _ = brain_module.run("migrate", e, "20261117-110000")
    finally:
        brain_module.shutil.copy2 = real_copy
    check("a copy that does not match keeps the old folder in place",
          not out.passed and (old_memory(e) / "gamma.md").is_file()
          and not old_memory(e).with_name("memory.migrated-20261117-110000").exists())

    # ---- merge=union, between two clones of one repo
    origin = root / "origin.git"
    git(root, "init", "-q", "--bare", str(origin))
    one = root / "one"
    git(root, "clone", "-q", str(origin), str(one))
    (one / ".docs").mkdir()
    brain("setup", one)
    (one / ".docs" / "brain" / "MEMORY.md").write_text("# Brain\n- [A](a.md) — a\n", encoding="utf-8")
    git(one, "add", "-A")
    git(one, "commit", "-qm", "brain")
    git(one, "push", "-q", "origin", "HEAD:main")
    two = root / "two"
    git(root, "clone", "-q", str(origin), str(two))
    for clone, line in ((one, "- [B](b.md) — b\n"), (two, "- [C](c.md) — c\n")):
        with open(clone / ".docs" / "brain" / "MEMORY.md", "a", encoding="utf-8") as fh:
            fh.write(line)
        git(clone, "commit", "-qam", line.strip())
    git(one, "push", "-q", "origin", "HEAD:main")
    pulled = subprocess.run(["git", "-C", str(two), "pull", "-q", "--no-rebase", "origin", "main"],
                            capture_output=True, text=True)
    merged = (two / ".docs" / "brain" / "MEMORY.md").read_text(encoding="utf-8")
    check("two clones that both add index lines merge cleanly and keep both",
          pulled.returncode == 0 and "[B](b.md)" in merged and "[C](c.md)" in merged and "<<<<<<<" not in merged)

    # ---- check
    d = repo("d")
    code, data = brain("check", d)
    check("check fails where the brain is not set up", code == 1 and "setting" in failed(data))
    brain("setup", d)
    db = d / ".docs" / "brain"
    note(db, "hub", "see [[leaf]] and [[not-yet]]")
    note(db, "leaf")
    (db / "MEMORY.md").write_text("# Brain\n\n- [Hub](hub.md) — the hub\n", encoding="utf-8")
    code, data = brain("check", d)
    check("a clean brain passes; a note reached through a hub's [[link]] counts as reached",
          code == 0 and step(data, "reach").get("ok"))
    check("a link to a note not written yet is listed, not failed",
          step(data, "unwritten").get("warn") and "not-yet" in step(data, "unwritten").get("message", ""))

    def breach(label, change, expect):
        saved = root / "saved"
        shutil.copytree(db, saved)
        change()
        code, data = brain("check", d)
        shutil.rmtree(db)
        shutil.copytree(saved, db)
        shutil.rmtree(saved)
        check(label, code == 1 and expect in failed(data))
        return data

    def add_index(text):
        with open(db / "MEMORY.md", "a", encoding="utf-8") as fh:
            fh.write(text)

    breach("an index line pointing at no note fails", lambda: add_index("- [Gone](gone.md) — x\n"), "index links")
    breach("a note the index cannot reach fails", lambda: note(db, "island"), "reach")
    breach("an index over 40 lines fails", lambda: add_index("- filler\n" * 40), "index size")
    breach("an index line over 150 characters fails", lambda: add_index("- " + "x" * 149 + "\n"), "index size")
    breach("a type: user note fails",
           lambda: (note(db, "person", kind="user"), add_index("- [Person](person.md) — p\n")), "personal")
    value = "q8Zr4TfLx2Wm9VbN"
    data = breach("a credential in a note fails", lambda: note(db, "leaf", f"api_key = '{value}'"), "secrets")
    check("the credential's value never appears in the output", value not in json.dumps(data))
    breach("a hidden memory folder holding notes after setup fails", lambda: note(old_memory(d), "stray"),
           "old folder")
    shutil.rmtree(old_memory(d))

    # ---- start: the asdev mod's start-up hook
    s = repo("s")
    old = old_memory(s)
    note(old, "first")
    (old / "MEMORY.md").write_text("# Memory Index\n\n- [First](first.md) — f\n", encoding="utf-8")
    code, data = brain("start", s, "--stamp", "20260101-000000")
    check("start sets up, moves the old notes in, and returns the index",
          code == 0 and data.get("newly_set") is True and data.get("moved") == 1
          and setting_of(s) == s / ".docs" / "brain" and (s / ".docs" / "brain" / "first.md").is_file()
          and not old.exists() and "[First](first.md)" in data.get("index", ""))
    code, data = brain("start", s)
    check("a second start does nothing and returns no index",
          code == 0 and [x["step"] for x in data.get("steps", [])] == ["start"] and "index" not in data)
    note(old_memory(s), "later")
    code, data = brain("start", s, "--stamp", "20260101-000001")
    check("a note the harness left in the old folder after setup is moved in at the next start",
          code == 0 and data.get("newly_set") is False and data.get("moved") == 1
          and (s / ".docs" / "brain" / "later.md").is_file() and "index" in data)
    note(old_memory(s), "first")
    code, data = brain("start", s, "--stamp", "20260101-000002")
    check("an old folder holding only copies the brain has is renamed, and no index returned",
          code == 0 and data.get("moved") == 0 and "index" not in data and not old_memory(s).joinpath("first.md").exists())
    t = repo("t")
    (t / ".claude").mkdir()
    (t / ".claude" / "settings.local.json").write_text(json.dumps({"autoMemoryDirectory": "D:\\elsewhere"}),
                                                       encoding="utf-8")
    note(old_memory(t), "mine")
    code, data = brain("start", t)
    check("start refuses a setting that points elsewhere and leaves the old folder as it is",
          code == 1 and "setting" in failed(data) and (old_memory(t) / "mine.md").is_file()
          and not (t / ".docs" / "brain" / "mine.md").exists())
    (root / "loose").mkdir()
    code, data = brain("start", root / "loose")
    check("start skips a folder outside a git repo", code == 3 and data.get("skipped"))

    # ---- doc_hygiene runs the check
    note(db, "island")
    hygiene = subprocess.run([sys.executable, str(HERE / "doc_hygiene.py"), "--path", str(d)],
                             capture_output=True, text=True, encoding="utf-8")
    check("doc_hygiene shows a brain breach as an advisory finding", "BRAIN_REACH" in hygiene.stdout)
except Exception as exc:  # a broken guard can trip a later step; that is one more failure, not a crash
    check(f"the suite ran to the end ({type(exc).__name__}: {exc})", False)
finally:
    shutil.rmtree(root, ignore_errors=True)

print(f"{sum(results)}/{len(results)} ok")
sys.exit(0 if all(results) else 1)
