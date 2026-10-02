@@@ hooks/after_compact.py
name: the notice fires on every session start, not only after a compaction
expect: FAIL startup: silent
<<<<<<< OLD
    if event.get("source") != "compact":
======= NEW
    if False:
>>>>>>> END

name: docs are named whether they exist or not
expect: FAIL after a compaction: names exactly the docs present
<<<<<<< OLD
if (docs / name).is_file()]
======= NEW
if True]
>>>>>>> END

name: the notice is built but never printed
expect: FAIL after a compaction: names exactly the docs present
<<<<<<< OLD
        if text:
            print(
======= NEW
        if False:
            print(
>>>>>>> END

name: a session outside a project gets no reminder
expect: FAIL no .docs folder: general reminder
<<<<<<< OLD
    if not present:
        # Sessions
======= NEW
    if not present:
        return None
        # Sessions
>>>>>>> END
