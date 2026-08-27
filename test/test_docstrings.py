from comment_deleter.config import Config
from comment_deleter.scrub import scrub_text


def scrub(old: str, new: str, filename: str = "a.py", **overrides) -> str:
    result, _ = scrub_text(old, new, filename, Config(**overrides))
    return result


def test_function_docstring_is_deleted():
    new = 'def solve(field):\n    """Solve the field."""\n    return field\n'
    assert scrub("", new) == "def solve(field):\n    return field\n"


def test_module_docstring_is_deleted():
    new = '"""Helper utilities."""\n\nvalue = 1\n'
    assert scrub("", new) == "\nvalue = 1\n"


def test_multiline_docstring_is_deleted():
    new = (
        "def solve(field):\n"
        '    """Solve the field.\n\n'
        "    Args:\n"
        "        field: the input.\n"
        '    """\n'
        "    return field\n"
    )
    assert scrub("", new) == "def solve(field):\n    return field\n"


def test_class_docstring_only_body_becomes_pass():
    new = 'class Failure(Exception):\n    """Raised when it fails."""\n'
    assert scrub("", new) == "class Failure(Exception):\n    pass\n"


def test_function_docstring_only_body_becomes_pass():
    new = 'def stub():\n    """Not implemented."""\n'
    assert scrub("", new) == "def stub():\n    pass\n"


def test_single_line_def_with_docstring_stays_valid():
    new = 'def stub(): """Not implemented."""\n'
    assert scrub("", new) == "def stub(): pass\n"


def test_stray_bare_string_statement_is_deleted():
    new = 'value = 1\n"""a note masquerading as a comment"""\nother = 2\n'
    assert scrub("", new) == "value = 1\nother = 2\n"


def test_assigned_string_is_untouched():
    new = 'DOC = """Not a docstring, it is a value."""\n'
    assert scrub("", new) == new


def test_returned_string_is_untouched():
    new = 'def describe():\n    return """A returned value."""\n'
    assert scrub("", new) == new


def test_string_passed_to_a_call_is_untouched():
    new = 'parser.add_argument("--flag", help="""Some help.""")\n'
    assert scrub("", new) == new


def test_untouched_docstring_survives_an_edit_elsewhere():
    old = 'def solve(field):\n    """Original docs."""\n    return field\n'
    new = 'def solve(field):\n    """Original docs."""\n    return field * 2\n'
    assert scrub(old, new) == new


def test_reworded_docstring_is_deleted():
    old = 'def solve(field):\n    """Original docs."""\n    return field\n'
    new = 'def solve(field):\n    """Original docs, now expanded at length."""\n    return field\n'
    assert scrub(old, new) == "def solve(field):\n    return field\n"


def test_doctests_are_preserved():
    new = 'def add(a, b):\n    """\n    >>> add(1, 2)\n    3\n    """\n    return a + b\n'
    assert scrub("", new) == new


def test_doctests_are_deleted_when_directive_preservation_is_off():
    new = 'def add(a, b):\n    """\n    >>> add(1, 2)\n    3\n    """\n    return a + b\n'
    assert scrub("", new, preserve_directives=False) == "def add(a, b):\n    return a + b\n"


def test_file_that_reads_dunder_doc_keeps_its_docstrings():
    new = '"""My CLI tool."""\nimport argparse\n\nargparse.ArgumentParser(description=__doc__)\n'
    assert scrub("", new) == new


def test_keep_marker_preserves_a_docstring():
    new = 'def solve(field):\n    """comment-deleter: keep this contract."""\n    return field\n'
    assert scrub("", new) == new


def test_docstring_stripping_can_be_disabled():
    new = 'def solve(field):\n    """Solve the field."""\n    return field\n'
    assert scrub("", new, strip_docstrings=False) == new


def test_non_python_files_are_unaffected_by_docstring_logic():
    new = 'function f() {\n  "use strict";\n  return 1;\n}\n'
    assert scrub("", new, "a.js") == new


def test_docstring_and_comment_on_the_same_line():
    new = 'def solve():\n    """Docs."""  # and a comment\n    return 1\n'
    assert scrub("", new) == "def solve():\n    return 1\n"


def test_unicode_before_a_docstring_keeps_offsets_correct():
    new = 'def solve():\n    label = "éééé"\n    """Docs."""\n    return label\n'
    assert scrub("", new) == 'def solve():\n    label = "éééé"\n    return label\n'


def test_raw_and_prefixed_docstrings_are_deleted():
    new = 'def solve():\n    r"""Raw \\nu docs."""\n    return 1\n'
    assert scrub("", new) == "def solve():\n    return 1\n"


def test_fstring_statement_is_left_alone():
    new = 'def solve(x):\n    f"""value is {x}"""\n    return x\n'
    assert scrub("", new) == new


def test_except_handler_with_only_a_string_becomes_pass():
    new = 'try:\n    run()\nexcept ValueError:\n    """Ignore it."""\n'
    assert scrub("", new) == "try:\n    run()\nexcept ValueError:\n    pass\n"


def test_if_block_with_only_a_string_becomes_pass():
    new = 'if flag:\n    """Nothing to do."""\nelse:\n    run()\n'
    assert scrub("", new) == "if flag:\n    pass\nelse:\n    run()\n"


def test_nested_function_docstrings_are_all_deleted():
    new = (
        'def outer():\n    """Outer docs."""\n\n'
        '    def inner():\n        """Inner docs."""\n        return 1\n\n'
        "    return inner\n"
    )
    assert scrub("", new) == "def outer():\n\n    def inner():\n        return 1\n\n    return inner\n"


def test_bytes_statement_is_left_alone():
    new = 'def solve():\n    b"""not a docstring"""\n    return 1\n'
    assert scrub("", new) == new


def test_docstring_only_module_is_left_alone_by_the_empty_file_guard():
    new = '"""Only a docstring."""\n'
    assert scrub("", new) == new
