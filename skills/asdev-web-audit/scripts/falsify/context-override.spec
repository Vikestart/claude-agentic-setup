@@@ skills/asdev-web-audit/scripts/context_override.py
name: a deliberate setting gets overridden
expect: a deliberate value must be refused
<<<<<<< OLD
        if current is not None and not ours:
======= NEW
        if False:
>>>>>>> END

name: re-setting forgets that the script created the file
expect: re-setting must not forget who made the file
<<<<<<< OLD
        created = entry["created_file"] if ours else not settings_path.is_file()
======= NEW
        created = not settings_path.is_file()
>>>>>>> END

name: clear removes a value changed by hand
expect: a hand-changed value must stay
<<<<<<< OLD
    if ours:
        del settings[KEY]
======= NEW
    if True:
        del settings[KEY]
>>>>>>> END

name: a value at the shared cap is accepted
expect: a value at the shared cap must be refused
<<<<<<< OLD
        if not floor < a.value <= MAX_VALUE:
======= NEW
        if not a.value <= MAX_VALUE:
>>>>>>> END

name: a CRLF settings file is rewritten as LF
expect: a CRLF file must stay CRLF
<<<<<<< OLD
.replace("\n", nl).encode("utf-8"))
======= NEW
.encode("utf-8"))
>>>>>>> END
