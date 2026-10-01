@@@ skills/asdev-web-audit/scripts/code_map.py
name: PHP single-quoted strings are not skipped
expect: FAIL php range function brace_in_string
<<<<<<< OLD
                e, kind = _close(_SQ, text, s + 1), "s"
======= NEW
                e, kind = s + 1, "s"
>>>>>>> END

name: PHP line comments are not skipped
expect: FAIL php range function brace_in_comment
<<<<<<< OLD
                e, kind = (q if q >= 0 else e), "c"
======= NEW
                e, kind = s + 1, "c"
>>>>>>> END

name: PHP heredoc and nowdoc are read as code
expect: FAIL php range function brace_in_heredoc
<<<<<<< OLD
                if not h:
======= NEW
                if True:
>>>>>>> END

name: JS template interpolation is not tracked
expect: FAIL js range function template_nesting
<<<<<<< OLD
    stack.append("t")
======= NEW
    pass
>>>>>>> END

name: JS regex literals are read as code
expect: FAIL js range function regex_braces
<<<<<<< OLD
            e = _regex_end(text, s) if _regex_allowed(text, s) else None
======= NEW
            e = None
>>>>>>> END

name: Python nested names lose their class
expect: FAIL py range method Outer.Inner.deep
<<<<<<< OLD
            it.name = f"{p.name}.{it.name}"
======= NEW
            pass
>>>>>>> END

name: a comment inside a top-level brace starts a block
expect: FAIL php spurious block a column-0 comment inside a brace
<<<<<<< OLD
        return top_depth[i] == 0 and not in_item[i + 1]
======= NEW
        return not in_item[i + 1]
>>>>>>> END

name: banners are never recorded
expect: FAIL php range banner Test section
<<<<<<< OLD
                    banners.append((start, lab))
======= NEW
                    pass
>>>>>>> END

name: comment paragraphs never start a block
expect: FAIL php range block First test paragraph
<<<<<<< OLD
        if top(j) and state[j] != "c":
======= NEW
        if False:
>>>>>>> END

@@@ skills/asdev-web-audit/scripts/code_show.py
name: @LINE picks the outermost item
expect: FAIL show @LINE picks the innermost item
<<<<<<< OLD
        return [min(hits, key=lambda it: (it.size, -it.depth))] if hits else []
======= NEW
        return [max(hits, key=lambda it: (it.size, -it.depth))] if hits else []
>>>>>>> END

name: an unknown target suggests nothing
expect: FAIL show unknown target lists close names
<<<<<<< OLD
    close = difflib.get_close_matches(target.lower(), list(pool), n=SUGGEST, cutoff=0.0)
======= NEW
    close = []
>>>>>>> END

@@@ skills/asdev-web-audit/scripts/code_map.py
name: md: fenced code is read as headings and items
expect: FAIL md spurious
<<<<<<< OLD
        if fence:
            continue
        h = MD_HEADING.match(ln)
======= NEW
        h = MD_HEADING.match(ln)
>>>>>>> END

name: md: a section ends at the next heading of any level
expect: FAIL md range section Steps
<<<<<<< OLD
        end = next((m[3] - 1 for m in marks[n + 1:] if m[1] <= level), len(lines))
======= NEW
        end = next((m[3] - 1 for m in marks[n + 1:]), len(lines))
>>>>>>> END

name: md: closing hashes stay in a heading's name
expect: FAIL md range section Sub step
<<<<<<< OLD
        name = re.sub(r"[ 	]+#+$", "", re.sub(r"<!--.*?-->", "", title).strip()) or "(untitled)"
======= NEW
        name = re.sub(r"<!--.*?-->", "", title).strip() or "(untitled)"
>>>>>>> END

name: md: trailing blank lines stay in a range
expect: FAIL md range section Goal
<<<<<<< OLD
        while end > start and not lines[end - 1].strip():
            end -= 1
======= NEW
>>>>>>> END
