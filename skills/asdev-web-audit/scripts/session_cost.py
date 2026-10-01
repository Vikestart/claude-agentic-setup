#!/usr/bin/env python3
"""What a whole session cost — the main chat and every subagent — price-weighted and split by cause.

`agent_audit.py` looks at one agent at a time; this looks at a session, so a night's work can be
compared with an earlier one. Usage is deduped by `requestId` (each content block repeats it).

Weights, relative to fresh input = 1: cache read 0.1, cache write 1.25 (5-min) or 2 (1-hour),
output 5. Each transcript's cost is split into:
  * fixed  — the start-up context (system prompt, tool definitions, instructions, brief), re-read
             on every turn. Shrinks with a smaller tool set or shorter instructions.
  * growth — everything added after the first turn (tool results, own edits and commands),
             re-read on every later turn. Shrinks with smaller reads and fewer turns.
  * writes — cache writes; output — tokens written.

    python $HOME/.claude/skills/asdev-web-audit/scripts/session_cost.py --project tilspire --since 2026-10-01
    python $HOME/.claude/skills/asdev-web-audit/scripts/session_cost.py <main-transcript.jsonl> ...

Read-only.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
from datetime import datetime, timezone

PARTS = ("fixed", "growth", "writes", "output")


def stamp(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def load(path: pathlib.Path):
    reqs: dict[str, tuple[str, dict]] = {}
    compactions = 0
    first_user = ""
    for line in path.open(encoding="utf-8", errors="replace"):
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if r.get("isCompactSummary"):
            compactions += 1
        msg = r.get("message") or {}
        if not first_user and r.get("type") == "user" and isinstance(msg.get("content"), str):
            first_user = " ".join(msg["content"].split())[:60]
        u, rid = msg.get("usage"), r.get("requestId")
        if u and rid:  # the last record of a request carries its final output count
            reqs[rid] = (reqs.get(rid, (r.get("timestamp") or "",))[0], u)
    return sorted(reqs.values(), key=lambda x: x[0]), compactions, first_user


def measure(rows) -> dict:
    m = dict.fromkeys(PARTS, 0.0) | {"turns": len(rows), "peak": 0, "ctx_sum": 0, "gaps": 0}
    cold = None
    prev = None
    for ts, u in rows:
        cr = u.get("cache_read_input_tokens", 0)
        cw = u.get("cache_creation_input_tokens", 0)
        inp = u.get("input_tokens", 0)
        ctx = inp + cr + cw
        cold = ctx if cold is None else cold
        w1h = (u.get("cache_creation") or {}).get("ephemeral_1h_input_tokens", 0)
        m["fixed"] += inp + 0.1 * min(cold, cr)
        m["growth"] += 0.1 * max(cr - cold, 0)
        m["writes"] += 2 * w1h + 1.25 * max(cw - w1h, 0)
        m["output"] += 5 * u.get("output_tokens", 0)
        m["peak"] = max(m["peak"], ctx)
        m["ctx_sum"] += ctx
        if ts and prev and (stamp(ts) - stamp(prev)).total_seconds() > 3600:
            m["gaps"] += 1
        prev = ts or prev
    m["cold"] = cold or 0
    m["cost"] = sum(m[p] for p in PARTS)
    return m


def line(label: str, m: dict) -> str:
    avg = m["ctx_sum"] // m["turns"] if m["turns"] else 0
    return (f"  {label:13} turns {m['turns']:>5} | start {m['cold']/1e3:>4.0f}k | peak {m['peak']/1e3:>4.0f}k"
            f" | avg {avg/1e3:>4.0f}k | {m['cost']/1e6:>6.2f}M | >1h gaps {m['gaps']}")


def report(main: pathlib.Path, top: int) -> None:
    rows, compactions, first_user = load(main)
    if not rows:
        return
    mm = measure(rows)
    span = f"{rows[0][0][:16]} – {rows[-1][0][:16]} UTC"
    print(f"\n{main.parent.name}/{main.stem[:8]}  {span}  compactions {compactions}  {first_user!r}")
    print(line("main", mm))
    agents = []
    sub = main.with_suffix("") / "subagents"
    for a in sorted(sub.glob("agent-*.jsonl")) if sub.is_dir() else []:
        arows, _, _ = load(a)
        if arows:
            agents.append((a.stem[6:13], measure(arows)))
    for name, am in sorted(agents, key=lambda x: -x[1]["cost"])[:top]:
        print(line(f"agent {name}", am))
    if len(agents) > top:
        print(f"  … {len(agents) - top} more agents")
    total = mm["cost"] + sum(am["cost"] for _, am in agents)
    print(f"  TOTAL {total/1e6:.2f}M weighted; main {mm['cost']/total*100:.0f}%, {len(agents)} agents")
    if agents:
        acost = sum(am["cost"] for _, am in agents) or 1
        split = ", ".join(f"{p} {sum(am[p] for _, am in agents)/acost*100:.0f}%" for p in PARTS)
        print(f"  agents' cost: {split}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("transcripts", nargs="*", type=pathlib.Path)
    ap.add_argument("--projects-root", type=pathlib.Path, default=pathlib.Path.home() / ".claude" / "projects")
    ap.add_argument("--project", action="append", default=[], help="substring of a project folder (repeatable)")
    ap.add_argument("--since", help="only transcripts modified on or after this date (YYYY-MM-DD)")
    ap.add_argument("--top", type=int, default=5, help="agents listed per session")
    a = ap.parse_args()
    paths = list(a.transcripts)
    if not paths:
        since = datetime.fromisoformat(a.since).replace(tzinfo=timezone.utc).timestamp() if a.since else 0
        for d in sorted(a.projects_root.iterdir()) if a.projects_root.is_dir() else []:
            if a.project and not any(p.lower() in d.name.lower() for p in a.project):
                continue
            paths += [p for p in d.glob("*.jsonl") if p.stat().st_mtime >= since]
    if not paths:
        print("no transcripts matched")
        return 1
    for p in sorted(paths, key=lambda p: p.stat().st_mtime, reverse=True):
        report(p, a.top)
    return 0


if __name__ == "__main__":
    sys.exit(main())
