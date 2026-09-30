#!/usr/bin/env python3
"""Which throwaway work keeps being rewritten — ranked, so the next script is chosen from data.

CLAUDE.md §0: "a procedure done twice becomes a script." Nobody remembers doing something twice
across sessions, but the transcripts do. Two signals:

  * THROWAWAY SCRIPTS — inline interpreter runs (`python - <<EOF`, `python -c`, `node -e`,
    `php -r`), shell blocks of six lines or more, and scripts written to a temp or scratch folder.
    Each is reduced to its identifiers (strings, paths and numbers removed) and grouped with
    others that share at least half of them, so "the patch script" is one row however its paths
    and strings changed.
  * REPEATED SEQUENCES — two to four consecutive shell commands (program + subcommand or script
    name) that recur across transcripts.

Rows are ranked by the tokens the model wrote to produce them (characters / 4), because output is
priced several times input and never cached. `fail` counts runs whose tool result was an error:
a shape that fails often is a trap a script would remove, not just a cost.

    python $HOME/.claude/skills/asdev-web-audit/scripts/automation_mine.py
    python $HOME/.claude/skills/asdev-web-audit/scripts/automation_mine.py --since 2026-09-01 --project tilspire

Read-only. Samples are printed locally and truncated; nothing leaves the machine.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

SHELL_TOOLS = {"Bash", "PowerShell"}
INLINE = re.compile(r"\b(?:python3?|py)(?:\.exe)?\s+(?:-c\b|-\s*<<|-\s*$)|\bnode\s+-e\b|\bphp\s+-r\b|"
                    r"\bcat\s+>\s*\S+\.(?:py|js|php|ps1|sh)\s*<<", re.M)
SCRATCH = re.compile(r"[\\/](?:scratchpad|Temp|tmp)[\\/]", re.I)
SCRIPT_EXT = (".py", ".js", ".mjs", ".php", ".ps1", ".sh")
BLOCK_LINES = 6
SIMILAR = 0.5
MIN_SHAPE = 3
STRINGS = re.compile(r'"""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\'|"(?:\\.|[^"\\\n])*"|\'(?:\\.|[^\'\\\n])*\'')
PATHS = re.compile(r"\S*[\\/]\S*")
IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]{2,}")
# Words every script shares say nothing about what it does, and would glue unrelated ones together.
STOP = set("""and are for from import def return with not None True False elif else while try except
finally class lambda pass break continue yield print open len str int range list dict encoding utf
EOF PY python python3 exe echo cat the then done fi esac""".split())
# Looking is not a procedure: "grep -> sed" topped every table and says nothing to automate.
READERS = set("""grep rg sed cat head tail ls wc find echo cut sort uniq tr awk diff file stat
get-content select-string get-childitem test-path select-object measure-object write-output""".split())


def default_projects_root() -> Path:
    return Path(os.environ.get("CLAUDE_PROJECTS_ROOT") or (Path.home() / ".claude" / "projects"))


def shape(text: str) -> frozenset[str]:
    text = PATHS.sub(" ", STRINGS.sub(" ", text))
    return frozenset(w for w in IDENT.findall(text) if w not in STOP)


def head(command: str) -> str:
    """`python install/verify.py --gate .` -> `python verify.py`; `git status -sb` -> `git status`."""
    words = command.strip().split()
    while words and (words[0] in ("cd", "&&") or "=" in words[0]):
        words = words[2:] if words[0] == "cd" else words[1:]
    if not words:
        return ""
    prog = re.split(r"[\\/]", words[0].strip("\"'"))[-1].lower().removesuffix(".exe")
    base = lambda w: re.split(r"[\\/]", w.strip("\"'"))[-1]
    if prog.startswith(("python", "py", "node", "php")):
        # Flags may take values (`-X utf8`), so the name is the script file or the `-m` module.
        for i, w in enumerate(words[1:], 1):
            if w in ("-", "-c", "-e", "-r") or w.startswith("<<"):
                return prog + " (inline)"
            if w == "-m" and i + 1 < len(words):
                return prog + " -m " + words[i + 1]
            if w.strip("\"'").lower().endswith(SCRIPT_EXT):
                return prog + " " + base(w)
            if w in ("&&", "|", ";"):
                break
        return prog
    if len(words) > 1 and not words[1].startswith("-") and words[1] not in ("&&", "|", ";"):
        return prog + " " + base(words[1])
    return prog


def body_of(cmd: str) -> str:
    """The script inside an inline run. `python -c "..."` is one quoted string, and shape()
    drops strings — so without unwrapping, every such run had no identifiers and they all
    fell into one meaningless group."""
    m = re.search(r"\s-[cer]\s+([\"'])([\s\S]*)\1", cmd)
    if m:
        return m.group(2)
    return cmd.split("\n", 1)[1] if "<<" in cmd.split("\n", 1)[0] and "\n" in cmd else cmd


def throwaway(name: str, inp: dict) -> tuple[str, str] | None:
    """(kind, body) when this tool call is throwaway scripting, else None."""
    if name in SHELL_TOOLS:
        cmd = inp.get("command") or ""
        if INLINE.search(cmd):
            return "inline", body_of(cmd)
        if cmd.count("\n") + 1 >= BLOCK_LINES:
            return "block", cmd
    elif name == "Write":
        fp = inp.get("file_path") or ""
        if SCRATCH.search(fp) and fp.lower().endswith(SCRIPT_EXT):
            return "scratch", inp.get("content") or ""
    return None


def read_transcript(path: Path) -> tuple[list[dict], list[str]]:
    """Throwaway runs and the ordered shell-command heads of one transcript."""
    runs: list[dict] = []
    heads: list[str] = []
    by_id: dict[str, dict] = {}
    with path.open(encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            # Tool results carry whole files; only an error flag is wanted from them, so most
            # lines are skipped unparsed — this is what keeps 2 GB of transcripts to a minute.
            # Both spellings: transcripts are compact JSON today, and a spaced one must not
            # silently mine nothing.
            if '"tool_use"' not in line and '"is_error":true' not in line \
                    and '"is_error": true' not in line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            msg = rec.get("message")
            if not isinstance(msg, dict) or not isinstance(msg.get("content"), list):
                continue
            for b in msg["content"]:
                if not isinstance(b, dict):
                    continue
                if b.get("type") == "tool_result" and b.get("is_error"):
                    run = by_id.get(b.get("tool_use_id") or "")
                    if run:
                        run["fail"] = 1
                if b.get("type") != "tool_use":
                    continue
                name, inp = b.get("name") or "", b.get("input") or {}
                if name in SHELL_TOOLS and (h := head(inp.get("command") or "")) \
                        and h.split()[0] not in READERS:
                    heads.append(h)
                hit = throwaway(name, inp)
                if hit:
                    run = {"kind": hit[0], "body": hit[1], "shape": shape(hit[1]),
                           "tokens": len(hit[1]) // 4, "fail": 0, "file": path}
                    runs.append(run)
                    by_id[b.get("id") or ""] = run
    return runs, heads


def jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    union = len(a | b)
    return len(a & b) / union if union else 1.0


def cluster(runs: list[dict]) -> list[list[dict]]:
    """Group runs whose identifier sets overlap by SIMILAR, then merge groups by their centroids.

    A group sharing half of the union with `s` must share at least one of `s`'s rarest
    len(s)//2 + 1 words, so only groups indexed under those are compared — exact, and it turns
    a quadratic pass over ~17k runs into seconds.
    """
    # Too few identifiers to say what a run does; left in the totals, kept out of the ranking.
    runs = [r for r in runs if len(r["shape"]) >= MIN_SHAPE]
    df = Counter(w for r in runs for w in r["shape"])
    reps: list[frozenset[str]] = []
    groups: list[list[dict]] = []
    index: dict[str, list[int]] = defaultdict(list)
    for r in sorted(runs, key=lambda r: -len(r["shape"])):
        s = r["shape"]
        rare = sorted(s, key=lambda w: df[w])[:len(s) // 2 + 1]
        cands = sorted({g for w in rare for g in index[w]})
        hit = next((g for g in cands if jaccard(reps[g], s) >= SIMILAR), None)
        if hit is None:
            hit = len(groups)
            reps.append(s)
            groups.append([])
            for w in s:
                index[w].append(hit)
        groups[hit].append(r)
    # Second pass: the same habit written with different helper names lands in several groups
    # (the patch script filled a whole top 15). Their most common identifiers still match.
    merged: list[tuple[frozenset[str], list[dict]]] = []
    for members in sorted(groups, key=len, reverse=True):
        core = frozenset(w for w, _ in Counter(w for m in members for w in m["shape"]).most_common(8))
        for mcore, mm in merged:
            if len(members) > 1 and jaccard(mcore, core) >= SIMILAR:
                mm.extend(members)
                break
        else:
            merged.append((core, members))
    return [m for _, m in merged]


def sample(text: str, width: int) -> str:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("#")]
    body = " ⏎ ".join(lines[:2])
    return (body[:width] + "…") if len(body) > width else body


def project_of(path: Path, root: Path) -> str:
    return path.relative_to(root).parts[0]


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--projects-root", type=Path, default=None)
    ap.add_argument("--project", action="append", default=[], help="substring of a project folder (repeatable)")
    ap.add_argument("--since", help="YYYY-MM-DD; transcripts modified on or after it")
    ap.add_argument("--top", type=int, default=15, help="rows per table")
    ap.add_argument("--min", type=int, default=3, help="fewest transcripts a row must appear in")
    ap.add_argument("--width", type=int, default=110, help="sample width in characters")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    root = (args.projects_root or default_projects_root()).resolve()
    since = datetime.strptime(args.since, "%Y-%m-%d").timestamp() if args.since else 0
    files = [p for p in root.rglob("*.jsonl")
             if p.stat().st_mtime >= since
             and (not args.project or any(s.lower() in project_of(p, root).lower() for s in args.project))]
    if not files:
        print(f"no transcripts under {root}", file=sys.stderr)
        return 2

    runs: list[dict] = []
    grams: dict[tuple[str, ...], set[Path]] = defaultdict(set)
    gram_hits: Counter = Counter()
    for f in files:
        r, heads = read_transcript(f)
        runs.extend(r)
        for n in (2, 3, 4):
            for i in range(len(heads) - n + 1):
                g = tuple(heads[i:i + n])
                if len(set(g)) > 1:
                    grams[g].add(f)
                    gram_hits[g] += 1

    rows = []
    for members in cluster(runs):
        where = {m["file"] for m in members}
        if len(where) < args.min:
            continue
        common = Counter(w for m in members for w in m["shape"]).most_common(6)
        rows.append({"runs": len(members), "transcripts": len(where),
                     "projects": len({project_of(p, root) for p in where}),
                     "fail": sum(m["fail"] for m in members), "tokens": sum(m["tokens"] for m in members),
                     "kinds": dict(Counter(m["kind"] for m in members)),
                     "shape": [w for w, _ in common], "sample": sample(members[0]["body"], args.width)})
    rows.sort(key=lambda r: -r["tokens"])

    # A longer sequence contained in an equally frequent one is the same habit reported twice.
    seqs = [(g, len(fs), gram_hits[g]) for g, fs in grams.items() if len(fs) >= args.min]
    seqs.sort(key=lambda s: (-s[1], -len(s[0])))
    kept: list[tuple[tuple[str, ...], int, int]] = []
    for g, t, hits in seqs:
        if any(t == kt and " ".join(g) in " ".join(k) for k, kt, _ in kept):
            continue
        kept.append((g, t, hits))

    if args.json:
        print(json.dumps({"transcripts": len(files), "runs": len(runs), "scripts": rows[:args.top],
                          "sequences": [{"steps": list(g), "transcripts": t, "hits": h}
                                        for g, t, h in kept[:args.top]]}, indent=1))
        return 0

    total = sum(r["tokens"] for r in runs)
    print(f"== throwaway scripts: {len(runs)} runs in {len(files)} transcripts, ~{total:,} tokens written ==")
    print(f"{'runs':>5} {'trans':>5} {'proj':>4} {'fail':>4} {'~tokens':>8}  shape | sample")
    for r in rows[:args.top]:
        print(f"{r['runs']:>5} {r['transcripts']:>5} {r['projects']:>4} {r['fail']:>4} {r['tokens']:>8,}  "
              f"{' '.join(r['shape'])} | {r['sample']}")
    print(f"\n== repeated command sequences (in >= {args.min} transcripts) ==")
    print(f"{'trans':>5} {'hits':>5}  steps")
    for g, t, h in kept[:args.top]:
        print(f"{t:>5} {h:>5}  {' -> '.join(g)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
