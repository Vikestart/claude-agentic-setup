"""Fast stdlib regression tests for the asdev-web-audit plumbing."""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stderr
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import agent_audit
import audit_all
import automation_mine
import convention_audit
import handover
import lint_rules
import quiet
import token_analyzer
import unused_css_detector
from _baseline import apply as apply_baseline
from _common import Report, base_parser, find_git, git_changed, set_scope


class CoordinationToolTests(unittest.TestCase):
    """agent_audit / handover — the two things that read agent transcripts and repo state."""

    def _transcript(self, root: Path, blocks: list[dict]) -> Path:
        path = root / "agent-deadbeef.jsonl"
        lines = [json.dumps({"timestamp": "2026-09-01T00:00:00Z", "message": {
            "role": "assistant", "model": "claude-opus-5",
            "usage": {"input_tokens": 10, "output_tokens": 5,
                      "cache_creation_input_tokens": 1, "cache_read_input_tokens": 2},
            "content": [b]}}) for b in blocks]
        path.write_text("\n".join(lines), encoding="utf-8")
        return path

    def test_context_peak_gap_rewrites_and_weighted_cost(self):
        # Three responses; the third follows a 10-minute pause, so its cache write is a re-cache.
        # The peak is the MIDDLE response, so keeping only the last value would fail.
        # The first is written twice (two content blocks, one requestId) and must count once.
        def rec(rid, ts, read, write):
            return json.dumps({"requestId": rid, "timestamp": ts, "message": {
                "role": "assistant", "usage": {"input_tokens": 10, "output_tokens": 100,
                "cache_read_input_tokens": read, "cache_creation_input_tokens": write},
                "content": [{"type": "text", "text": "x"}]}})
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "agent-feed.jsonl"
            path.write_text("\n".join([
                rec("r1", "2026-09-30T10:00:00Z", 0, 50_000),
                rec("r1", "2026-09-30T10:00:00Z", 0, 50_000),
                rec("r2", "2026-09-30T10:01:00Z", 50_000, 1_000),
                rec("r3", "2026-09-30T10:11:00Z", 0, 40_000)]), encoding="utf-8")
            a = agent_audit.read_agent(path)
        self.assertEqual(a["turns"], 3)
        self.assertEqual(a["peak_ctx"], 51_010)
        self.assertEqual(a["gap_writes"], 40_000)
        # input 30 + read 50,000 x 0.1 + write 91,000 x 2 + output 300 x 5
        self.assertEqual(agent_audit.weighted(a), 30 + 5_000 + 182_000 + 1_500)

    def test_forbidden_read_is_caught_through_any_tool_not_just_read(self):
        """Reaching a forbidden path by ANY tool must not report "scope: clean".

        Two false negatives, found one after the other: inspecting only Read/Write inputs missed the
        reviewer that used `cat`, and then matching only Bash missed `Grep`, which returns file
        contents and takes `path` rather than `file_path`. Every tool's input is matched now.
        """
        for tool, payload in (("Bash", {"command": "cat /repo/x/local/pointers/admin.md"}),
                              ("Grep", {"pattern": "x", "path": "/repo/x/local", "output_mode": "content"}),
                              ("Glob", {"pattern": "/repo/x/local/**"})):
            with self.subTest(tool=tool), tempfile.TemporaryDirectory() as tmp:
                path = self._transcript(Path(tmp), [
                    {"type": "tool_use", "id": "1", "name": tool, "input": payload}])
                agent = agent_audit.read_agent(path)
                self.assertEqual(agent["reads"], {},
                                 "paths must not be guessed out of a non-path tool")
                bad, _ = agent_audit.violations(agent, [], ["*/local/*"])
                self.assertTrue(bad, f"{tool} reached a forbidden path and was reported clean")

    def test_forbidden_matching_is_case_sensitive(self):
        """`*/local/*` must not flag Windows' `AppData/Local/Temp`.

        fnmatch is case-insensitive on Windows, so the naive version flagged every scratch path and
        would have trained a reader to ignore the check.
        """
        with tempfile.TemporaryDirectory() as tmp:
            path = self._transcript(Path(tmp), [
                {"type": "tool_use", "id": "1", "name": "Read",
                 "input": {"file_path": r"C:\Users\x\AppData\Local\Temp\scratch.py"}},
            ])
            agent = agent_audit.read_agent(path)
            hard, soft = agent_audit.violations(agent, [], ["*/local/*"])
            self.assertEqual(hard, [], "AppData/Local must not match a lowercase local/ rule")
            self.assertEqual(soft, [], "AppData/Local must not even warn - it is not the overlay")
            self.assertTrue(agent_audit.violations(agent, [], ["*/Local/*"])[0])

    def test_capitalised_segment_warns_instead_of_slipping_through(self):
        """`X/Local/pointers` opens the same file on Windows as `local/`.

        Case-sensitive matching killed the AppData noise but opened a bypass; the second pass
        reports it as a lower-confidence warning rather than saying nothing.
        """
        with tempfile.TemporaryDirectory() as tmp:
            path = self._transcript(Path(tmp), [
                {"type": "tool_use", "id": "1", "name": "Bash",
                 "input": {"command": "cat /repo/x/Local/pointers/admin.md"}}])
            agent = agent_audit.read_agent(path)
            hard, soft = agent_audit.violations(agent, [], ["*/local/*"])
            self.assertEqual(hard, [], "an exact-case rule should not hard-fail on a case variant")
            self.assertTrue(soft, "a capitalised segment must at least warn, not pass silently")

    def test_handover_refuses_to_overwrite_and_leaves_judgement_blank(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            text = handover.build(root, None, False)
            self.assertGreaterEqual(text.count(handover.TODO), 3,
                                    "decisions, next steps and deployment stay unwritten")
            out = root / ".docs" / "handover.md"
            out.parent.mkdir(parents=True)
            out.write_text("hand-written, do not lose", encoding="utf-8")
            argv = ["handover.py", "--path", str(root)]
            buf = io.StringIO()
            with patch.object(sys, "argv", argv), redirect_stdout(buf):
                self.assertEqual(handover.main(), 1,
                                 "handover must refuse to overwrite without --force")
            self.assertEqual(out.read_text(encoding="utf-8"), "hand-written, do not lose")

    def test_icon_block_exempts_a_drawn_shape_but_still_flags_a_glyph(self):
        """The house style puts a bar's colour on a parent rule, so size alone must exempt."""
        with tempfile.TemporaryDirectory() as tmp:
            css = Path(tmp) / "a.css"
            css.write_text(".chart .bar i{height:100%;display:block;}\n"
                           ".empty i{display:block;font-size:3rem;}\n", encoding="utf-8")
            report = Report("lint_rules")
            lint_rules.lint_css(report, tmp)
            rules = [i for i in report.items if i["rule"] == "CSS_ICON_BLOCK"]
            self.assertEqual(len(rules), 1, f"expected only the glyph to flag, got {rules}")
            self.assertEqual(rules[0]["line"], 2)


class AuditPlumbingTests(unittest.TestCase):
    def tearDown(self) -> None:
        set_scope(None, "whole project")

    def test_advisory_findings_do_not_fail_but_unreadable_blocking_files_do(self):
        advisory = Report("advisory", advisory=True)
        advisory.add("x.css", 1, "SOFT", "review this")
        self.assertEqual(advisory.exit_code, 0)

        blocking = Report("blocking")
        blocking.unread("x.php", "permission denied")
        self.assertEqual(blocking.exit_code, 1)

    def test_scope_flags_are_mutually_exclusive(self):
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            base_parser("test").parse_args(["--changed", "--staged"])

    def test_aggregate_fails_closed_when_a_scanner_crashes(self):
        with tempfile.TemporaryDirectory() as root:
            stdout = io.StringIO()
            with (patch.object(audit_all, "TOOLS", [("missing_auditor", True)]),
                  patch.object(sys, "argv", ["audit_all.py", "--path", root, "-q"]),
                  redirect_stdout(stdout), self.assertRaises(SystemExit) as stopped):
                audit_all.main()
            self.assertEqual(stopped.exception.code, 1)
            self.assertIn("aggregate is incomplete", stdout.getvalue())

    def test_quiet_aggregate_emits_one_clean_summary_line(self):
        with tempfile.TemporaryDirectory() as root:
            stdout = io.StringIO()
            with (patch.object(audit_all, "TOOLS", []),
                  patch.object(sys, "argv", ["audit_all.py", "--path", root, "-q"]),
                  redirect_stdout(stdout), self.assertRaises(SystemExit) as stopped):
                audit_all.main()
            self.assertEqual(stopped.exception.code, 0)
            self.assertEqual(1, len(stdout.getvalue().strip().splitlines()))

    def test_unused_css_uses_whole_project_usage_context(self):
        with tempfile.TemporaryDirectory() as root:
            Path(root, "style.css").write_text(".used{color:red;}\n", encoding="utf-8")
            Path(root, "index.html").write_text(
                '<div class="used"></div>\n', encoding="utf-8"
            )
            set_scope({"style.css"}, "fixture")
            report = unused_css_detector.run(SimpleNamespace(path=root))
            self.assertFalse(any(item["rule"] == "UNUSED_CLASS"
                                 for item in report.items))

    def test_custom_token_limits_keep_project_relative_scope(self):
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root, "assets", "js")
            folder.mkdir(parents=True)
            Path(root, ".token-limits.json").write_text(json.dumps({
                "assets/js": {"size_kb": 0, "lines": 0, "ext": [".js"]}
            }), encoding="utf-8")
            Path(folder, "app.js").write_text("export const ok = true;\n", encoding="utf-8")
            set_scope({"assets/js/app.js"}, "fixture")
            report = token_analyzer.run(SimpleNamespace(path=root))
            self.assertEqual(report.items[0]["file"], "assets/js/app.js")

    def test_high_confidence_conventions_are_scanned(self):
        with tempfile.TemporaryDirectory() as root:
            Path(root, "app.html").write_text(
                '<svg></svg><img src="data:image/png;base64,AAAA">\n',
                encoding="utf-8",
            )
            set_scope({"app.html"}, "fixture")
            report = convention_audit.run(SimpleNamespace(path=root))
            rules = {item["rule"] for item in report.items}
            self.assertEqual({"BASE64_IMAGE", "INLINE_SVG"}, rules)

    def test_a_sprite_reference_is_not_inline_svg_but_a_drawing_is(self):
        with tempfile.TemporaryDirectory() as root:
            Path(root, "icons.php").write_text(
                "<?php echo '<svg class=\"i\" aria-hidden=\"true\"><use href=\"/icons.svg#house\"></use></svg>';\n"
                "<?php echo '<svg viewBox=\"0 0 24 24\"><path d=\"M3 3h18\"/></svg>';\n"
                "<?php echo '<svg><use href=\"#a\"/><circle r=\"2\"/></svg>';\n",
                encoding="utf-8",
            )
            set_scope({"icons.php"}, "fixture")
            report = convention_audit.run(SimpleNamespace(path=root))
            lines = sorted(item["line"] for item in report.items if item["rule"] == "INLINE_SVG")
            self.assertEqual([2, 3], lines)

    def test_configured_lockstep_rule_fires_for_a_half_finished_release(self):
        """The `lockstep` rule kind, exercised through whatever local/ actually configures.

        Skips cleanly when no local overlay is installed — that is the normal state on a machine
        other than the author's, and a shared skill must not fail there.
        """
        rules = [r for r in convention_audit._load_project_rules() if r.get("kind") == "lockstep"]
        if not rules:
            self.skipTest("no local/project-rules.json lockstep rule configured")
        rule = rules[0]
        with tempfile.TemporaryDirectory() as parent:
            root = Path(parent, rule["project"])
            root.mkdir()
            first = rule["paths"][0]
            target = Path(root, first)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("// changed\n", encoding="utf-8")
            set_scope({first}, "fixture")
            report = convention_audit.run(SimpleNamespace(path=str(root)))
            self.assertTrue(any(item["rule"] == rule["code"] for item in report.items),
                            f"{rule['code']} did not fire when only {first} changed")

    def test_reviewed_baseline_matches_exact_source_context(self):
        with tempfile.TemporaryDirectory() as root:
            line = '$q = $pdo->prepare("SELECT * FROM users WHERE id = ?");'
            Path(root, "app.php").write_text(line + "\n", encoding="utf-8")
            Path(root, ".audit-baseline.json").write_text(json.dumps({
                "entries": [{
                    "scanner": "security_audit",
                    "rule": "SQL_INJECTION",
                    "file": "app.php",
                    "line": 1,
                    "context": line,
                    "reason": "Reviewed fixture",
                }]
            }), encoding="utf-8")
            report = Report("security_audit")
            report.add("app.php", 1, "SQL_INJECTION", "fixture finding")
            accepted, diagnostics = apply_baseline([(report, True)], root)
            self.assertEqual(accepted, 1)
            self.assertFalse(report.items)
            self.assertFalse(diagnostics)

    def test_git_scope_includes_modified_and_untracked_files(self):
        git = find_git()
        if not git:
            self.skipTest("git unavailable")
        with tempfile.TemporaryDirectory() as root:
            commands = [
                ["init", "-q"],
                ["config", "user.email", "audit@example.invalid"],
                ["config", "user.name", "Audit Test"],
            ]
            for args in commands:
                subprocess.run([git, *args], cwd=root, check=True,
                               capture_output=True)
            Path(root, "tracked.js").write_text("const a = 1;\n", encoding="utf-8")
            subprocess.run([git, "add", "tracked.js"], cwd=root, check=True,
                           capture_output=True)
            subprocess.run([git, "commit", "-qm", "fixture"], cwd=root,
                           check=True, capture_output=True)
            Path(root, "tracked.js").write_text("const a = 2;\n", encoding="utf-8")
            Path(root, "new.css").write_text(".x{color:red;}\n", encoding="utf-8")
            self.assertEqual(git_changed(root), {"tracked.js", "new.css"})


class QuietRunnerTests(unittest.TestCase):
    """quiet.py — one line into the context, everything else into the log, exit code untouched."""

    def _run(self, code: str, *opts: str) -> tuple[int, str, Path]:
        log = Path(tempfile.mkdtemp()) / "run.log"
        out = io.StringIO()
        with redirect_stdout(out):
            rc = quiet.main([*opts, "--log", str(log), "--", sys.executable, "-c", code])
        return rc, out.getvalue(), log

    def test_pass_keeps_exit_code_and_prints_one_line(self) -> None:
        rc, out, log = self._run("print('a'); print('3 passed')")
        self.assertEqual(rc, 0)
        self.assertEqual(len(out.strip().splitlines()), 1)
        self.assertIn("3 passed", out)
        self.assertEqual(log.read_text(encoding="utf-8").split(), ["a", "3", "passed"])

    def test_failure_keeps_exit_code_and_shows_tail(self) -> None:
        rc, out, _ = self._run("import sys; [print(f'line {i}') for i in range(50)]; sys.exit(3)",
                               "--tail", "5")
        self.assertEqual(rc, 3)
        self.assertTrue(out.startswith("exit=3 |"))
        self.assertIn("line 49", out)
        self.assertNotIn("line 44", out)

    def test_summary_regex_picks_last_match(self) -> None:
        _, out, _ = self._run("print('suite A: 2 passed'); print('suite B: 5 passed'); print('done')",
                              "--summary", r"\d+ passed")
        self.assertIn("suite B: 5 passed", out)
        self.assertNotIn("done", out.split("|")[1])

    def test_shell_string_runs_under_bash_not_cmd(self) -> None:
        # cmd.exe passes single quotes through, so this printed nothing and still exited 0.
        if not quiet.find_bash():
            self.skipTest("no bash on this machine")
        log = Path(tempfile.mkdtemp()) / "run.log"
        with redirect_stdout(io.StringIO()) as out:
            rc = quiet.main(["--shell", "--log", str(log), "--",
                             f"'{Path(sys.executable).as_posix()}' -c 'print(41 + 1)' && echo second"])
        self.assertEqual(rc, 0)
        self.assertEqual(log.read_text(encoding="utf-8").split(), ["42", "second"])

    def test_one_string_without_shell_is_not_found_with_a_hint(self) -> None:
        log = Path(tempfile.mkdtemp()) / "run.log"
        with redirect_stdout(io.StringIO()) as out:
            rc = quiet.main(["--log", str(log), "--", "python -c 'print(1)'"])
        self.assertEqual(rc, 127)
        self.assertIn("needs --shell", out.getvalue())

    def test_timeout_kills_the_whole_tree(self) -> None:
        # A grandchild that outlives a killed parent keeps writing — to a log, or a database.
        tmp = Path(tempfile.mkdtemp())
        marker = tmp / "marker.txt"
        child = f"import time, pathlib; time.sleep(3); pathlib.Path(r'{marker}').write_text('late')"
        parent = (f"import subprocess, sys, time; subprocess.Popen([sys.executable, '-c', {child!r}]); "
                  "time.sleep(30)")
        with redirect_stdout(io.StringIO()):
            rc = quiet.main(["--timeout", "1", "--log", str(tmp / "run.log"), "--",
                             sys.executable, "-c", parent])
        self.assertEqual(rc, 124)
        time.sleep(4)
        self.assertFalse(marker.exists(), "the grandchild survived the timeout")

    def test_undecodable_output_does_not_crash(self) -> None:
        rc, out, _ = self._run("import sys; sys.stdout.buffer.write(b'caf\\xe9 ok\\n')")
        self.assertEqual(rc, 0)
        self.assertIn("ok", out)


class AutomationMineTests(unittest.TestCase):
    """automation_mine — the ranking a new script is chosen from must group and count honestly."""

    PATCH = ("python - <<'PY'\nimport io\np = '{p}'\ns = io.open(p, encoding='utf-8', newline='').read()\n"
             "old = '{o}'\nassert s.count(old) == 1\ns = s.replace(old, 'x')\n"
             "io.open(p, 'w', encoding='utf-8', newline='').write(s)\nPY")

    def _use(self, tid, name, inp):
        return json.dumps({"message": {"role": "assistant", "content": [
            {"type": "tool_use", "id": tid, "name": name, "input": inp}]}})

    def test_same_habit_groups_across_paths_and_a_failure_is_counted(self):
        lines = [self._use(f"t{i}", "Bash", {"command": self.PATCH.format(p=p, o=o)})
                 for i, (p, o) in enumerate([("a.php", "foo"), ("b/c.js", "bar(1)"), ("d.css", "x:y")])]
        # The second patch run failed: its result is an error, and only that one may be flagged.
        lines.append(json.dumps({"message": {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "t1", "is_error": True, "content": "Exit code 1"}]}}))
        # Two json runs: a group of two is what the second, merging pass may wrongly fold in.
        for tid in ("t8", "t9"):
            lines.append(self._use(tid, "Bash", {"command": "python -c \"import json, sys; "
                                   "d = json.load(open(sys.argv[1])); json.dump(d, sys.stdout)\" x.json"}))
        lines.append(self._use("t10", "Bash", {"command": "grep -n foo a.php"}))
        lines.append(self._use("t11", "Write", {"file_path": "C:/x/scratchpad/p.py", "content": "print(1)"}))
        lines.append(self._use("t12", "Write", {"file_path": "C:/proj/app.py", "content": "print(1)"}))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "s.jsonl"
            path.write_text("\n".join(lines), encoding="utf-8")
            runs, heads = automation_mine.read_transcript(path)
        self.assertEqual(sorted(r["kind"] for r in runs), ["inline"] * 5 + ["scratch"])
        self.assertEqual([r["fail"] for r in runs[:3]], [0, 1, 0], "only the failed run is flagged")
        groups = automation_mine.cluster(runs)
        patch_group = next(g for g in groups if len(g) >= 3)
        self.assertEqual(len(patch_group), 3, "the three patch runs are one habit, the json runs are not")
        self.assertIn(2, [len(g) for g in groups], "the json runs are their own habit")
        self.assertNotIn("grep", " ".join(heads), "reading is not a procedure")

    def test_head_names_the_procedure_not_its_arguments(self):
        h = automation_mine.head
        self.assertEqual(h("python install/verify.py --gate ."), "python verify.py")
        self.assertEqual(h("cd /c/repo && git status -sb"), "git status")
        self.assertEqual(h("python - <<'PY'\nprint(1)\nPY"), "python (inline)")
        self.assertEqual(h("python -X utf8 C:\\s\\falsify.py --suite x"), "python falsify.py")


if __name__ == "__main__":
    unittest.main(verbosity=2)
