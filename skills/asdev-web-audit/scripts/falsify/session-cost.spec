@@@ skills/asdev-web-audit/scripts/session_cost.py
name: truncated output is taken at face value again
expect: AssertionError: False is not true
<<<<<<< OLD
    m["estimated"] = m["output"] < 5 * visible_tokens
======= NEW
    m["estimated"] = False
>>>>>>> END

name: complete output is overwritten by the estimate
expect: AssertionError: True is not false
<<<<<<< OLD
    m["estimated"] = m["output"] < 5 * visible_tokens
======= NEW
    m["estimated"] = True
>>>>>>> END
