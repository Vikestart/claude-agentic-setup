@@@ skills/asdev-web-audit/scripts/brain.py
name: migrate overwrites a note the brain already has
expect: FAIL migrate never overwrites
<<<<<<< OLD
        if dest.exists():
            if dest.is_file() and digest(dest) == digest(path):
======= NEW
        if False:
            if dest.is_file() and digest(dest) == digest(path):
>>>>>>> END

name: the old folder is renamed without verifying the copies
expect: FAIL a copy that does not match keeps the old folder
<<<<<<< OLD
    if broken or missing:
======= NEW
    if False:
>>>>>>> END

name: a re-run renames onto an existing folder
expect: FAIL a re-run in the same second renames the old folder uniquely
<<<<<<< OLD
    while candidate.exists():
======= NEW
    while False:
>>>>>>> END

name: the clash's index line still points at the brain's own note
expect: FAIL the index gains the old lines
<<<<<<< OLD
            line = line.replace(f"]({old})", f"]({new})")
======= NEW
            pass
>>>>>>> END

name: migrate runs before setup
expect: FAIL migrate refuses before setup
<<<<<<< OLD
    if not (current and same_path(current, where.brain)):
        out.step(False, "setting", "run
======= NEW
    if False:
        out.step(False, "setting", "run
>>>>>>> END

name: setup drops the settings file's other keys
expect: FAIL setup points memory at the repo's brain and keeps every other key
<<<<<<< OLD
    data, nl = read_json(where.settings)
======= NEW
    data, nl = {}, "\n"
>>>>>>> END

name: a worktree gets its own brain
expect: FAIL a worktree session points at the main repo's brain
<<<<<<< OLD
        self.main = self.common.parent if self.common.name == ".git" else self.checkout
======= NEW
        self.main = self.checkout
>>>>>>> END

name: setup trusts that the settings file is ignored
expect: FAIL setup git-ignores the settings file
<<<<<<< OLD
    if ignored(cwd, probe):
        return True, f"{probe} is ignored"
======= NEW
    if True:
        return True, f"{probe} is ignored"
>>>>>>> END

name: a worktree on an older branch gets no ignore rule
expect: FAIL a worktree whose branch lacks the ignore rule
<<<<<<< OLD
    append_line(where.common / "info" / "exclude", pattern)
======= NEW
    pass
>>>>>>> END

name: the index is not set to merge=union
expect: FAIL two clones that both add index lines merge cleanly
<<<<<<< OLD
UNION = ".docs/brain/MEMORY.md merge=union"
======= NEW
UNION = ".docs/brain/MEMORY.md -diff"
>>>>>>> END

name: an index line to a missing note passes
expect: FAIL an index line pointing at no note fails
<<<<<<< OLD
                (listed if rel in notes else dead).append(rel)
======= NEW
                listed.append(rel)
>>>>>>> END

name: an unreachable note passes
expect: FAIL a note the index cannot reach fails
<<<<<<< OLD
    lost = sorted(set(notes) - reached)
======= NEW
    lost = []
>>>>>>> END

name: an oversized index passes
expect: FAIL an index over 40 lines fails
<<<<<<< OLD
    size_ok = len(lines) <= INDEX_MAX_LINES and not long_lines
======= NEW
    size_ok = True
>>>>>>> END

name: a type user note passes
expect: FAIL a type: user note fails
<<<<<<< OLD
        if found and USER_TYPE.search(found.group(1)):
======= NEW
        if False:
>>>>>>> END

name: a credential passes
expect: FAIL a credential in a note fails
<<<<<<< OLD
    out.step(not secrets, "secrets"
======= NEW
    out.step(True, "secrets"
>>>>>>> END

name: a recreated hidden memory folder passes
expect: FAIL a hidden memory folder holding notes after setup fails
<<<<<<< OLD
        held = holding(old_folders(where))
======= NEW
        held = []
>>>>>>> END

@@@ skills/asdev-web-audit/scripts/doc_hygiene.py
name: doc_hygiene drops the brain's findings
expect: FAIL doc_hygiene shows a brain breach
<<<<<<< OLD
            if not s["ok"]:
                report.add(".docs/brain"
======= NEW
            if False:
                report.add(".docs/brain"
>>>>>>> END

@@@ skills/asdev-web-audit/scripts/brain.py
name: start runs setup at every start
expect: FAIL a second start does nothing and returns no index
<<<<<<< OLD
    if current and same_path(current, where.brain) and not sources:
        out.step(True, "start"
======= NEW
    if False:
        out.step(True, "start"
>>>>>>> END

name: start returns the index when nothing changed
expect: FAIL an old folder holding only copies the brain has
<<<<<<< OLD
    if out.facts.get("newly_set") or out.facts.get("moved"):
======= NEW
    if True:
>>>>>>> END

name: start never migrates
expect: FAIL start sets up, moves the old notes in
<<<<<<< OLD
    if out.passed and sources:
        migrate(where, out, stamp)
======= NEW
    if False:
        migrate(where, out, stamp)
>>>>>>> END

name: start skips a project whose old folder holds notes again
expect: FAIL a note the harness left in the old folder after setup is moved in
<<<<<<< OLD
    if current and same_path(current, where.brain) and not sources:
======= NEW
    if current and same_path(current, where.brain):
>>>>>>> END
