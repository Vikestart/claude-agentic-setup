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

@@@ hooks/after_compact.py
name: the hook stops naming oversized files
expect: FAIL an oversized working file is named with its trim rule
<<<<<<< OLD
            + budget_note(event["cwd"]))
======= NEW
            + "")
>>>>>>> END
