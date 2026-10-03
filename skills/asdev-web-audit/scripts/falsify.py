"""Prove each new guard actually guards something.

WHY THIS EXISTS. The house rule is that every new assertion must be reverted one
at a time and shown to go RED *for the right reason*, that the suite must first be
proven GREEN on a clean tree (otherwise "went red" may only mean "could not run"),
and that the tree must be restored byte-exactly. That is a precise mechanical
ritual, and without tooling it gets hand-written as throwaway code every time --
which is how vacuous assertions ship: a check that stays GREEN when its guard is
removed was never testing anything.

USAGE

    falsify.py --suite "node scripts/test_phase118_nav_search.mjs" \\
               --mutations mutations.txt

The mutations file uses patch.py's block format, written with the Write tool and
escaped nowhere. `name:` and `expect:` lines above a block describe it:

    @@@ assets/js/app-shell.js
    name: duplicate option-id prefix
    expect: duplicate DOM ids
    <<<<<<< OLD
    optionIdPrefix: 'shell-search',
    ======= NEW
    optionIdPrefix: 'dict',
    >>>>>>> END

A file ending in .json is instead a list of objects with the same fields:

    [{"name":   "duplicate option-id prefix",
      "file":   "assets/js/app-shell.js",
      "old":    "optionIdPrefix: 'shell-search',",
      "new":    "optionIdPrefix: 'dict',",
      "expect": "duplicate DOM ids"}]

`new` may be "" (an empty NEW block) to delete the anchor outright. `expect` is a substring that must
appear in the failing output -- it is what separates "red for the right reason"
from "red because I broke the file".

WHAT IT REFUSES TO DO

  * Run at all if the suite is not GREEN on the clean tree first.
  * Apply a mutation whose anchor is not UNIQUE in the file. A non-unique anchor
    once deleted ~1,565 lines from a source file while leaving it syntactically
    valid, so every check downstream stayed green. Uniqueness is asserted, never
    assumed.
  * Continue after a restore fails its SHA-256 check. A harness that leaves the
    tree mutated is worse than no harness.

LINE ENDINGS. Files are read and written as BYTES, so a CRLF working tree survives
untouched. An anchor written with "\\n" is retried as "\\r\\n" automatically, and the
report says which form matched.
"""

from __future__ import annotations

import re
import argparse
import hashlib
import json
import os
import subprocess
import sys

import patch


JOURNAL = ".falsify-inflight.json"


def sha(path: str) -> str:
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def recover(cwd: str) -> None:
    """Restore a tree left mutated by a HARD kill, before doing anything else.

    ⚠️ try/finally covers Ctrl+C and exceptions, but NOTHING in-process survives
    TerminateProcess / `kill -9` -- verified: a killed run left the guard deleted with
    no warning. So each mutation is journalled with a full byte copy first, and a run
    that finds a stale journal puts the file back and says so. That converts the one
    unfixable case from silent corruption into a loud, self-healing one.
    """
    path = os.path.join(cwd, JOURNAL)
    if not os.path.isfile(path):
        return
    try:
        with open(path, encoding="utf-8") as handle:
            record = json.load(handle)
        target, backup = record["file"], record["backup"]
        with open(backup, "rb") as handle:
            original = handle.read()
        digest = hashlib.sha256(original).hexdigest()
        with open(target, "wb") as handle:
            handle.write(original)
        print(f"RECOVERED     a previous run was killed mid-mutation; restored\n"
              f"              {target}\n"
              f"              to sha256 {digest[:16]} from its journal copy.\n")
        os.remove(backup)
    except (OSError, KeyError, ValueError) as exc:
        print(f"⚠️  A stale {JOURNAL} exists but could not be applied: {exc}\n"
              f"    Check the tree by hand before trusting any result below.\n")
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def run(cmd: str, cwd: str) -> tuple[int, str]:
    proc = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True,
                          text=True, encoding="utf-8", errors="replace")
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def load_mutations(path: str) -> list[dict]:
    """A .json list, or else patch.py's block spec with `name:` / `expect:` lines above each block.

    WHY THE SPEC. Anchors are code, and code in JSON needs every quote, backslash and newline
    escaped. So the JSON was built by an inline Python script before nearly every run (138 runs in
    September 2026), where the same escapes break again in the shell. The spec is taken literally.
    """
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    if path.lower().endswith(".json"):
        return json.loads(text)
    try:
        files = patch.parse(text)
    except patch.SpecError as error:
        raise SystemExit(f"falsify: {path}: {error}") from None
    lines = text.lstrip(patch.BOM).replace("\r\n", "\n").split("\n")
    mutations = []
    for file, blocks in files:
        for old, new, count, start in blocks:
            if count != 1:
                raise SystemExit(f"falsify: {path}: line {start}: a mutation's anchor must be unique; "
                                 f"drop 'x{count}'")
            # The block's own notes run back to the previous block's END or the file line;
            # the nearest `name:` / `expect:` wins.
            meta: dict[str, str] = {}
            k = start - 2
            while k >= 0 and lines[k] != patch.END and not lines[k].startswith(patch.FILE):
                key, sep, value = lines[k].partition(":")
                if sep and key.strip() in ("name", "expect"):
                    meta.setdefault(key.strip(), value.strip())
                k -= 1
            mutations.append({"file": file, "old": old, "new": new, **meta})
    return mutations


def locate(data: bytes, needle: str) -> tuple[bytes, int]:
    """Return (anchor-as-bytes, occurrences), retrying an LF anchor as CRLF."""
    raw = needle.encode("utf-8")
    if data.count(raw):
        return raw, data.count(raw)
    crlf = needle.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8")
    return crlf, data.count(crlf)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Revert each guard one at a time and prove it goes red for the right reason.")
    parser.add_argument("--suite", help="command that must be GREEN on a clean tree")
    parser.add_argument("--mutations", required=True,
                        help="patch.py-style block spec with name:/expect: lines, or a .json list")
    parser.add_argument("--cwd", default=".", help="working directory for the suite (default: cwd)")
    parser.add_argument("--only", help="comma-separated mutation names to run; the rest are skipped")
    parser.add_argument("--check", action="store_true",
                        help="only confirm every file exists and every anchor occurs once; no suite run")
    args = parser.parse_args()
    if not args.check and not args.suite:
        parser.error("--suite is required unless --check is given")

    cwd = os.path.abspath(args.cwd)
    mutations = load_mutations(args.mutations)
    if not isinstance(mutations, list) or not mutations:
        raise SystemExit("falsify: --mutations must hold at least one mutation.")
    for index, m in enumerate(mutations, 1):
        m.setdefault("name", f"mutation {index}")
    if args.only:
        wanted = [n.strip() for n in args.only.split(",") if n.strip()]
        unknown = [n for n in wanted if n not in {m["name"] for m in mutations}]
        if unknown:
            raise SystemExit("falsify: --only names no mutation called: " + ", ".join(unknown))
        mutations = [m for m in mutations if m["name"] in wanted]

    files = sorted({os.path.join(cwd, m["file"]) for m in mutations})
    missing = [f for f in files if not os.path.isfile(f)]
    if missing:
        raise SystemExit("falsify: these files do not exist:\n  " + "\n  ".join(missing))
    if args.check:
        # The anchors were otherwise found wrong only after the clean-tree suite run, one turn and
        # one suite later; agents hand-wrote this pre-flight about 25 times since 2026-10-01.
        bad = 0
        for m in mutations:
            with open(os.path.join(cwd, m["file"]), "rb") as handle:
                hits = locate(handle.read(), m["old"])[1]
            bad += hits != 1
            print(f"  {'ok' if hits == 1 else 'BAD':<5} {m['name']:<42} anchor occurs {hits}x")
        print(f"check: {len(mutations) - bad}/{len(mutations)} anchors unique")
        return 1 if bad else 0
    # ⚠️ RECOVER FIRST, THEN BASELINE. Hashing before recovery captures the MUTATED file
    # as the baseline, so the restore at the end of the first mutation compares against a
    # corrupt reference and reports a false "RESTORE FAILED" on a tree that is actually
    # correct. Order matters more than it looks here.
    recover(cwd)
    baseline = {f: sha(f) for f in files}

    # --- The precondition. Without it, every "went red" below is meaningless. ---
    code, out = run(args.suite, cwd)
    if code != 0:
        print("ABORT: the suite is NOT GREEN on a clean tree, so no mutation result would mean\n"
              "anything -- a red run could simply be the suite failing to run at all.\n")
        print(out.strip()[-1200:])
        return 2
    print(f"PRECONDITION  green on a clean tree ({len(files)} file(s) under test)")
    print(f"              {out.strip().splitlines()[-1][:100] if out.strip() else '(no output)'}\n")

    passed, problems, warnings = 0, [], 0
    for index, m in enumerate(mutations, 1):
        name = m.get("name") or f"mutation {index}"
        path = os.path.join(cwd, m["file"])
        expect = m.get("expect", "")
        with open(path, "rb") as handle:
            original = handle.read()

        anchor, hits = locate(original, m["old"])
        if hits != 1:
            problems.append(name)
            print(f"  SKIP   {name:<42} anchor occurs {hits}x, not once -- unreliable")
            continue

        replacement = m.get("new", "")
        new_bytes = replacement.encode("utf-8")
        if replacement and b"\r\n" in anchor and b"\r\n" not in new_bytes:
            new_bytes = replacement.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8")

        # ⚠️ try/finally IS THE WHOLE SAFETY PROPERTY. Without it, Ctrl+C during a slow
        # suite -- or any exception between the write and the restore -- leaves the file
        # on disk WITH ITS GUARD DELETED and no warning. Verified: a 30 s suite killed at
        # 6 s left the mutation in place. This module's own docstring says a harness that
        # leaves the tree mutated is worse than no harness, so the restore must run on
        # every exit path, including KeyboardInterrupt.
        journal = os.path.join(cwd, JOURNAL)
        backup = os.path.join(cwd, JOURNAL + ".bak")
        try:
            with open(backup, "wb") as handle:
                handle.write(original)
            with open(journal, "w", encoding="utf-8") as handle:
                json.dump({"file": path, "backup": backup,
                           "sha256": baseline[path], "mutation": name}, handle)
            with open(path, "wb") as handle:
                handle.write(original.replace(anchor, new_bytes, 1))
            code, out = run(args.suite, cwd)
        finally:
            with open(path, "wb") as handle:
                handle.write(original)
            for leftover in (journal, backup):
                try:
                    os.remove(leftover)
                except OSError:
                    pass
            if sha(path) != baseline[path]:
                print(f"  ABORT  {name:<42} RESTORE FAILED -- tree is dirty, stopping now")
                return 2

        if code != 0 and (not expect or expect in out):
            passed += 1
            why = f"for the right reason ({expect!r})" if expect else "as expected"
            print(f"  RED    {name:<42} {why}")
            # ⚠️ `expect` is a SUBSTRING test, so a short or generic string can match text
            # the guard never produced. Verified: a mutation that only introduced a syntax
            # error printed "SyntaxError: invalid syntax", which satisfied expect="invalid"
            # and certified a guard that was never exercised. Quote the assertion verbatim.
            if expect and (len(expect) < 12 or " " not in expect):
                warnings += 1
                print(f"         ^ WEAK EXPECT {expect!r}: short/single-word substrings also "
                      "match crashes and syntax errors. Quote the assertion text.")
            # A unittest failure ALWAYS prints a traceback, so the markers below fire on every
            # honest Python guard unless the "it actually ran and asserted" evidence is checked
            # first — a warning that cries wolf on correct usage gets ignored, and then it is not
            # there when the mutation really did fail to load.
            # "Ran N tests" is NOT evidence: unittest's loader wraps an import failure as a
            # _FailedTest and still reports "Ran 1 test", so that disjunct silenced this warning for
            # any suite run through `unittest discover` — the common case. An AssertionError is the
            # only proof the guard was actually reached.
            asserted = "AssertionError" in out
            if expect and not asserted and any(marker in out for marker in
                              ("SyntaxError", "Traceback (most recent call last)",
                               "ReferenceError", "Cannot find module", "Parse error")):
                warnings += 1
                print("         ^ the output also contains a CRASH signature - confirm the "
                      "suite ran and asserted, rather than failing to load.")
        elif code != 0:
            problems.append(name)
            print(f"  RED?   {name:<42} but the output never mentions {expect!r}")
            hint = next((l.strip() for l in out.splitlines()
                         if "Error" in l or "assert" in l.lower()), "")
            if hint:
                print(f"         {hint[:110]}")
        else:
            problems.append(name)
            print(f"  GREEN  {name:<42} <-- VACUOUS: the guard does not hold")

    code, out = run(args.suite, cwd)
    restored = all(sha(f) == baseline[f] for f in files)
    print(f"\nRESTORED      byte-exactly: {'yes' if restored else 'NO'}")
    print(f"POSTCONDITION green again: {'yes' if code == 0 else 'NO'}")
    # Warnings go on the LAST line too: a caller that reads only the summary (quiet.py) must still
    # see that a RED may have been a crash rather than the guard.
    print(f"\nfalsified {passed}/{len(mutations)}"
          + (f"; {warnings} warning(s) - read the log" if warnings else "")
          + (f"; {len(problems)} problem(s): " + ", ".join(problems) if problems else ""))
    return 0 if (passed == len(mutations) and restored and code == 0) else 1


if __name__ == "__main__":
    sys.exit(main())
