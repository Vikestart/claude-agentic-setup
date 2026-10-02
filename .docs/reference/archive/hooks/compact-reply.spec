@@@ hooks/after_compact.py
name: the last reply is never added
expect: FAIL last reply: every text block of the last message, in order
<<<<<<< OLD
            text = with_reply(text, event)
======= NEW
            pass
>>>>>>> END

name: a subagent's text counts as the session's reply
expect: FAIL last reply: an earlier message and a subagent's text are left out
<<<<<<< OLD
            if rec.get("type") != "assistant" or rec.get("isSidechain"):
======= NEW
            if rec.get("type") != "assistant":
>>>>>>> END

name: text from earlier messages piles up into the reply
expect: FAIL last reply: an earlier message and a subagent's text are left out
<<<<<<< OLD
                reply_id, texts = msg.get("id"), []
======= NEW
                reply_id = msg.get("id")
>>>>>>> END

name: only the tail is read, so an early reply is lost
expect: FAIL last reply beyond the tail window: found by the full read
<<<<<<< OLD
    for start in (max(0, size - TAIL_BYTES), 0):
======= NEW
    for start in (max(0, size - TAIL_BYTES),):
>>>>>>> END

name: a long reply is restored uncut
expect: FAIL a reply over the cap is cut and says so
<<<<<<< OLD
        reply = reply[:REPLY_CAP] + f"
======= NEW
        reply = reply + f"
>>>>>>> END

name: mid-turn narration is restored as if it were the reply
expect: FAIL last reply: narration in an unfinished turn is not the reply
<<<<<<< OLD
            if msg.get("stop_reason") != "end_turn":
======= NEW
            if False:
>>>>>>> END
