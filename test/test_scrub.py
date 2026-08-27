from comment_deleter.config import Config
from comment_deleter.scrub import scrub_text


def scrub(old: str, new: str, filename: str = "a.py", **overrides) -> str:
    config = Config(**overrides)
    result, _ = scrub_text(old, new, filename, config)
    return result


def removed_count(old: str, new: str, filename: str = "a.py") -> int:
    _, count = scrub_text(old, new, filename, Config())
    return count


def test_newly_written_comment_is_deleted():
    old = "value = 1\n"
    new = "# explain the value\nvalue = 1\n"
    assert scrub(old, new) == "value = 1\n"


def test_untouched_comment_survives():
    old = "# original note\nvalue = 1\n"
    new = "# original note\nvalue = 1\nother = 2\n"
    assert scrub(old, new) == old + "other = 2\n"


def test_edited_comment_is_deleted():
    old = "# original note\nvalue = 1\n"
    new = "# original note, now reworded\nvalue = 1\n"
    assert scrub(old, new) == "value = 1\n"


def test_comment_survives_when_only_its_code_line_changes():
    old = "value = 1  # keeps the answer\n"
    new = "value = 42  # keeps the answer\n"
    assert scrub(old, new) == new


def test_comment_survives_when_it_is_only_moved():
    old = "# note\nvalue = 1\n"
    new = "value = 1\n# note\n"
    assert scrub(old, new) == new


def test_trailing_comment_removal_strips_separating_whitespace():
    old = "value = 1\n"
    new = "value = 1  # added by claude\n"
    assert scrub(old, new) == "value = 1\n"


def test_standalone_comment_removal_takes_the_whole_line_including_indent():
    old = "def f():\n    return 1\n"
    new = "def f():\n    # compute the result\n    return 1\n"
    assert scrub(old, new) == old


def test_multiline_block_comment_is_removed_entirely():
    old = "int main() { return 0; }\n"
    new = "/*\n * Entry point.\n */\nint main() { return 0; }\n"
    assert scrub(old, new, "a.c") == old


def test_block_comment_touched_on_one_line_is_removed_whole():
    old = "/*\n * Original text.\n */\nint x;\n"
    new = "/*\n * Original text.\n * Added line.\n */\nint x;\n"
    assert scrub(old, new, "a.c") == "int x;\n"


def test_inline_block_comment_keeps_surrounding_code():
    old = "f(bar);\n"
    new = "f(/* the bar */ bar);\n"
    assert scrub(old, new, "a.c") == "f(bar);\n"


def test_directives_are_preserved_by_default():
    old = "value = 1\n"
    new = "value = 1  # type: ignore[assignment]\nother = call()  # noqa: E501\n"
    assert scrub(old, new) == new


def test_directives_are_deleted_when_preservation_is_off():
    old = "value = 1\n"
    new = "value = 1  # noqa: E501\n"
    assert scrub(old, new, preserve_directives=False) == "value = 1\n"


def test_shebang_and_license_header_survive_a_new_file():
    new = "#!/usr/bin/env python3\n# SPDX-License-Identifier: MIT\n# helper module\nvalue = 1\n"
    expected = "#!/usr/bin/env python3\n# SPDX-License-Identifier: MIT\nvalue = 1\n"
    assert scrub("", new) == expected


def test_go_build_directive_survives():
    new = "//go:build linux\n\n// package docs\npackage main\n"
    assert scrub("", new, "a.go") == "//go:build linux\n\npackage main\n"


def test_explicit_keep_marker_survives():
    old = "value = 1\n"
    new = "# comment-deleter: keep this rationale\nvalue = 1\n"
    assert scrub(old, new) == new


def test_extra_preserve_patterns_from_config():
    import re

    old = "value = 1\n"
    new = "# TODO(afeeney): revisit\n# ordinary note\nvalue = 1\n"
    result = scrub(old, new, preserve_patterns=(re.compile(r"TODO\("),))
    assert result == "# TODO(afeeney): revisit\nvalue = 1\n"


def test_duplicate_comment_text_only_loses_the_new_copy():
    old = "# note\nvalue = 1\n"
    new = "# note\nvalue = 1\n# note\nother = 2\n"
    assert scrub(old, new) == old + "other = 2\n"


def test_python_safety_check_rejects_a_scrub_that_breaks_a_valid_file():
    from comment_deleter.scrub import _python_still_parses

    assert _python_still_parses("value = 1\n", "value = 1\n")
    assert not _python_still_parses("if flag:\n    pass\n", "if flag:\n")


def test_python_safety_check_allows_an_already_broken_file():
    from comment_deleter.scrub import _python_still_parses

    assert _python_still_parses("def f(:\n", "def f(:\n")


def test_absolute_excluded_paths_are_untouched():
    old = "value = 1\n"
    new = "# added\nvalue = 1\n"
    assert scrub(old, new, "/home/me/proj/.venv/lib/a.py") == new


def test_never_empties_a_file():
    new = "# just a comment\n"
    assert scrub("", new) == new


def test_excluded_paths_are_untouched():
    old = "value = 1\n"
    new = "# added\nvalue = 1\n"
    assert scrub(old, new, "node_modules/pkg/a.py") == new


def test_unknown_extension_is_untouched():
    old = "value = 1\n"
    new = "# added\nvalue = 1\n"
    assert scrub(old, new, "a.unknownext") == new


def test_counts_only_deleted_comments():
    old = "value = 1\n"
    new = "# one\n# two\nvalue = 1  # three\n"
    assert removed_count(old, new) == 3


def test_crlf_line_endings_are_preserved():
    old = "value = 1\r\n"
    new = "# added\r\nvalue = 1  # trailing\r\nother = 2\r\n"
    assert scrub(old, new) == "value = 1\r\nother = 2\r\n"
