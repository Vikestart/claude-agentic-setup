@@@ install/verify.py
name: a test file is listed, not found
expect: FAIL: test_every_test_file_runs
<<<<<<< OLD
    suites = sorted([*AUDIT.glob("test_*.py"), *(HOME / "hooks").glob("test_*.py")])
======= NEW
    suites = [AUDIT / "test_doc_budget.py"]
>>>>>>> END

name: a falsify spec is listed instead of found
expect: FAIL: test_every_falsify_spec_is_checked
<<<<<<< OLD
    specs = sorted(p for p in (AUDIT / "falsify").glob("*") if p.suffix in (".spec", ".json"))
======= NEW
    specs = [AUDIT / "falsify" / "verify.spec"]
>>>>>>> END

name: exit 0 without its summary passes
expect: FAIL: test_exit_zero_without_its_summary
<<<<<<< OLD
    return (lines[-1] if lines else "(no output)"), not pattern
======= NEW
    return (lines[-1] if lines else "(no output)"), True
>>>>>>> END
