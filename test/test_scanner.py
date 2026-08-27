import pytest

from comment_deleter.languages import spec_for_path
from comment_deleter.scanner import find_comments


def comment_texts(source: str, filename: str) -> list[str]:
    spec = spec_for_path(filename)
    assert spec is not None
    return [span.text for span in find_comments(source, spec)]


def test_python_finds_line_and_trailing_comments():
    source = "# header\nvalue = 1  # trailing\n"
    assert comment_texts(source, "a.py") == ["# header", "# trailing"]


def test_python_ignores_hash_inside_strings():
    source = 'url = "https://x/#frag"\ntext = """\n# not a comment\n"""\n'
    assert comment_texts(source, "a.py") == []


def test_python_falls_back_when_file_does_not_tokenize():
    source = "def broken(:\n    pass  # still a comment\n"
    assert comment_texts(source, "a.py") == ["# still a comment"]


def test_c_block_and_line_comments():
    source = "int x = 1; /* block */\n// line\n"
    assert comment_texts(source, "a.c") == ["/* block */", "// line"]


def test_c_ignores_comment_markers_inside_strings():
    source = 'const char *s = "// not a comment";\n'
    assert comment_texts(source, "a.c") == []


def test_c_char_literal_does_not_swallow_the_line():
    source = "char c = '/'; // real\n"
    assert comment_texts(source, "a.c") == ["// real"]


def test_rust_lifetime_does_not_open_a_string():
    source = "fn f<'a>(x: &'a str) {} // note\n"
    assert comment_texts(source, "a.rs") == ["// note"]


def test_rust_nested_block_comments():
    source = "/* outer /* inner */ still */\nlet x = 1;\n"
    assert comment_texts(source, "a.rs") == ["/* outer /* inner */ still */"]


def test_javascript_regex_literal_is_not_a_comment():
    source = "const re = /a\\/\\/b/g;\nconst other = /[/]/;\n"
    assert comment_texts(source, "a.js") == []


def test_javascript_division_is_not_a_regex():
    source = "const ratio = total / count; // note\n"
    assert comment_texts(source, "a.js") == ["// note"]


def test_javascript_template_literal_hides_markers():
    source = "const t = `a // b ${x} /* c */`;\n// real\n"
    assert comment_texts(source, "a.ts") == ["// real"]


def test_shell_heredoc_body_is_not_scanned():
    source = "cat <<'EOF'\n# not a comment\nEOF\n# real\n"
    assert comment_texts(source, "a.sh") == ["# real"]


def test_shell_hash_needs_a_word_boundary():
    source = 'echo a#b\necho "${#items[@]}"\n# real\n'
    assert comment_texts(source, "a.sh") == ["# real"]


def test_yaml_inline_comment_requires_space():
    source = "key: value#notcomment\nother: 1  # real\n"
    assert comment_texts(source, "a.yaml") == ["# real"]


def test_html_comments():
    source = "<div></div>\n<!-- note -->\n"
    assert comment_texts(source, "a.html") == ["<!-- note -->"]


def test_sql_and_lua_dash_comments():
    assert comment_texts("SELECT 1; -- note\n", "a.sql") == ["-- note"]
    assert comment_texts("local x = 1 -- note\n", "a.lua") == ["-- note"]


@pytest.mark.parametrize("filename", ["README.md", "data.json", "notes.txt", "nb.ipynb"])
def test_prose_and_data_files_have_no_spec(filename):
    assert spec_for_path(filename) is None


def test_nested_template_literal_hides_a_url():
    source = "const t = `Changelog: ${link(`https://example.com/v${tag}`)}`;\n// real\n"
    assert comment_texts(source, "a.js") == ["// real"]


def test_template_substitution_with_object_literal():
    source = "const t = `${fn({ a: 1 })} // not a comment`;\nlet x = 1; // real\n"
    assert comment_texts(source, "a.js") == ["// real"]


def test_deeply_nested_templates_terminate():
    source = "const t = `${`${`${`https://a`}`}`}`;\n// real\n"
    assert comment_texts(source, "a.js") == ["// real"]
