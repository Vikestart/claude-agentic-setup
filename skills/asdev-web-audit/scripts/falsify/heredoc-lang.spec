@@@ skills/asdev-web-audit/scripts/a11y_audit.py
name: a PHP heredoc opener is read as an html tag again
expect: Lists differ: [6] != [2, 6]
<<<<<<< OLD
HTML_TAG = re.compile(r"(?<!<)<html\b
======= NEW
HTML_TAG = re.compile(r"<html\b
>>>>>>> END
