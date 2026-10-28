#!/usr/bin/env python3
"""Tests for gemini.py against a fake agy: what Gemini can see, what comes back, what is refused."""
import json, os, shutil, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
root = Path(tempfile.mkdtemp())
results = []

FAKE = r'''
import json, os, sys
from pathlib import Path
if sys.argv[1] == "models":
    print("gemini-3.8-flash-high\tGemini 3.8 Flash (High)\ngemini-3.10-flash-high\tGemini 3.10 Flash (High)\n"
          "gemini-3.10-flash-low\tGemini 3.10 Flash (Low)\nclaude-opus-4-6-thinking\tClaude Opus 4.6 (Thinking)")
    sys.exit()
seen = sorted(str(p.relative_to(Path.cwd())).replace("\\", "/") for p in Path.cwd().rglob("*") if ".git" not in p.parts)
Path(os.environ["FAKE_LOG"]).write_text(json.dumps({"argv": sys.argv[1:], "seen": seen}))
if "mute" in sys.argv[2]:
    print(json.dumps({"status": "SUCCESS", "response": "", "denied_actions": [{"action": "command", "display_name": "RunCommand"}]}))
    sys.exit()
if "accept-edits" in sys.argv:
    Path("a.py").write_text("fixed\n")
print(json.dumps({"status": "SUCCESS", "response": "report text", "usage": {"input_tokens": 5, "output_tokens": 2}}))
'''


def check(name, cond):
    results.append(bool(cond))
    print(("ok   " if cond else "FAIL ") + name)


def sh(*args, cwd):
    subprocess.run(args, cwd=cwd, check=True, capture_output=True)


def run(repo, *extra):
    log.unlink(missing_ok=True)
    p = subprocess.run([sys.executable, str(HERE / "gemini.py"), "--brief", str(brief), "--repo", str(repo), *extra],
                       capture_output=True, text=True, env={**os.environ, "AGY": str(fake), "FAKE_LOG": str(log)})
    return p.returncode, p.stdout, json.loads(log.read_text()) if log.exists() else None


try:
    fake = root / "agy.py"
    fake.write_text(FAKE)
    log, brief = root / "log.json", root / "brief.md"
    brief.write_text("Review a.py.")
    repo = root / "repo"
    repo.mkdir()
    sh("git", "init", "-q", cwd=repo)
    (repo / "a.py").write_text("bug\n")
    (repo / ".gitignore").write_text(".env\n")
    (repo / ".env.example").write_text("KEY=\n")
    sh("git", "add", ".", cwd=repo)
    sh("git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "init", cwd=repo)
    (repo / ".env").write_text("KEY=secret\n")
    (repo / "draft.py").write_text("uncommitted\n")

    code, out, got = run(repo)
    check("a review sees the committed files", got and "a.py" in got["seen"] and ".env.example" in got["seen"])
    check("a review never sees .env or uncommitted files",
          got and ".env" not in got["seen"] and "draft.py" not in got["seen"])
    check("a review runs in plan mode on the newest model of the effort",
          got and got["argv"][got["argv"].index("--mode") + 1] == "plan"
          and got["argv"][got["argv"].index("--model") + 1] == "gemini-3.10-flash-high")
    check("the report and a status line come back", code == 0 and "gemini: SUCCESS" in out and "report text" in out)

    code, out, got = run(repo, "--edit", "--effort", "low")
    patch = next((ln.split()[2] for ln in out.splitlines() if ln.startswith("gemini: patch ")), None)
    check("an edit comes back as a patch and leaves the repo untouched",
          code == 0 and patch and "+fixed" in Path(patch).read_text() and (repo / "a.py").read_text() == "bug\n")
    check("the worktree is removed afterwards", subprocess.run(["git", "worktree", "list"], cwd=repo,
          capture_output=True, text=True).stdout.count("\n") == 1)

    brief.write_text("mute: run a command.")
    code, out, got = run(repo)
    check("an empty answer after a refused command fails and names the refusal",
          code == 1 and "FAILED (no answer)" in out and "refused RunCommand" in out)
    brief.write_text("Review a.py.")

    def commit(msg):
        sh("git", "add", "-A", cwd=repo)
        sh("git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", msg, cwd=repo)

    pub = "-----BEGIN PUBLIC KEY-----\nMFkw\n-----END PUBLIC KEY-----\n"
    (repo / "claims-public-key.pem").write_text(pub)
    commit("public key")
    code, out, got = run(repo)
    check("a committed .pem holding only a public key is let through", code == 0 and got is not None)

    (repo / "server.pem").write_text("-----BEGIN CERTIFICATE-----\nMIIB\n-----END CERTIFICATE-----\n"
                                     # Split so the precommit scan does not take the fixture for a real key.
                                     "-----BEGIN " + "PRIVATE KEY-----\nMIIE\n-----END " + "PRIVATE KEY-----\n")
    commit("cert and key")
    (repo / "server.pem").write_text(pub)
    code, out, got = run(repo)
    check("a committed .pem with a private key stops the run, whatever the working tree holds",
          code == 2 and "server.pem" in out and "claims-public-key.pem" not in out and got is None)
    sh("git", "checkout", "--", "server.pem", cwd=repo)

    sh("git", "add", "-f", ".env", cwd=repo)
    sh("git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "leak", cwd=repo)
    code, out, got = run(repo)
    check("a committed .env stops the run before agy starts", code == 2 and "REFUSED" in out and got is None)

    plain = root / "plain"
    plain.mkdir()
    code, out, got = run(plain)
    check("a folder outside git is refused", code == 2 and got is None)
finally:
    shutil.rmtree(root, ignore_errors=True)

print(f"{sum(results)}/{len(results)} ok")
sys.exit(0 if all(results) else 1)
