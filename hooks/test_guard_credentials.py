"""Checks the credentials guard (guard_credentials.py) against sample shell commands: each must be
refused or allowed as listed. Run after any change to the guard: python test_guard_credentials.py"""
import json, subprocess, sys, pathlib
H = pathlib.Path.home().as_posix()
hook = f"{H}/.claude/hooks/guard_credentials.py"
cases = [  # (command, cwd, expect_block)
 ("cd ~/.claude && grep -rn 'max' --include=*.md . | head", "C:/xampp/htdocs", True),
 ("grep -rn foo ~/.claude", "C:/xampp/htdocs", True),
 ("grep -rn foo", H + "/.claude", True),
 ("grep -rn foo --exclude=.credentials.json ~/.claude", "C:/xampp/htdocs", False),
 ("grep -rn foo ~/.claude/skills", "C:/xampp/htdocs", False),
 ("cd ~/.claude && grep -rn foo skills .docs", "C:/xampp/htdocs", False),
 ("cat ~/.claude/.credentials.json", "C:/xampp/htdocs", True),
 ("Get-Content $env:USERPROFILE\.claude\*", "C:/xampp/htdocs", True),
 ("rg foo ~/.claude", "C:/xampp/htdocs", False),
 ("rg --hidden foo ~/.claude", "C:/xampp/htdocs", True),
 ("rg --hidden -g '!.credentials.json' foo ~/.claude", "C:/xampp/htdocs", False),
 ("Get-ChildItem -Recurse ~/.claude | Select-String token", "C:/xampp/htdocs", True),
 ("Get-ChildItem -Recurse ~/.claude -Filter *.md", "C:/xampp/htdocs", False),
 ("find ~/.claude -type f -exec cat {} +", "C:/xampp/htdocs", True),
 ("find ~/.claude/agents -name '*.md'", "C:/xampp/htdocs", False),
 ("cd ~/.claude/agents && ls && cat opus-high-executor.md", "C:/xampp/htdocs", False),
 ("grep -rn foo src/", "C:/xampp/htdocs", False),
 ("git status", H, False),
 ("cd ~/.claude && find skills/asdev-web-audit -name '*.pyc' | head -3", "C:/xampp/htdocs", False),
 ("find ~/.claude/* -type f -exec cat {} +", "C:/xampp/htdocs", True),
 ("grep -rl secret /c/Users/aleks", "C:/xampp/htdocs", True),
 ("cd ~/.claude && ls -A; ls -A .docs | head -3", "C:/xampp/htdocs", False),
 ("ls -AR ~/.claude | xargs cat", "C:/xampp/htdocs", True),
 ("dir /s %USERPROFILE%\.claude | findstr x", "C:/xampp/htdocs", True),
 ("Get-ChildItem ~/.claude | Select-Object Name", "C:/xampp/htdocs", False),
]
bad = 0
for cmd, cwd, exp in cases:
    r = subprocess.run([sys.executable, hook], input=json.dumps({"tool_name":"Bash","tool_input":{"command":cmd},"cwd":cwd}), capture_output=True, text=True)
    got = '"deny"' in r.stdout
    if got != exp or r.returncode or r.stderr:
        bad += 1; print("FAIL", exp, got, r.returncode, cmd, r.stderr[-300:])
print(f"{len(cases)-bad}/{len(cases)} ok")
