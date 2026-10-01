#!/usr/bin/env python3
"""Generate ~/.codex/AGENTS.md from ~/.claude/CLAUDE.md. PAUSED since 2026-10-01 (see CANONICAL).

The two global instruction files must say the SAME THING. They were maintained as separate documents
"in each file's own idiom" until 2026-08-30, and the drift that invites is exactly what the mirroring
rule existed to prevent: a rule added on one side silently stops being a shared standard.

So AGENTS.md is now GENERATED. The only differences are:

  * the model names — this author's Codex profile routes to Terra / Sol where Claude Code
    routes to Opus / Fable (see SUBSTITUTIONS);
  * a generated-file header telling a reader to edit CLAUDE.md instead.

Since 2026-09-30 `~/.claude/CLAUDE.md` is a stub importing the shared rules from the setup repo,
which in turn import each person's machine bullets from `~/.claude/CLAUDE.personal.md`. Codex reads
AGENTS.md as plain text, so every whole-line `@path` import is inlined here (`expand_imports`).

    python $HOME/.claude/skills/asdev-web-audit/scripts/sync_agents_md.py          # write AGENTS.md
    python $HOME/.claude/skills/asdev-web-audit/scripts/sync_agents_md.py --check  # verify it is current (CI//gate use)

`--check` exits 1 when AGENTS.md is missing or stale, so "the mirror drifted" becomes a failure
rather than something noticed months later.
"""

from __future__ import annotations

import argparse
from collections import Counter
import difflib
import re
import sys
from pathlib import Path

SOURCE = Path.home() / ".claude" / "CLAUDE.md"
TARGET = Path.home() / ".codex" / "AGENTS.md"
PERSONAL = Path.home() / ".claude" / "CLAUDE.personal.md"
PERSONAL_EXAMPLE = Path.home() / ".claude" / "claude-agentic-setup" / "CLAUDE.personal.example.md"

# Only a line that is nothing but an import counts: an `@` in prose (an email, a package scope such
# as `@anthropic-ai`) or inside a code fence is text. Claude Code stops at five hops; so do we.
IMPORT_LINE = re.compile(r"^[ \t]*@(\S+)[ \t]*$")
FENCE = re.compile(r"^[ \t]*(```|~~~)")
MAX_IMPORT_DEPTH = 5


def _import_target(ref: str, base: Path) -> Path:
    if ref.startswith("~/"):
        return Path.home() / ref[2:]
    target = Path(ref)
    return target if target.is_absolute() else base / target


def expand_imports(path: Path, substitute: dict[Path, Path] | None = None,
                   _chain: tuple[Path, ...] = ()) -> str:
    """The text of `path` with its whole-line `@path` imports inlined, recursively.

    `substitute` maps an import target to the file read in its place: the share bundle swaps the
    personal file for the example, so one person's machine never ships to anyone else. A missing
    import fails loudly — silently dropping it would generate an AGENTS.md without those rules.
    """
    substitute = {k.resolve(): v for k, v in (substitute or {}).items()}
    real = path.resolve()
    if real in _chain:
        raise SystemExit(f"sync_agents_md: import cycle: {' -> '.join(str(p) for p in (*_chain, real))}")
    if len(_chain) > MAX_IMPORT_DEPTH:
        raise SystemExit(f"sync_agents_md: imports nest deeper than {MAX_IMPORT_DEPTH} at {path}")
    text = path.read_text(encoding="utf-8" if not _chain else "utf-8-sig")
    out, in_fence = [], False
    for line in text.split("\n"):
        if FENCE.match(line):
            in_fence = not in_fence
        match = None if in_fence else IMPORT_LINE.match(line.rstrip("\r"))
        if not match:
            out.append(line)
            continue
        target = _import_target(match.group(1), path.parent)
        target = substitute.get(target.resolve(), target)
        if not target.is_file():
            hint = (f" Copy {PERSONAL_EXAMPLE.name} from the setup repo to {PERSONAL} and fill it in."
                    if target.resolve() == PERSONAL.resolve() else "")
            raise SystemExit(f"sync_agents_md: {path} imports {match.group(1)}, which does not exist "
                             f"({target}).{hint}")
        out.append(expand_imports(target, substitute, (*_chain, real)).removesuffix("\n"))
    return "\n".join(out)

# CANONICAL is the ONE place the line mapping is written. The versioned variants, the article
# handling and the banner text are all DERIVED from it below, so editing this list cannot strand a
# hardcoded pair. It could before: eleven variants were spelled out by hand, and changing CANONICAL
# alone would have emitted two mappings at once — bare "Opus"->"Sol" beside "Opus 5 Max"->"Terra 5
# Max" — while `--check` still reported "in sync".
#
# PAUSED 2026-10-01: the owner decoupled Codex. Neither the installer nor the gate runs this file
# any more; `expand_imports` is still used by harness_parity.py and share_bundle.py. Before
# resuming, add a Codex pair for Sonnet (back since 2026-10-01 as `sonnet-medium-executor`).
#
# Anticipated: when Astra ships the aliases re-rank to track TIER rather than keeping today's
# pairings — Fable->Astra, Opus->Sol. Sol moves from Fable to Opus, so that is a re-ranking, not
# an append. Not applied yet; the list below is current.
CANONICAL = [("Opus", "Terra"), ("Fable", "Sol")]

VOWELS = "AEIOU"
# Legacy spellings. CLAUDE.md is version-free, but text that does name a version must still convert.
VERSION_SUFFIXES = (" 5 Max", " 5", "")


def _expand(canonical: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Every spelling the source might contain, ordered so the longest match wins.

    Order matters twice. "Opus 5 Max" has to be replaced before a bare "Opus" matches inside it;
    and an article-carrying form has to precede the bare name, or "an Opus review" becomes
    "an Terra review" instead of "a Terra review".
    """
    out: list[tuple[str, str]] = []
    for suffix in VERSION_SUFFIXES:
        for old, new in canonical:
            o, n = old + suffix, new + suffix
            old_vowel, new_vowel = old[0].upper() in VOWELS, new[0].upper() in VOWELS
            if old_vowel and not new_vowel:
                out += [("an " + o, "a " + n), ("An " + o, "A " + n)]
            elif new_vowel and not old_vowel:
                out += [("a " + o, "an " + n), ("A " + o, "An " + n)]
        out += [(old + suffix, new + suffix) for old, new in canonical]
    return out


SUBSTITUTIONS = _expand(CANONICAL)

HEADER = """<!-- GENERATED FILE - DO NOT EDIT DIRECTLY.

Generated from ~/.claude/CLAUDE.md and the files it imports, by
~/.claude/skills/asdev-web-audit/scripts/sync_agents_md.py. The two are deliberately identical apart
from model names ({mapping}), because a rule that exists on one side only silently stops being a
shared standard.

Edit ~/.claude/claude-agentic-setup/CLAUDE.shared.md (shared rules) or ~/.claude/CLAUDE.personal.md
(your machine), then re-run the script. `--check` reports drift.
-->

"""


def render(source_text: str) -> str:
    body = source_text
    for old, new in SUBSTITUTIONS:
        body = body.replace(old, new)
    # A many-to-one mapping is fine until BOTH collapsed tiers carry a bold role label, at which
    # point the mirror defines one name twice with different jobs ("**Luna**: legwork ... **Luna**:
    # only high-volume fan-out") and the Codex-side rule becomes unusable. `--check` cannot see this
    # — it compares the file to this same generator — so it is asserted here instead.
    collapsed = {new for new, count in Counter(n for _, n in CANONICAL).items() if count > 1}
    for alias in sorted(collapsed):
        labels = body.count(f"**{alias}**")
        if labels > 1:
            raise SystemExit(
                f"sync_agents_md: '{alias}' carries {labels} bold role labels because more than one "
                f"model maps to it. The mirror would define one tier twice with different roles. "
                f"Label only one of them, or give the other its own alias.")
    return HEADER.format(mapping=", ".join(f"{o}->{n}" for o, n in CANONICAL)) + body


def main() -> int:
    # The drift diff carries CLAUDE.md's arrows and warning signs; on cp1252 stdout it crashed
    # mid-print instead of reporting FAIL.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap =argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="exit 1 if AGENTS.md is missing or stale")
    args = ap.parse_args()

    if not SOURCE.is_file():
        print(f"FAIL: source not found: {SOURCE}")
        return 1
    expected = render(expand_imports(SOURCE))

    if args.check:
        if not TARGET.is_file():
            print(f"FAIL: {TARGET} does not exist; run this script without --check")
            return 1
        actual = TARGET.read_text(encoding="utf-8")
        if actual == expected:
            print(f"AGENTS.md is in sync with CLAUDE.md ({len(expected.splitlines())} lines)")
            return 0
        diff = list(difflib.unified_diff(actual.splitlines(), expected.splitlines(),
                                         "AGENTS.md (current)", "AGENTS.md (expected)", lineterm="", n=1))
        print(f"FAIL: AGENTS.md has drifted from CLAUDE.md ({len(diff)} diff lines). Re-run without --check.")
        for line in diff[:40]:
            print("  " + line)
        return 1

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(expected, encoding="utf-8", newline="\n")
    print(f"wrote {TARGET} ({len(expected.splitlines())} lines) from {SOURCE.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
