#!/usr/bin/env python3
"""trigger_probe.py -- Windows-safe skill-trigger measurement.

skill-creator's run_loop.py waits on the `claude -p` pipe with select(), which Windows supports only
for sockets; every run there fails and reads as "not triggered". This runner reads the pipe on a
thread instead and asks the same question: does `claude -p <query>` invoke the skill?

    python scripts/trigger_probe.py local/evals/trigger-eval.json --skill asdev-blueprints --runs 3

Lives inside the skill (self-containment rule, SKILL.md section 8): the description and the tool that
measures it travel together.

Safety: each run starts in an empty sandbox directory, with only the Skill tool allowed and at most
two turns, so a query can be *decided* but nothing can be read, written or executed.
"""
from __future__ import annotations

import argparse
import json
import os
import tempfile
import shutil
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent  # scripts/ -> the skill directory


def invoked_skills(line: str) -> set[str]:
    """Skill NAMES actually invoked in one stream-json line.

    ⚠️ Do not shortcut this with a substring test. `'"name":"Skill"' in line and skill in line` looks
    right and is wrong twice over: it fires when the model invokes a DIFFERENT skill (correctly
    choosing `asdev-conventions` for a CSS fix counted as a asdev-blueprints trigger), and the
    skill's own name appears in the init event's available-skills list on every single run, so the
    second half of the test is always true. That defect scored five correct refusals as failures on
    2026-08-27 and sent a description rewrite chasing a regression that did not exist.
    """
    try:
        d = json.loads(line)
    except (json.JSONDecodeError, ValueError):
        return set()
    if not isinstance(d, dict):
        return set()
    msg = d.get("message")
    if not isinstance(msg, dict):          # some stream events carry `message` as a plain string
        return set()
    content = msg.get("content")
    if not isinstance(content, list):
        return set()
    found: set[str] = set()
    for c in content:
        if isinstance(c, dict) and c.get("type") == "tool_use" and c.get("name") == "Skill":
            name = (c.get("input") or {}).get("skill")
            if isinstance(name, str):
                found.add(name)
    return found


def run_failed(line: str) -> str | None:
    """The run's own verdict that it could not answer — an auth failure, a usage limit, a crash.

    Without this the probe cannot tell "the model chose no skill" from "the runner never got to
    decide", and reports the second as the first. That is not hypothetical: an expired OAuth
    session once turned every run into a 7-second error and the probe published 10/21, which reads
    exactly like a description regression. A measurement that cannot fail loudly is not a
    measurement. Mirrors falsify.py's green-precondition rule.
    """
    try:
        d = json.loads(line)
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(d, dict):
        return None
    # ONLY the failures that mean the model never got to choose. `error_max_turns` is NOT one of
    # them: this probe caps `--max-turns 2` on purpose, so a run that answers without a skill
    # routinely ends that way. Treating it as a failure aborted a perfectly good 21/21 once.
    if d.get("type") == "result" and d.get("subtype") == "error_during_execution":
        return str(d.get("result") or d.get("subtype"))[:200]
    msg = d.get("message")
    if isinstance(msg, dict):
        for c in msg.get("content") or []:
            if isinstance(c, dict) and c.get("type") == "text":
                text = (c.get("text") or "").strip()
                # STARTSWITH, never "contains": the eval set asks about billing and machine APIs,
                # and an answer that merely mentions a usage limit would have aborted all 63 runs.
                if text.startswith(("Failed to authenticate", "Usage limit", "Claude usage limit",
                                    "API Error")):
                    return text[:200]
    return None


def run_query(query: str, skill: str, model: str, timeout: int, sandbox: Path) -> dict:
    cmd = ["claude", "-p", query, "--output-format", "stream-json", "--verbose",
           "--include-partial-messages", "--model", model, "--allowedTools", "Skill", "--max-turns", "2"]
    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
    env["PYTHONUTF8"] = "1"
    # shell=False with a resolved executable: under shell=True on Windows, proc.kill() kills the
    # cmd.exe wrapper and orphans the real child, and the reader breaks early on every triggered
    # run — so a 63-run probe leaked a process per success.
    exe = shutil.which(cmd[0]) or cmd[0]
    proc = subprocess.Popen([exe, *cmd[1:]], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                            cwd=str(sandbox), env=env)
    lines: list[str] = []
    done = threading.Event()

    def reader() -> None:
        assert proc.stdout is not None
        for raw in proc.stdout:
            line = raw.decode("utf-8", errors="replace")
            lines.append(line)
            if invoked_skills(line):
                done.set()
                break
        done.set()

    t = threading.Thread(target=reader, daemon=True)
    t.start()
    start = time.time()
    done.wait(timeout)
    elapsed = round(time.time() - start, 1)
    timed_out = not done.is_set()
    try:
        proc.kill()
    except OSError:
        pass
    used: set[str] = set()
    error: str | None = None
    for line in lines:
        used |= invoked_skills(line)
        error = error or run_failed(line)
    triggered = skill in used
    # A run that invoked the skill answered the question, whatever it reported afterwards.
    if triggered:
        error = None
    elif not lines and not error:
        # Zero stream-json lines means the CLI died before saying anything — the exact shape the
        # expired-OAuth run took. Without this it scores as a calm "did not trigger".
        code = proc.poll()
        error = f"run produced no output (exit {code if code is not None else 'unknown'})"
    elif timed_out and not error:
        # A hung run never got to decide either — scoring it "did not trigger" is the same false
        # negative an auth failure produced, just slower.
        error = f"run timed out after {timeout}s without reaching a decision"
    return {"triggered": triggered, "timed_out": timed_out, "elapsed": elapsed, "lines": len(lines),
            "skills_used": sorted(used), "error": error}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("eval_set")
    ap.add_argument("--skill", required=True)
    # Pinned deliberately: the 21/21 baseline was measured on this model, and a comparison against
    # it is only meaningful on the same one. This is a reproducibility anchor, not the version-free
    # naming that prose uses — pass --model to measure elsewhere.
    ap.add_argument("--model", default="claude-fable-5")
    ap.add_argument("--runs", type=int, default=2)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--timeout", type=int, default=150)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    # The sandbox is neutral ground on purpose — outside the skill and outside any project — so the
    # cwd cannot colour the decision. (Tested 2026-08-27: moving it from inside the skill to here
    # changed nothing, 16/21 both ways, so location is NOT a confound. Kept neutral anyway.)
    sandbox = Path(tempfile.gettempdir()) / "asdev-blueprints-probe"
    sandbox.mkdir(parents=True, exist_ok=True)
    evals = json.loads(Path(args.eval_set).read_text(encoding="utf-8"))
    jobs = [(i, e, r) for i, e in enumerate(evals) for r in range(args.runs)]
    results: dict[int, list[dict]] = {i: [] for i in range(len(evals))}
    print(f"{len(jobs)} runs, {args.workers} workers, model {args.model}, timeout {args.timeout}s", flush=True)
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(run_query, e["query"], args.skill, args.model, args.timeout, sandbox): (i, r) for i, e, r in jobs}
        for f in as_completed(futs):
            i, r = futs[f]
            res = f.result()
            results[i].append(res)
            q = evals[i]
            print(f"  [{'T' if res['triggered'] else '-'}{'!' if res['timed_out'] else ' '}] {res['elapsed']:>6}s expected={q['should_trigger']} :: {q['query'][:70]}", flush=True)

    # A score computed over runs that never reached the model is worse than no score: it looks
    # exactly like a real regression and invites a "fix" to a description that was never broken.
    errors = [r["error"] for rs in results.values() for r in rs if r.get("error")]
    if errors:
        top = sorted({e for e in errors})[:3]
        print(f"\nABORTED — {len(errors)} of {len(jobs)} runs could not reach the model, so no score "
              f"is meaningful. Fix this, then re-run:", flush=True)
        for message in top:
            print(f"  {message}")
        if any("authenticate" in e.lower() for e in errors):
            print("  (an expired CLI session: sign in again, then re-run the probe)")
        return 2

    rows = []
    passed = 0
    for i, e in enumerate(evals):
        rs = results[i]
        rate = sum(1 for r in rs if r["triggered"]) / max(1, len(rs))
        timeouts = sum(1 for r in rs if r["timed_out"])
        ok = (rate >= 0.5) == e["should_trigger"]
        passed += ok
        others = sorted({n for r in rs for n in r.get("skills_used", []) if n != args.skill})
        rows.append({"query": e["query"], "should_trigger": e["should_trigger"], "trigger_rate": rate,
                     "timeouts": timeouts, "pass": ok, "other_skills_used": others, "runs": rs})
    summary = {"model": args.model, "runs_per_query": args.runs, "passed": passed, "total": len(evals), "rows": rows}
    out = Path(args.out).resolve() if args.out else SKILL_ROOT / ".sandbox" / "trigger_probe_results.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\n{passed}/{len(evals)} queries behave as expected")
    for r in rows:
        other = (" via " + ",".join(r["other_skills_used"])) if r["other_skills_used"] else ""
        print(f"  {'PASS' if r['pass'] else 'FAIL'} expected={r['should_trigger']} rate={r['trigger_rate']:.2f}{other} :: {r['query'][:76]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
