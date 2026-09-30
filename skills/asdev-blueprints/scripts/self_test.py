#!/usr/bin/env python3
"""self_test.py -- structural checks for the asdev-blueprints skill.

Run after editing any reference file, and whenever a path the local overlay cites moves:

    python scripts/self_test.py [-q] [--projects-root PATH]

Checks (exit 1 on any failure, 0 otherwise):
  1. SKILL.md has YAML frontmatter with `name` and `description`, and stays inside the line budget.
  2. Every reference file SKILL.md links exists and carries the skeleton headings (1, 2, 3, 4, 7).
  3. Every capability id in SKILL.md section 5 is defined in exactly ONE reference file's section 7,
     appears in the manifest template, and no reference defines an id SKILL.md does not list.
  4. Where the optional `local/` overlay is installed: every repository path it cites still exists.
     The shared half names no repository, so with no overlay there is nothing to verify and the check
     says so rather than passing silently.
  5. The assets the scaffold copies are present.
  6. assets/env.example.template holds no populated credential-shaped value.

Why these and not more: the skill's value is in contracts that are TRUE and pointers that resolve. A
pointer naming a file that no longer exists sends the next session on a hunt and erodes trust in every
other line. The content itself is judged by review, not by a script.
"""
from __future__ import annotations

import argparse
import glob
import re
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
REFS_DIR = SKILL_DIR / "references"
ASSETS_DIR = SKILL_DIR / "assets"

def _overlay_projects() -> tuple:
    """Repository names the local overlay cites, if an overlay is installed. Empty otherwise."""
    cfg = Path(__file__).resolve().parent.parent / "local" / "projects.json"
    if not cfg.is_file():
        return ()
    try:
        import json
        data = json.loads(cfg.read_text(encoding="utf-8"))
        return tuple(n for n in data.get("projects", []) if isinstance(n, str))
    except (OSError, ValueError):
        return ()


PROJECTS = _overlay_projects()
ID_RE = re.compile(r"`([a-z]+\.[a-z0-9-]+)`")
ROW_ID_RE = re.compile(r"^\|\s*`([a-z]+\.[a-z0-9-]+)`\s*\|", re.M)
PATH_RE = re.compile(r"`((?:%s)/[^`]+)`" % "|".join(PROJECTS)) if PROJECTS else None
LOOSE_PATH_RE = re.compile(r"`((?:[A-Za-z0-9_.\-]+/)+[A-Za-z0-9_.\-]+\.(?:php|md|js|mjs|json|sh|sql|yml|htaccess))`")
CRED_KEY_RE = re.compile(r"(KEY|SECRET|TOKEN|PASS|PASSWORD|BEARER)(_|$)")
REQUIRED_HEADINGS = ("## 1.", "## 2.", "## 3.", "## 4.", "## 7.")
OPTIONAL_HEADINGS = ("## 5.", "## 6.")
REQUIRED_ASSETS = (
    "platform-manifest.template.md",
    "AGENTS.template.md",
    "CLAUDE.template.md",
    "env.example.template",
    "htaccess-deny.snippet",
    "auditignore.template",
    "audit-baseline.template.json",
    "pre-commit.template.sh",
    "ci-workflow.template.yml",
    "docs-skeleton/roadmap.md",
    "docs-skeleton/implementation_plan.md",
    "docs-skeleton/task.md",
    "docs-skeleton/walkthrough.md",
    "docs-skeleton/changelog.md",
    "docs-skeleton/handover.md",
)
LINE_BUDGET_WARN = 400
LINE_BUDGET_FAIL = 500


class Report:
    def __init__(self, quiet: bool) -> None:
        self.quiet = quiet
        self.failures: list[str] = []
        self.warnings: list[str] = []
        self.checks = 0

    def ok(self, msg: str) -> None:
        self.checks += 1
        if not self.quiet:
            print(f"  ok    {msg}")

    def fail(self, msg: str) -> None:
        self.checks += 1
        self.failures.append(msg)
        if not self.quiet:
            print(f"  FAIL  {msg}")

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)
        if not self.quiet:
            print(f"  warn  {msg}")


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def section(text: str, heading_prefix: str) -> str:
    """Text from the first line starting with heading_prefix to the next '## ' heading (or EOF)."""
    lines = text.splitlines()
    start = next((i for i, l in enumerate(lines) if l.startswith(heading_prefix)), None)
    if start is None:
        return ""
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    return "\n".join(lines[start:end])


def check_frontmatter(rep: Report, skill_text: str) -> None:
    lines = skill_text.splitlines()
    if not lines or lines[0].strip() != "---":
        rep.fail("SKILL.md: frontmatter must start with '---' on line 1")
        return
    try:
        close = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        rep.fail("SKILL.md: frontmatter never closes")
        return
    fm = "\n".join(lines[1:close])
    for key in ("name:", "description:"):
        if re.search(rf"^{key}", fm, re.M):
            rep.ok(f"SKILL.md frontmatter has {key[:-1]}")
        else:
            rep.fail(f"SKILL.md frontmatter lacks {key[:-1]}")
    n = len(lines)
    if n > LINE_BUDGET_FAIL:
        rep.fail(f"SKILL.md is {n} lines (> {LINE_BUDGET_FAIL}); move detail into references/")
    elif n > LINE_BUDGET_WARN:
        rep.warn(f"SKILL.md is {n} lines (> {LINE_BUDGET_WARN}); consider moving detail into references/")
    else:
        rep.ok(f"SKILL.md is {n} lines")


def linked_references(skill_text: str) -> list[str]:
    names = set(re.findall(r"\]\(references/([a-z0-9-]+\.md)\)", skill_text))
    names |= set(re.findall(r"\|\s*([a-z-]+\.md)(?:\s*§\d+)?\s*\|$", skill_text, re.M))
    return sorted(names)


def check_reference_files(rep: Report, names: list[str]) -> dict[str, str]:
    texts: dict[str, str] = {}
    for name in names:
        path = REFS_DIR / name
        if not path.is_file():
            rep.fail(f"references/{name}: linked from SKILL.md but missing")
            continue
        text = read(path)
        texts[name] = text
        if name == "reference-map.md":
            rep.ok(f"references/{name} exists ({len(text.splitlines())} lines)")
            continue
        missing = [h for h in REQUIRED_HEADINGS if not re.search(rf"^{re.escape(h)}", text, re.M)]
        if missing:
            rep.fail(f"references/{name}: missing skeleton headings {missing}")
        else:
            rep.ok(f"references/{name}: skeleton headings present ({len(text.splitlines())} lines)")
        for h in OPTIONAL_HEADINGS:
            if not re.search(rf"^{re.escape(h)}", text, re.M):
                rep.warn(f"references/{name}: no '{h}' section (allowed only if genuinely empty)")
    return texts


def check_ids(rep: Report, skill_text: str, ref_texts: dict[str, str]) -> None:
    inventory = section(skill_text, "## 5.")
    skill_ids: dict[str, str] = {}
    for line in inventory.splitlines():
        m = ROW_ID_RE.match(line)
        if m:
            skill_ids[m.group(1)] = line
    if not skill_ids:
        rep.fail("SKILL.md section 5: no capability ids found (rows must start with | `area.name` |)")
        return
    rep.ok(f"SKILL.md section 5 lists {len(skill_ids)} capability ids")

    manifest = read(ASSETS_DIR / "platform-manifest.template.md") if (ASSETS_DIR / "platform-manifest.template.md").is_file() else ""
    manifest_ids = set(ROW_ID_RE.findall(manifest))

    # Only tokens whose area prefix SKILL.md declares count as ids: `robots.txt` or `sw.js` in a
    # section-7 row must not read as an undeclared capability.
    areas = {cid.split(".", 1)[0] for cid in skill_ids}
    defined_in: dict[str, list[str]] = {}
    for name, text in ref_texts.items():
        if name == "reference-map.md":
            continue
        # A definition is a section-7 table ROW that starts with the id; a mention of another
        # capability inside a cell ("sends through `mail.transport`") is a cross-reference.
        for cid in set(ROW_ID_RE.findall(section(text, "## 7."))):
            if cid.split(".", 1)[0] in areas:
                defined_in.setdefault(cid, []).append(name)

    # The port-from map lives in the optional `local/` overlay: it names one team's repositories, so
    # it is not shared. Its coverage is checked only when the overlay is installed — a shared copy of
    # the skill has no map, and every id must still be defined by a reference §7 regardless.
    map_path = SKILL_DIR / "local" / "reference-map.md"
    map_text = read(map_path) if map_path.is_file() else ""
    map_rows = set(ROW_ID_RE.findall(map_text))
    for cid, row in skill_ids.items():
        pattern_only = "pattern only" in row or "local overlay" in row
        homes = defined_in.get(cid, [])
        if map_text and cid not in map_rows:
            rep.fail(f"{cid}: no row in local/reference-map.md")
        if pattern_only:
            if not map_text:
                rep.ok(f"{cid}: pattern-only id (overlay absent, nothing to check)")
            elif cid in map_text or homes:
                rep.ok(f"{cid}: pattern-only id present in local/reference-map.md")
            else:
                rep.fail(f"{cid}: marked pattern-only but absent from local/reference-map.md")
        elif len(homes) == 1:
            rep.ok(f"{cid}: defined in {homes[0]} section 7")
        elif not homes:
            rep.fail(f"{cid}: not defined in any reference section 7")
        else:
            rep.fail(f"{cid}: defined in more than one reference section 7: {homes}")
        if cid not in manifest_ids:
            rep.fail(f"{cid}: missing from assets/platform-manifest.template.md")

    for cid, homes in defined_in.items():
        if cid not in skill_ids:
            rep.fail(f"{cid}: defined in {homes} section 7 but not listed in SKILL.md section 5")
    for cid in manifest_ids - set(skill_ids):
        rep.fail(f"{cid}: in the manifest template but not listed in SKILL.md section 5")


def normalise_path(raw: str) -> str | None:
    p = raw.strip()
    if any(ch in p for ch in "<>{}") or "…" in p:
        return None
    p = re.split(r"::|#", p)[0]
    p = re.sub(r":\d+(-\d+)?$", "", p)
    p = p.rstrip(".,;:)")
    return p or None


def check_paths(rep: Report, root: Path, skill_text: str, ref_texts: dict[str, str]) -> None:
    """Repository paths are cited only by the optional `local/` overlay, so this checks that.

    The shared half deliberately names no repository: its contracts say what to build and why. When
    no overlay is installed there is nothing to verify here, and saying so is the honest result.
    """
    overlay = SKILL_DIR / "local"
    if not overlay.is_dir():
        rep.ok("no local/ overlay installed; no repository paths to verify")
        return
    if not root.is_dir():
        rep.warn(f"projects root {root} not found; overlay path checks skipped (inconclusive)")
        return
    if PATH_RE is None:
        rep.ok("overlay installed but names no repositories (local/projects.json); nothing to verify")
        return
    sources = {f"local/{p.relative_to(overlay).as_posix()}": read(p)
               for p in sorted(overlay.rglob("*.md")) if p.is_file()}
    sources["SKILL.md"] = skill_text
    sources.update({f"references/{k}": v for k, v in ref_texts.items()})
    seen: dict[str, str] = {}
    missing = 0
    for src, text in sources.items():
        for lineno, line in enumerate(text.splitlines(), 1):
            for raw in PATH_RE.findall(line):
                p = normalise_path(raw)
                if p is None or p in seen:
                    continue
                seen[p] = f"{src}:{lineno}"
                target = root / p
                if "*" in p:
                    found = bool(glob.glob(str(target)))
                else:
                    found = target.exists()
                if not found:
                    missing += 1
                    rep.fail(f"path not found: {p}  (cited at {seen[p]})")
    rep.ok(f"{len(seen) - missing}/{len(seen)} cited project paths exist under {root}")

    # Unprefixed citations (`api/lib/Foo.php`, `includes/bar.php`) are resolved against every project
    # root; a miss is a WARNING, not a failure, because a path cited relative to a subdirectory
    # (core/admin/lang/en.php written as `lang/en.php`) is legitimate prose. They are never skipped
    # silently: the count is printed so a reviewer can see what the strict check did not cover.
    loose_seen: dict[str, str] = {}
    loose_missing: list[str] = []
    for src, text in sources.items():
        for lineno, line in enumerate(text.splitlines(), 1):
            for raw in LOOSE_PATH_RE.findall(line):
                p = normalise_path(raw)
                if p is None or p in seen or p in loose_seen or p.split("/", 1)[0] in PROJECTS:
                    continue
                if p.startswith((".docs/", "assets/", "references/", "local/", "scripts/", "asdev-conventions/", "asdev-web-audit/")):
                    continue  # skill-internal or per-project template paths, not pointers into a project
                loose_seen[p] = f"{src}:{lineno}"
                if not any((root / proj / p).exists() for proj in PROJECTS):
                    loose_missing.append(f"{p} ({loose_seen[p]})")
    for m in loose_missing:
        rep.warn(f"unprefixed path not found under any project root: {m}")
    rep.ok(f"{len(loose_seen) - len(loose_missing)}/{len(loose_seen)} unprefixed cited paths resolve under some project root (misses are warnings)")


def check_assets(rep: Report) -> None:
    for rel in REQUIRED_ASSETS:
        if (ASSETS_DIR / rel).is_file():
            rep.ok(f"assets/{rel}")
        else:
            rep.fail(f"assets/{rel} missing")


def check_env_template(rep: Report) -> None:
    path = ASSETS_DIR / "env.example.template"
    if not path.is_file():
        return
    populated = []
    for lineno, line in enumerate(read(path).splitlines(), 1):
        if not line or line.lstrip().startswith("#") or "=" not in line:
            continue
        key, _, rest = line.partition("=")
        value = rest.split("#", 1)[0].strip()
        if CRED_KEY_RE.search(key.strip()) and value:
            populated.append(f"{key.strip()} (line {lineno})")
    if populated:
        rep.fail("env.example.template has populated credential-shaped keys: " + ", ".join(populated))
    else:
        rep.ok("env.example.template: every credential-shaped key is blank")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--projects-root", default=None,
                    help="root holding the repositories the local overlay cites "
                         "(defaults to local/projects.json's projects_root)")
    ap.add_argument("-q", "--quiet", action="store_true", help="print only the summary")
    args = ap.parse_args()

    if args.projects_root is None:
        cfg = SKILL_DIR / "local" / "projects.json"
        if cfg.is_file():
            try:
                import json
                args.projects_root = json.loads(cfg.read_text(encoding="utf-8")).get("projects_root")
            except (OSError, ValueError):
                args.projects_root = None
    args.projects_root = args.projects_root or ""

    rep = Report(args.quiet)
    skill_path = SKILL_DIR / "SKILL.md"
    if not skill_path.is_file():
        print(f"FAIL: {skill_path} missing")
        return 1
    skill_text = read(skill_path)

    check_frontmatter(rep, skill_text)
    ref_texts = check_reference_files(rep, linked_references(skill_text))
    check_ids(rep, skill_text, ref_texts)
    check_paths(rep, Path(args.projects_root), skill_text, ref_texts)
    check_assets(rep)
    check_env_template(rep)

    status = "GREEN" if not rep.failures else "RED"
    print(f"asdev-blueprints self_test: {status} - {rep.checks} checks, {len(rep.failures)} failures, {len(rep.warnings)} warnings")
    if args.quiet and rep.failures:
        for f in rep.failures:
            print(f"  FAIL  {f}")
    return 1 if rep.failures else 0


if __name__ == "__main__":
    sys.exit(main())
