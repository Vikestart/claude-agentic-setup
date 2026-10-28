#!/usr/bin/env python3
"""Hand one task to Gemini through Antigravity CLI (`agy -p`) and print its report.

    gemini.py --brief FILE [--repo DIR] [--rev REV] [--edit] [--effort low|medium|high] [--timeout S]

Gemini works in a fresh git worktree of REV (default HEAD), never in the repo itself: a worktree
holds only committed files, so `.env` and everything else git ignores never reach Google
(owner, 2026-10-27). A secret that is committed stops the run before agy starts. Uncommitted
changes are not in the worktree either: commit what Gemini should see.

Without --edit it runs in agy's plan mode and changes nothing (reviews, questions). With --edit
its changes come back as a patch file for you to check and `git apply`; the repo is untouched.
The model is the newest `gemini-*-<effort>` that `agy models` lists, so a new release needs no edit.

Prints one status line (status, model, seconds, tokens), then Gemini's report; with --edit also
the diffstat and the patch path. Exit 0 done, 1 agy failed, 2 refused.
"""
import argparse, json, os, re, shutil, subprocess, sys, tempfile, time
from pathlib import Path

SECRET = re.compile(r"(^|/)(\.env(\.(?!example$)[^/]+)?|[^/]+\.(key|p12|pfx)|id_(rsa|ed25519|ecdsa)[^/]*|\.credentials\.json)$", re.I)
# A .pem may hold only a public key or certificate, safe to share (tilspire commits one, 2026-10-28):
# it passes when every block is public and nothing says PRIVATE; anything else in a .pem is refused.
PEM = re.compile(r"(^|/)[^/]+\.pem$", re.I)
PUBLIC_BLOCKS = {"PUBLIC KEY", "RSA PUBLIC KEY", "CERTIFICATE", "TRUSTED CERTIFICATE"}
# Windows caps a command line at 32,767 characters; the brief travels as one argument.
BRIEF_MAX = 30_000


def agy_cmd() -> list[str]:
    # AGY points the tests at a fake agy; a .py there runs under this interpreter.
    path = os.environ.get("AGY") or shutil.which("agy") or str(Path(os.environ.get("LOCALAPPDATA", "")) / "agy" / "bin" / "agy.exe")
    return [sys.executable, path] if path.endswith(".py") else [path]


def git(*args: str, cwd: Path) -> str:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True).stdout


def public_pem(repo: Path, rev: str, path: str) -> bool:
    # Read the committed blob, not the working tree: the commit is what Gemini would see.
    text = subprocess.run(["git", "show", f"{rev}:{path}"], cwd=repo, capture_output=True).stdout.decode("utf-8", "replace")
    blocks = re.findall(r"-----BEGIN ([A-Z0-9 ]+)-----", text)
    return bool(blocks) and set(blocks) <= PUBLIC_BLOCKS and "PRIVATE" not in text.upper()


def refuse(msg: str) -> int:
    print(f"gemini: REFUSED {msg}")
    return 2


def pick_model(effort: str) -> str | None:
    out = subprocess.run([*agy_cmd(), "models"], capture_output=True, text=True).stdout
    ids = [ln.split()[0] for ln in out.splitlines() if re.match(rf"gemini-\S+-{effort}\s", ln)]
    # Newest first: compare the version numbers, not the strings ("3.10" sorts after "3.9").
    ver = lambda m: [int(n) for n in re.findall(r"\d+", m)]
    return max(ids, key=ver) if ids else None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--brief", required=True)
    ap.add_argument("--repo", default=".")
    ap.add_argument("--rev", default="HEAD")
    ap.add_argument("--edit", action="store_true")
    ap.add_argument("--effort", choices=["low", "medium", "high"], default="high")
    ap.add_argument("--timeout", type=int, default=900)
    a = ap.parse_args()

    brief = Path(a.brief).read_text(encoding="utf-8")
    if len(brief) > BRIEF_MAX:
        return refuse(f"brief is {len(brief)} characters, over {BRIEF_MAX}: point Gemini at files instead")
    try:
        repo = Path(git("rev-parse", "--show-toplevel", cwd=Path(a.repo)).strip())
    except (subprocess.CalledProcessError, FileNotFoundError, NotADirectoryError):
        return refuse(f"{a.repo} is not in a git repository")
    try:
        files = git("ls-tree", "-r", "--name-only", a.rev, cwd=repo).splitlines()
    except subprocess.CalledProcessError:
        return refuse(f"no revision {a.rev} in {repo}")
    secrets = [f for f in files if SECRET.search(f) or (PEM.search(f) and not public_pem(repo, a.rev, f))]
    if secrets:
        return refuse(f"{a.rev} contains committed secrets, which would go to Google: {', '.join(secrets[:5])}")
    model = pick_model(a.effort)
    if not model:
        print(f"gemini: FAILED `agy models` lists no gemini-*-{a.effort} model (signed out?)")
        return 1

    run = Path(tempfile.mkdtemp(prefix="agy-run-"))
    wt = run / "wt"
    git("worktree", "add", "--detach", str(wt), a.rev, cwd=repo)
    try:
        t0 = time.monotonic()
        proc = subprocess.run(
            [*agy_cmd(), "-p", brief, "--mode", "accept-edits" if a.edit else "plan", "--model", model,
             "--output-format", "json", "--print-timeout", f"{a.timeout}s"],
            cwd=wt, capture_output=True, text=True, encoding="utf-8", errors="replace")
        secs = round(time.monotonic() - t0)
        try:
            res = json.loads(proc.stdout)
        except ValueError:
            print(f"gemini: FAILED exit {proc.returncode} after {secs}s, no JSON; last output:")
            print("\n".join((proc.stdout + proc.stderr).strip().splitlines()[-15:]))
            return 1
        u = res.get("usage") or {}
        report = (res.get("response") or "").strip()
        # agy says SUCCESS even when a refused tool ended the turn with no answer.
        status = res.get("status", "?") if report else "FAILED (no answer)"
        print(f"gemini: {status} {model} {secs}s in={u.get('input_tokens', '?')} out={u.get('output_tokens', '?')}")
        denied = sorted({d.get("display_name") or d.get("action", "?") for d in res.get("denied_actions") or []})
        if denied:
            # Shell commands stay refused: one could read files outside the worktree. Gemini edits; we run the checks.
            print(f"gemini: refused {', '.join(denied)} (headless agy runs no commands; brief it to read and edit only)")
        print(report)
        git("add", "-A", cwd=wt)
        diff = git("diff", "--cached", "--binary", cwd=wt)
        if diff and not a.edit:
            print("gemini: WARNING review mode changed files; the changes were discarded")
        elif diff:
            patch = run / "changes.patch"
            patch.write_text(diff, encoding="utf-8", newline="\n")
            print(git("diff", "--cached", "--stat", cwd=wt).rstrip())
            print(f"gemini: patch {patch} (check it, then `git apply` it in {repo})")
        elif a.edit:
            print("gemini: no changes made")
        return 0 if status == "SUCCESS" else 1
    finally:
        subprocess.run(["git", "worktree", "remove", "--force", str(wt)], cwd=repo, capture_output=True)


if __name__ == "__main__":
    sys.exit(main())
