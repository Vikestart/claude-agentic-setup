# Python fixture header. <start:block:Python fixture header>
import os
LIMIT = 3  # <end:block:Python fixture header>


class Outer:  # <start:class:Outer>
    """Docstring with def fake(): and class Fake: inside."""

    def method(self):  # <start:method:Outer.method>
        text = """
def not_a_function():
    pass
"""
        return text  # <end:method:Outer.method>

    class Inner:  # <start:class:Outer.Inner>
        def deep(self):  # <start:method:Outer.Inner.deep>
            return {
                "k": "}",
            }  # <end:method:Outer.Inner.deep> <end:class:Outer.Inner> <end:class:Outer>


def multi_line_signature(  # <start:function:multi_line_signature>
    a,
    b,
):
    def nested(x):  # <start:function:nested>
        return x  # <end:function:nested>
    return nested(a) + b  # <end:function:multi_line_signature>
# a column-0 comment after a function is not part of it


def after():  # <start:function:after>
    return os.sep  # <end:function:after>


# ---- Python banner ---- <start:banner:Python banner>
# Block paragraph in Python. <start:block:Block paragraph in Python>
value = after()
print(value, LIMIT)  # <end:block:Block paragraph in Python> <end:banner:Python banner>
