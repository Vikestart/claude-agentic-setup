name: gemini runs in the repo itself instead of a worktree
expect: FAIL a review never sees .env
@@@ skills/asdev-web-audit/scripts/gemini.py
<<<<<<< OLD
            cwd=wt, capture_output=True, text=True, encoding="utf-8", errors="replace")
======= NEW
            cwd=repo, capture_output=True, text=True, encoding="utf-8", errors="replace")
>>>>>>> END

name: no committed-secret check
expect: FAIL a committed .env stops the run
@@@ skills/asdev-web-audit/scripts/gemini.py
<<<<<<< OLD
    secrets = [f for f in files if SECRET.search(f) or (PEM.search(f) and not public_pem(repo, a.rev, f))]
======= NEW
    secrets = []
>>>>>>> END

name: newest model picked by string order
expect: FAIL a review runs in plan mode on the newest model
@@@ skills/asdev-web-audit/scripts/gemini.py
<<<<<<< OLD
    return max(ids, key=ver) if ids else None
======= NEW
    return max(ids) if ids else None
>>>>>>> END

name: an empty answer counts as agy's SUCCESS
expect: FAIL an empty answer after a refused command fails
@@@ skills/asdev-web-audit/scripts/gemini.py
<<<<<<< OLD
    status = res.get("status", "?") if report else "FAILED (no answer)"
======= NEW
    status = res.get("status", "?")
>>>>>>> END

name: every committed .pem counts as public
expect: FAIL a committed .pem with a private key stops the run
@@@ skills/asdev-web-audit/scripts/gemini.py
<<<<<<< OLD
    return bool(blocks) and set(blocks) <= PUBLIC_BLOCKS and "PRIVATE" not in text.upper()
======= NEW
    return True
>>>>>>> END

name: a .pem is judged by its working-tree copy, not the commit
expect: FAIL a committed .pem with a private key stops the run
@@@ skills/asdev-web-audit/scripts/gemini.py
<<<<<<< OLD
    text = subprocess.run(["git", "show", f"{rev}:{path}"], cwd=repo, capture_output=True).stdout.decode("utf-8", "replace")
======= NEW
    text = (repo / path).read_text(encoding="utf-8", errors="replace")
>>>>>>> END
