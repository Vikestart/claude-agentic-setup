@@@ skills/asdev-web-audit/scripts/doc_hygiene.py
name: no file is ever over its size budget
expect: FAIL an oversized working file is named with its trim rule
<<<<<<< OLD
        if rel in BUDGET_KB and kb > BUDGET_KB[rel]:
======= NEW
        if False:
>>>>>>> END

name: every file counts as over budget
expect: FAIL all files within budget: no budget note
<<<<<<< OLD
        if rel in BUDGET_KB and kb > BUDGET_KB[rel]:
======= NEW
        if rel in BUDGET_KB:
>>>>>>> END

@@@ skills/asdev-web-audit/scripts/doc_hygiene.py
name: the memory index is never checked
expect: FAIL an oversized memory index is named, a lean one is not
<<<<<<< OLD
    if memory and os.path.getsize(memory) / 1024.0 > MEMORY_KB:
======= NEW
    if False:
>>>>>>> END
