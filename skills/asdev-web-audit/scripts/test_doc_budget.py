#!/usr/bin/env python3
"""Tests for doc_hygiene.over_budget, the size-budget list every compaction notice names.

They lived in hooks/test_after_compact.py until the asdev mod took over that notice (2026-10-02);
the mod's own tests cover how the notice uses this list.
"""
import os, re, shutil, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from doc_hygiene import over_budget

root = Path(tempfile.mkdtemp())
results = []


def check(name, cond):
    results.append(bool(cond))
    print(("ok   " if cond else "FAIL ") + name)


try:
    lean = root / "lean"
    (lean / ".docs").mkdir(parents=True)
    (lean / ".docs" / "task.md").write_text("x" * 100, encoding="utf-8")
    fat = root / "fat"
    (fat / ".docs").mkdir(parents=True)
    (fat / ".docs" / "task.md").write_text("x" * 40_000, encoding="utf-8")
    (fat / ".docs" / "roadmap.md").write_text("x" * 100, encoding="utf-8")

    config = root / "config"
    os.environ["CLAUDE_CONFIG_DIR"] = str(config)
    fat_found = {rel: over for rel, over, _ in over_budget(str(fat))}
    check("an oversized working file is named with its trim rule, a lean one is not",
          fat_found.get(".docs/task.md", "").startswith("39 kB of 15") and ".docs/roadmap.md" not in fat_found
          and all(how for _, _, how in over_budget(str(fat))))
    check("all files within budget: no budget note", over_budget(str(lean)) == [])

    memory = config / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(fat.resolve())) / "memory"
    memory.mkdir(parents=True)
    (memory / "MEMORY.md").write_bytes(b"- x\n" * 2500)
    mem = [over for rel, over, _ in over_budget(str(fat)) if rel.endswith("MEMORY.md")]
    check("an oversized memory index is named, a lean one is not",
          mem == ["10 kB of 6"] and not any(rel.endswith("MEMORY.md") for rel, _, _ in over_budget(str(lean))))
finally:
    shutil.rmtree(root, ignore_errors=True)

print(f"{sum(results)}/{len(results)} ok")
sys.exit(0 if all(results) else 1)
