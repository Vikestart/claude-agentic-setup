#!/usr/bin/env python3
"""What a subagent ACTUALLY did — files, cost, and whether it stayed in its lane.

The house rule is "verify, don't trust the report": an agent's own summary is a claim, not
evidence. Two failure modes this makes cheap to catch:

  * SCOPE. A detached reviewer was told not to read a `local/` overlay, read it anyway, and then
    reasoned from what it saw. A read leaves no trace in Git, so nothing caught it — but the
    transcript records every tool call, so this does.
  * COST. Section 6 quotes measured figures (cold start, fresh input, duplicate reads). They came
    from one day's data and will drift. `--summary` regenerates them, so a rule can be re-grounded
    instead of slowly becoming folklore.

    python $HOME/.claude/skills/asdev-web-audit/scripts/agent_audit.py --summary
    python $HOME/.claude/skills/asdev-web-audit/scripts/agent_audit.py --agent a265bb1
    python $HOME/.claude/skills/asdev-web-audit/scripts/agent_audit.py --agent a265bb1 --forbidden "*/local/*"

Transcripts are discovered under `--projects-root` (default `$HOME/.claude/projects`), newest
session first. Read-only: this never writes to a transcript or a project.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import os
import statistics
import sys
from datetime import datetime
from pathlib import Path

USAGE_FIELDS = ("input_tokens", "output_tokens",
                "cache_creation_input_tokens", "cache_read_input_tokens")
# Tools whose input names a concrete path. Bash is excluded from path EXTRACTION — a shell command
# may touch any number of paths and guessing them would produce confident nonsense. But it is NOT
# excluded from the forbidden check: the reviewer this tool was written for read a forbidden
# directory with `cat`, and the first version reported "scope: clean", which is worse than no check
# at all. Bash commands are therefore substring-matched against forbidden globs (see `mentions`).
# Price weights relative to fresh input, as all three 2026-09-30 spend reports used them. A
# 5-minute cache write is really 1.25x; 2x (the 1-hour price) keeps figures comparable with theirs.
WEIGHTS = {"input_tokens": 1.0, "cache_read_input_tokens": 0.1,
           "cache_creation_input_tokens": 2.0, "output_tokens": 5.0}
GAP_SECONDS = 300  # the default subagent cache lifetime
PATH_TOOLS = {"Read": "read", "Write": "write", "Edit": "write", "NotebookEdit": "write"}


def default_projects_root() -> Path:
    return Path(os.environ.get("CLAUDE_PROJECTS_ROOT") or (Path.home() / ".claude" / "projects"))


def find_subagent_dirs(root: Path) -> list[Path]:
    """Every `subagents/` directory under the projects root, newest first."""
    if not root.is_dir():
        return []
    dirs = [p for p in root.glob("*/*/subagents") if p.is_dir()]
    return sorted(dirs, key=lambda p: p.stat().st_mtime, reverse=True)


def collect(paths: list[Path], root: Path) -> list[Path]:
    if paths:
        return [p for p in paths if p.is_file()]
    out: list[Path] = []
    for d in find_subagent_dirs(root):
        out.extend(sorted(d.glob("agent-*.jsonl")))
    return out


def read_agent(path: Path) -> dict:
    """One agent's transcript reduced to what a reviewer needs to judge it."""
    acc = {f: 0 for f in USAGE_FIELDS}
    acc.update(id=path.stem, model="", effort="", turns=0, tools=0, cold_start=0,
               first_ts="", last_ts="", reads={}, writes={}, bash=0, errors=0,
               bash_cmds=[], inputs=[], peak_ctx=0, ctx_sum=0, gap_writes=0)
    prev_at: datetime | None = None
    id_to_tool: dict[str, str] = {}
    seen_requests: set[str] = set()
    with path.open(encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue
            ts = rec.get("timestamp") or ""
            if ts:
                acc["first_ts"] = acc["first_ts"] or ts
                acc["last_ts"] = ts
            acc["effort"] = rec.get("effort") or acc["effort"]
            msg = rec.get("message")
            if not isinstance(msg, dict):
                continue
            usage = msg.get("usage")
            # ⚠️ COUNT EACH API RESPONSE ONCE. A response is written to the transcript as one
            # record PER CONTENT BLOCK (thinking, text, tool_use), and every one of those records
            # repeats the same `usage`. Summing per record inflated this session's totals by 2.97x
            # and put three-times-too-large figures into the global instruction file. `requestId`
            # is the response identity; records without one are counted individually.
            request_id = rec.get("requestId")
            if isinstance(usage, dict) and (request_id is None or request_id not in seen_requests):
                if request_id is not None:
                    seen_requests.add(request_id)
                acc["turns"] += 1
                for f in USAGE_FIELDS:
                    acc[f] += int(usage.get(f) or 0)
                if not acc["cold_start"]:
                    acc["cold_start"] = sum(int(usage.get(f) or 0) for f in USAGE_FIELDS)
                # Context = everything the response re-read or wrote to cache. Cost grows with
                # context x turns, so the peak and average say more than any total.
                ctx = sum(int(usage.get(f) or 0) for f in
                          ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"))
                acc["peak_ctx"] = max(acc["peak_ctx"], ctx)
                acc["ctx_sum"] += ctx
                at = parse_ts(ts)
                # A write straight after a pause longer than the cache lives is the whole context
                # being cached again — the cost the 1-hour agent cache exists to remove.
                if at and prev_at and (at - prev_at).total_seconds() > GAP_SECONDS:
                    acc["gap_writes"] += int(usage.get("cache_creation_input_tokens") or 0)
                prev_at = at or prev_at
            if isinstance(usage, dict):
                acc["model"] = msg.get("model") or acc["model"]
            for block in msg.get("content") or []:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "tool_use":
                    name = block.get("name") or "?"
                    acc["tools"] += 1
                    id_to_tool[block.get("id") or ""] = name
                    if name == "Bash":
                        acc["bash"] += 1
                    # EVERY tool's input is kept as text for the forbidden check, not just Bash's.
                    # `Grep` with output_mode=content returns file contents, takes `path` not
                    # `file_path`, and is not Bash — so a forbidden directory read that way was
                    # reported "scope: clean", the same false negative the `cat` spelling produced.
                    acc["inputs"].append(f"{name} {json.dumps(block.get('input') or {})}")
                    kind = PATH_TOOLS.get(name)
                    fp = (block.get("input") or {}).get("file_path")
                    if kind and isinstance(fp, str):
                        bucket = acc["reads"] if kind == "read" else acc["writes"]
                        bucket[fp] = bucket.get(fp, 0) + 1
                elif block.get("type") == "tool_result" and block.get("is_error"):
                    acc["errors"] += 1
    return acc


def mentions(command: str, pattern: str) -> bool:
    """Does a shell command name something the pattern forbids?

    The glob's literal segments must appear in order — `*/local/*` reduces to `/local/`, which
    catches `cat .../local/x.md` and `grep -r .../local` without trying to parse the command.
    A heuristic, and labelled as one: it is here to stop a false "clean", not to be exhaustive.

    CASE-SENSITIVE, like the path matching. `fnmatch` is case-insensitive on Windows, so a
    `*/local/*` rule also flagged every `AppData/Local/Temp` scratch path — noise that would
    have trained a reader to ignore the check.
    """
    # Collapse BOTH separators and runs of them: a Windows path inside tool-input JSON
    # arrives as `C:\\Users\\x`, which a single-backslash replace turns into `//` and no
    # literal ever matches again.
    cmd = re.sub(r"[\\/]+", "/", command)
    literals = [s for s in re.split(r"[*?\[\]]+", pattern.replace("\\", "/")) if s]
    pos = 0
    for index, literal in enumerate(literals):
        found = cmd.find(literal, pos)
        if found >= 0:
            pos = found + len(literal)
            continue
        # A rule written `*/local/*` means "anything under local/", and a tool that names the
        # DIRECTORY spells it `.../local"` with no trailing slash — `Grep --path .../local` slipped
        # through on exactly that. Retry the final literal without its slash, but require a path
        # boundary after it so `/localhost` is not swept in.
        if index == len(literals) - 1 and literal.endswith("/"):
            stem = literal[:-1]
            at = cmd.find(stem, pos)
            while at >= 0:
                if cmd[at + len(stem): at + len(stem) + 1] in ("", "/", '"', "'", " ", ",", ")"):
                    return True
                at = cmd.find(stem, at + 1)
        return False
    return True


def parse_ts(ts: str) -> datetime | None:
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")) if ts else None
    except ValueError:
        return None


def weighted(a: dict) -> float:
    return sum(a[f] * w for f, w in WEIGHTS.items())


def fresh(a: dict) -> int:
    """Input the model was billed to ingest — cache reads are nearly free and excluded."""
    return a["input_tokens"] + a["cache_creation_input_tokens"]


# Windows' own `AppData/Local` is not the `local/` overlay. It is excluded from the case-insensitive
# pass only — flagging every scratch path is how a warning gets trained out of a reader.
CASE_NOISE_RE = re.compile(r"appdata/local(?:low)?/", re.IGNORECASE)


def violations(a: dict, owned: list[str], forbidden: list[str]) -> tuple[list[str], list[str]]:
    """Paths the agent touched that its brief did not allow.

    Forbidden always wins. `owned` is only enforced for WRITES: a brief that names the files an
    agent may change should not also have to enumerate every file it may legitimately consult.

    Returns (violations, warnings). Matching is CASE-SENSITIVE, because `fnmatch` is not on Windows
    and `*/local/*` otherwise flagged every `AppData/Local/Temp` path. But case-sensitivity alone is
    a bypass — `X/Local/pointers` opens the same file — so a second, case-insensitive pass reports
    what it finds as a lower-confidence WARNING rather than silently letting it through.
    """
    out: list[str] = []
    soft: list[str] = []
    touched = [(p, "read") for p in a["reads"]] + [(p, "write") for p in a["writes"]]
    for path, kind in touched:
        norm = re.sub(r"[\\/]+", "/", path)
        if any(fnmatch.fnmatchcase(norm, pat) for pat in forbidden):
            out.append(f"{kind} FORBIDDEN  {path}")
        elif (not CASE_NOISE_RE.search(norm)
              and any(fnmatch.fnmatchcase(norm.lower(), pat.lower()) for pat in forbidden)):
            soft.append(f"{kind} case-only  {path}")
        elif kind == "write" and owned and not any(fnmatch.fnmatchcase(norm, p) for p in owned):
            out.append(f"write NOT-OWNED {path}")
    for raw in a.get("inputs", []):
        for pat in forbidden:
            if mentions(raw, pat):
                out.append(f"tool  FORBIDDEN  {raw.strip()[:90]}")
                break
            if not CASE_NOISE_RE.search(re.sub(r"[\\/]+", "/", raw)) and mentions(raw.lower(), pat.lower()):
                soft.append(f"tool  case-only  {raw.strip()[:90]}")
                break
    return sorted(set(out)), sorted(set(soft))


def report_one(a: dict, owned: list[str], forbidden: list[str], top: int) -> int:
    print(f"\n=== {a['id']} ===")
    print(f"  model {a['model'] or '?'}   effort {a['effort'] or '?'}   turns {a['turns']}   "
          f"tools {a['tools']} ({a['bash']} bash)   tool errors {a['errors']}")
    print(f"  cold start {a['cold_start']:,}   fresh input {fresh(a):,}   "
          f"output {a['output_tokens']:,}   cache read {a['cache_read_input_tokens']:,}")
    avg = a["ctx_sum"] // a["turns"] if a["turns"] else 0
    print(f"  context avg {avg:,}   peak {a['peak_ctx']:,}   cache writes after >5-min gaps "
          f"{a['gap_writes']:,}   weighted {weighted(a):,.0f}")
    if a["first_ts"]:
        print(f"  {a['first_ts']} -> {a['last_ts']}")
    for label, bucket in (("read", a["reads"]), ("written", a["writes"])):
        if not bucket:
            continue
        rows = sorted(bucket.items(), key=lambda kv: -kv[1])
        print(f"  files {label}: {len(rows)}")
        for path, n in rows[:top]:
            flag = f" x{n}" if n > 1 else ""
            print(f"    {path}{flag}")
        if len(rows) > top:
            print(f"    ... +{len(rows) - top} more (--top 0 for all)")
    bad, soft = violations(a, owned, forbidden)
    if soft:
        print(f"  ~~ {len(soft)} case-only match(es) - a capitalised segment opens the same file "
              f"on Windows, so treat as probable evasion:")
        for line in soft:
            print(f"    {line}")
    if bad:
        print(f"  !! {len(bad)} SCOPE VIOLATION(S):")
        for line in bad:
            print(f"    {line}")
    elif owned or forbidden and not soft:
        print("  scope: clean")
    return 1 if bad else 0


def report_summary(agents: list[dict]) -> int:
    """Regenerate the figures section 6 quotes, from whatever transcripts exist now."""
    if not agents:
        print("no agent transcripts found")
        return 0
    colds = sorted(a["cold_start"] for a in agents if a["cold_start"]) or [0]
    freshes = sorted(fresh(a) for a in agents) or [0]
    seen: dict[str, int] = {}
    for a in agents:
        for path, n in a["reads"].items():
            seen[path] = seen.get(path, 0) + n
    total_reads = sum(seen.values())
    repeat_reads = sum(n - 1 for n in seen.values() if n > 1)

    print(f"{len(agents)} agent transcript(s)\n")
    print(f"  cold start      min {colds[0]:,}  median {statistics.median(colds):,.0f}  max {colds[-1]:,}")
    print(f"  fresh input     min {freshes[0]:,}  median {statistics.median(freshes):,.0f}  max {freshes[-1]:,}")
    print(f"  output tokens   total {sum(a['output_tokens'] for a in agents):,}")
    peaks = sorted(a["peak_ctx"] for a in agents)
    print(f"  peak context    median {statistics.median(peaks):,.0f}  max {peaks[-1]:,}")
    print(f"  weighted total  {sum(weighted(a) for a in agents):,.0f}   of which cache writes after "
          f">5-min gaps {sum(a['gap_writes'] for a in agents) * WEIGHTS['cache_creation_input_tokens']:,.0f}")
    print(f"  tool calls      total {sum(a['tools'] for a in agents):,}")
    print(f"  distinct files read {len(seen):,}; repeat reads {repeat_reads:,} "
          f"({100 * repeat_reads / max(total_reads, 1):.0f}% of all reads were of a file "
          f"already read by some agent)")
    hottest = sorted(seen.items(), key=lambda kv: -kv[1])[:5]
    if hottest and hottest[0][1] > 1:
        print("  most re-read:")
        for path, n in hottest:
            if n > 1:
                print(f"    {n}x  {path}")
    print("\n  Section 6 quotes these; re-run after a wave of agents to keep them honest.")
    return 0


def main() -> int:
    # The default Windows console codec is cp1252 and this script prints paths it did not choose.
    # Without this, one non-ASCII byte anywhere aborts the whole report.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("transcripts", nargs="*", type=Path, help="agent-*.jsonl paths (default: discover)")
    ap.add_argument("--agent", action="append", default=[],
                    help="match an agent id or prefix; repeatable")
    ap.add_argument("--projects-root", type=Path, default=None)
    ap.add_argument("--owned", action="append", default=[],
                    help="glob an agent MAY write; anything else it writes is flagged")
    ap.add_argument("--forbidden", action="append", default=[],
                    help="glob the agent must not touch at all, read included")
    ap.add_argument("--summary", action="store_true", help="aggregate figures instead of per-agent detail")
    ap.add_argument("--top", type=int, default=8, help="files listed per bucket (0 = all)")
    args = ap.parse_args()

    root = args.projects_root or default_projects_root()
    paths = collect(list(args.transcripts), root)
    if args.agent:
        paths = [p for p in paths if any(a.lower() in p.stem.lower() for a in args.agent)]
    if not paths:
        # FAIL CLOSED. A scope-verification tool that answers "nothing found" with a
        # success code turns a typo in --agent into a clean bill of health.
        print(f"no agent transcripts found (looked under {root})")
        return 0 if not (args.agent or args.transcripts) else 1

    agents = [read_agent(p) for p in paths]
    if args.summary:
        return report_summary(agents)
    top = args.top if args.top > 0 else 10 ** 9
    bad = 0
    for a in sorted(agents, key=lambda x: -fresh(x)):
        bad += report_one(a, args.owned, args.forbidden, top)
    if bad:
        print(f"\n{bad} agent(s) went outside their declared scope")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
