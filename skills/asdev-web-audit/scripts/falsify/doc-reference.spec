@@@ skills/asdev-web-audit/scripts/doc_hygiene.py
name: reference files are never size-checked
expect: Lists differ: [] != ['.docs/reference/big.md']
<<<<<<< OLD
            if name.lower().endswith(".md") and kb > REFERENCE_KB and
======= NEW
            if False and
>>>>>>> END

name: the archive is no longer exempt
expect: First list contains 1 additional elements
<<<<<<< OLD
        dirnames[:] = [d for d in dirnames if d != "archive"]
======= NEW
        dirnames[:] = dirnames
>>>>>>> END
