"""Tests for the shared-setup tooling: run `python install/test_setup.py`.

Everything that touches a home folder runs in a scratch one (USERPROFILE/HOME pointed at a temp
folder holding a copy of this repo), so the real ~/.claude is never changed.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "skills" / "asdev-web-audit" / "scripts"
sys.path[:0] = [str(REPO / "install"), str(SCRIPTS)]

import install  # noqa: E402
import sync_agents_md  # noqa: E402

FRAGMENT = json.loads((REPO / "settings" / "shared-settings.json").read_text(encoding="utf-8"))


def run(argv, home=None, cwd=None, extra_env=None):
    env = dict(os.environ)
    if home is not None:
        env.update(USERPROFILE=str(home), HOME=str(home))
    env.pop("SETUP_INSTALL_FAULT", None)
    env.update(extra_env or {})
    return subprocess.run(argv, cwd=cwd, env=env, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=300)


def scratch_home(testcase) -> Path:
    """A temp home whose ~/.claude holds a copy of this repo, minus git history and private parts."""
    home = Path(tempfile.mkdtemp(prefix="setup-test-"))
    testcase.addCleanup(shutil.rmtree, home, ignore_errors=True)
    shutil.copytree(REPO, home / ".claude" / "claude-agentic-setup",
                    ignore=shutil.ignore_patterns(".git", "__pycache__", "local", ".sandbox"))
    run(["git", "init", "-q"], cwd=home / ".claude" / "claude-agentic-setup")
    return home


class ImportExpansion(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="setup-imports-"))
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)

    def write(self, name, text):
        path = self.dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def test_whole_line_imports_are_inlined_and_nothing_else(self):
        top = self.write("a.md", "top\n@b.md\n```\n@c.md\n```\nmail me @ x or @b.md inline\n@~/p.md\nend\n")
        self.write("b.md", "B1\n@sub/d.md\n")
        self.write("sub/d.md", "D\n")
        self.write("home/p.md", "P\n")
        with mock.patch.object(Path, "home", return_value=self.dir / "home"):
            text = sync_agents_md.expand_imports(top)
        self.assertEqual(text, "top\nB1\nD\n```\n@c.md\n```\nmail me @ x or @b.md inline\nP\nend\n")

    def test_a_missing_import_fails_loudly(self):
        top = self.write("a.md", "x\n@nope.md\n")
        caught = None
        try:
            sync_agents_md.expand_imports(top)
        except BaseException as exc:  # noqa: BLE001 - the type IS what is under test
            caught = exc
        self.assertIsInstance(caught, SystemExit, f"no guard message, got {type(caught).__name__}")
        self.assertIn("which does not exist", str(caught))

    def test_substitute_swaps_the_personal_file(self):
        top = self.write("a.md", "@mine.md\n")
        self.write("mine.md", "MINE\n")
        example = self.write("example.md", "EXAMPLE\n")
        text = sync_agents_md.expand_imports(top, substitute={self.dir / "mine.md": example})
        self.assertEqual(text, "EXAMPLE\n")


class SettingsMerge(unittest.TestCase):
    def test_merge_adds_everything_once(self):
        merged, changes, _ = install.merge_settings({"theme": "dark"}, FRAGMENT, {})
        self.assertTrue(changes)
        self.assertEqual(merged["theme"], "dark")
        for entry in FRAGMENT["add"]["permissions.allow"]:
            self.assertIn(entry, merged["permissions"]["allow"])
        again, changes2, _ = install.merge_settings(merged, FRAGMENT, FRAGMENT["set"])
        self.assertEqual(changes2, [])
        self.assertEqual(again, merged)

    def test_a_personal_override_is_kept(self):
        mine = {"workflowSizeGuideline": "large"}
        merged, changes, overrides = install.merge_settings(mine, FRAGMENT, FRAGMENT["set"])
        self.assertEqual(merged["workflowSizeGuideline"], "large")
        self.assertTrue(any("workflowSizeGuideline" in o for o in overrides))

    def test_a_changed_shared_value_lands(self):
        fragment = json.loads(json.dumps(FRAGMENT))
        fragment["set"]["workflowSizeGuideline"] = "large"
        merged, changes, _ = install.merge_settings({"workflowSizeGuideline": FRAGMENT["set"]["workflowSizeGuideline"]},
                                                    fragment, FRAGMENT["set"])
        self.assertEqual(merged["workflowSizeGuideline"], "large")
        self.assertIn("updated workflowSizeGuideline", changes)

    def test_unset_removes_only_the_value_the_setup_wrote(self):
        fragment = {"unset": {"autoCompactWindow": 400000}}
        merged, changes, _ = install.merge_settings({"autoCompactWindow": 400000, "theme": "dark"}, fragment, {})
        self.assertEqual(merged, {"theme": "dark"})
        self.assertIn("unset autoCompactWindow", changes)
        mine, changes2, _ = install.merge_settings({"autoCompactWindow": 700000}, fragment, {})
        self.assertEqual(mine, {"autoCompactWindow": 700000}, "a personal value must stay")
        self.assertEqual(changes2, [])

    def test_a_hook_already_there_in_another_spelling_is_not_added_twice(self):
        mine = {"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [
            {"type": "command", "command": 'python "C:/Users/p/.claude/hooks/guard_credentials.py"'}]}]}}
        merged, _, _ = install.merge_settings(mine, FRAGMENT, {})
        commands = [h["command"] for g in merged["hooks"]["PreToolUse"] for h in g["hooks"]]
        self.assertEqual(sum("guard_credentials.py" in c for c in commands), 1, f"guard added twice: {commands}")

    def test_an_unreadable_hook_command_fails_closed(self):
        fragment = {"add": {"hooks": {"PreToolUse": [{"matcher": "*", "command": "python ~/.claude/hooks/x.py",
                                                     "timeout": 5}]}}}
        with self.assertRaises(install.Stop, msg="unreadable hook form was not refused"):
            install.hook_scripts(fragment)

    def test_retire_removes_only_what_it_names(self):
        base, _, _ = install.merge_settings({}, FRAGMENT, {})
        base["permissions"]["allow"].append("Bash(mine)")
        fragment = json.loads(json.dumps(FRAGMENT))
        gone = fragment["add"]["permissions.allow"].pop()
        hook = fragment["add"]["hooks"]["PostToolUse"].pop()
        fragment["retire"] = {"permissions.allow": [gone], "hooks": {"PostToolUse": [hook]}}
        merged, _, _ = install.merge_settings(base, fragment, FRAGMENT["set"])
        self.assertNotIn(gone, merged["permissions"]["allow"])
        self.assertIn("Bash(mine)", merged["permissions"]["allow"])
        commands = [h["command"] for g in merged.get("hooks", {}).get("PostToolUse", []) for h in g["hooks"]]
        self.assertNotIn(hook["command"], commands)


class AgentDefinitions(unittest.TestCase):
    # At spawn depth 1 the harness stops nesting anyway. This keeps the frontmatter honest for the day
    # the depth rises again (phase leads, rolled back 2026-09-30): then only the frontmatter stops it.
    def test_only_phase_leads_keep_the_agent_tool(self):
        defs = sorted((REPO / "agents").glob("*.md"))
        self.assertTrue(any(p.name.endswith("-lead.md") for p in defs), "no lead definitions found")
        for path in defs:
            front = path.read_text(encoding="utf-8").split("---")[1]
            fields = dict(line.split(":", 1) for line in front.strip().splitlines() if ":" in line)
            # `Task` is the Agent tool's legacy name; `Agent(type, …)` limits it but still grants it.
            spawn = ("Agent", "Task")
            denied = {t.strip() for t in fields.get("disallowedTools", "").split(",")}
            allowed = fields.get("tools")
            grants = allowed is None or any(t.strip().split("(")[0] in spawn for t in allowed.split(","))
            can_spawn = not denied.intersection(spawn) and grants
            with self.subTest(path.name):
                self.assertEqual(can_spawn, path.name.endswith("-lead.md"),
                                 "only *-lead.md may keep the Agent tool")


class GitBash(unittest.TestCase):
    def test_found_from_the_git_a_hook_sees(self):
        root = Path(tempfile.mkdtemp(prefix="setup-gitbash-"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        git = root / "Git" / "mingw64" / "libexec" / "git-core" / "git.exe"
        bash = root / "Git" / "bin" / "bash.exe"
        for f in (git, bash):
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_bytes(b"")
        env = {k: v for k, v in os.environ.items() if k != "CLAUDE_CODE_GIT_BASH_PATH"}
        with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(install.os, "name", "nt"), \
                mock.patch.object(install.shutil, "which", return_value=str(git)):
            self.assertEqual(install.find_bash(), str(bash), "Git Bash not found from a hook's git.exe")


class PreCommit(unittest.TestCase):
    def setUp(self):
        self.repo = Path(tempfile.mkdtemp(prefix="setup-precommit-"))
        self.addCleanup(shutil.rmtree, self.repo, ignore_errors=True)
        run(["git", "init", "-q"], cwd=self.repo)

    def stage(self, path, text):
        target = self.repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        run(["git", "add", "-f", path], cwd=self.repo)
        return run([sys.executable, str(REPO / "install" / "precommit.py")], cwd=self.repo)

    def test_clean_docs_that_name_token_prefixes_pass(self):
        r = self.stage("README.md", "Scans for `sk-ant-`, `ghp_` and `AKIA` prefixes.\n")
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_a_token_shaped_string_is_refused(self):
        fake = "gh" + "p_" + "A1b2" * 9  # built here, so no token-shaped text sits in this file
        r = self.stage("README.md", f"token = {fake}\n")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("looks like a GitHub token", r.stdout)

    def test_a_local_overlay_is_refused(self):
        r = self.stage("skills/asdev-web-audit/local/projects.md", "private\n")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("private folder", r.stdout)


class Installer(unittest.TestCase):
    def installer(self, home):
        return [sys.executable, str(home / ".claude" / "claude-agentic-setup" / "install" / "install.py")]

    def seed(self, home):
        claude = home / ".claude"
        (claude / "agents").mkdir(parents=True)
        (claude / "agents" / "my-agent.md").write_text("mine\n", encoding="utf-8")
        (claude / "hooks").mkdir()
        (claude / "hooks" / "my_hook.py").write_text("print('mine')\n", encoding="utf-8")
        (claude / "CLAUDE.md").write_text("my own rules\n", encoding="utf-8")
        (claude / "settings.json").write_text(json.dumps({"theme": "dark", "workflowSizeGuideline": "large"}),
                                              encoding="utf-8")

    def test_fresh_machine_install_rerun_check_and_uninstall(self):
        home = scratch_home(self)
        self.seed(home)
        claude, repo = home / ".claude", home / ".claude" / "claude-agentic-setup"

        first = run(self.installer(home), home=home)
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        for link in ("agents", "hooks", ".docs", "skills/asdev-web-audit"):
            self.assertTrue(install.is_link(claude / link), link)
        self.assertEqual((claude / "CLAUDE.md").read_bytes(), install.STUB)
        self.assertEqual((claude / "CLAUDE.personal.md").read_text(encoding="utf-8"), "my own rules\n")
        self.assertTrue((repo / "agents" / "my-agent.md").is_file())
        self.assertTrue((repo / "hooks" / "my_hook.py").is_file())
        ignored = run(["git", "status", "--porcelain", "--ignored"], cwd=repo).stdout
        self.assertIn("!! agents/my-agent.md", ignored)
        self.assertIn("!! hooks/my_hook.py", ignored)
        settings = json.loads((claude / "settings.json").read_text(encoding="utf-8"))
        self.assertEqual(settings["theme"], "dark")
        self.assertEqual(settings["workflowSizeGuideline"], "large")
        self.assertIn(FRAGMENT["add"]["permissions.deny"][0], settings["permissions"]["deny"])
        backups = list((claude / "backups").glob("pre-install-*"))
        self.assertEqual(len(backups), 1)
        self.assertTrue((backups[0] / "agents" / "my-agent.md").is_file())

        second = run(self.installer(home), home=home)
        self.assertIn("everything was already in place", second.stdout, second.stdout)
        checked = run(self.installer(home) + ["--check"], home=home)
        self.assertEqual(checked.returncode, 0, checked.stdout)

        parity_root = run([sys.executable, "-c", "import harness_parity; print(harness_parity.HOME_ROOT)"],
                          home=home, cwd=claude / "skills" / "asdev-web-audit" / "scripts")
        self.assertEqual(Path(parity_root.stdout.strip()), claude,
                         f"harness_parity looks in the wrong home {parity_root.stderr}")
        audit = run([sys.executable, str(claude / "skills" / "asdev-web-audit" / "scripts" / "security_audit.py"),
                     "--path", str(claude / "skills" / "asdev-web-audit")], home=home)
        self.assertEqual(audit.returncode, 0, "the scanner flagged its own folder " + audit.stdout[-800:])

        gone = run(self.installer(home) + ["--uninstall"], home=home)
        self.assertEqual(gone.returncode, 0, gone.stdout + gone.stderr)
        for link in ("agents", "hooks", ".docs", "skills/asdev-web-audit"):
            self.assertFalse(install.is_link(claude / link), link)
            self.assertTrue((claude / link).is_dir(), link)
        self.assertTrue((claude / "agents" / "my-agent.md").is_file())
        self.assertEqual((claude / "CLAUDE.md").read_bytes(), (repo / "CLAUDE.shared.md").read_bytes())

    def test_a_failed_swap_puts_the_original_back(self):
        home = scratch_home(self)
        self.seed(home)
        claude = home / ".claude"
        r = run(self.installer(home), home=home, extra_env={"SETUP_INSTALL_FAULT": "after-backup"})
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("injected fault", r.stderr)
        self.assertTrue((claude / "agents").is_dir() and not install.is_link(claude / "agents"),
                        "agents folder was not put back")
        self.assertEqual((claude / "agents" / "my-agent.md").read_text(encoding="utf-8"), "mine\n")
        self.assertFalse((claude / "agents.install-tmp").exists())

    def test_foreign_files_stop_the_install_before_any_change(self):
        home = scratch_home(self)
        self.seed(home)
        claude = home / ".claude"
        (claude / ".docs").mkdir()
        (claude / ".docs" / "notes.md").write_text("mine\n", encoding="utf-8")
        r = run(self.installer(home), home=home)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn(".docs holds files the repo does not have", r.stdout)
        self.assertFalse(install.is_link(claude / "agents"))
        self.assertEqual((claude / "CLAUDE.md").read_text(encoding="utf-8"), "my own rules\n")


if __name__ == "__main__":
    unittest.main(verbosity=1)
