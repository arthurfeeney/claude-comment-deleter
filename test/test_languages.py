import pytest

from comment_deleter.config import Config
from comment_deleter.languages import spec_for_path
from comment_deleter.scrub import scrub_text

# filename -> (what Claude wrote, what must land on disk)
# Every fixture pairs a deletable comment with a comment marker hidden inside a
# string, so a scanner that ignores string context fails loudly.
FIXTURES: dict[str, tuple[str, str]] = {
    "a.py": (
        '# note\nurl = "http://x/#frag"  # trailing\n',
        'url = "http://x/#frag"\n',
    ),
    "a.c": (
        '// note\nconst char *s = "// not a comment"; /* trailing */\n',
        'const char *s = "// not a comment";\n',
    ),
    "a.cpp": (
        '// note\nauto s = "/* nope */";\n',
        'auto s = "/* nope */";\n',
    ),
    "a.cu": (
        '// note\n__global__ void k() {} // trailing\n',
        '__global__ void k() {}\n',
    ),
    "a.m": (
        '// note\nNSString *s = @"// nope";\n',
        'NSString *s = @"// nope";\n',
    ),
    "a.java": (
        '// note\nString s = "// nope"; /* trailing */\n',
        'String s = "// nope";\n',
    ),
    "a.kt": (
        '// note\nval s = "// nope"\n',
        'val s = "// nope"\n',
    ),
    "a.scala": (
        '// note\nval s = "// nope"\n',
        'val s = "// nope"\n',
    ),
    "a.swift": (
        '// note\nlet s = "// nope"\n',
        'let s = "// nope"\n',
    ),
    "a.cs": (
        '// note\nvar s = "// nope";\n',
        'var s = "// nope";\n',
    ),
    "a.js": (
        '// note\nconst s = "// nope";  // trailing\n',
        'const s = "// nope";\n',
    ),
    "a.ts": (
        '// note\nconst s: string = `// nope ${x}`;\n',
        'const s: string = `// nope ${x}`;\n',
    ),
    "a.jsx": (
        '// note\nconst e = <div title="// nope" />;\n',
        'const e = <div title="// nope" />;\n',
    ),
    "a.tsx": (
        '// note\nconst e = <div title="// nope" />;\n',
        'const e = <div title="// nope" />;\n',
    ),
    "a.go": (
        '// note\ns := `// nope`  // trailing\n',
        's := `// nope`\n',
    ),
    "a.rs": (
        '// note\nlet s = "// nope"; /* trailing */\n',
        'let s = "// nope";\n',
    ),
    "a.sh": (
        '# note\necho "# nope"  # trailing\n',
        'echo "# nope"\n',
    ),
    "a.yaml": (
        '# note\nkey: "# nope"  # trailing\n',
        'key: "# nope"\n',
    ),
    "a.toml": (
        '# note\nkey = "# nope"  # trailing\n',
        'key = "# nope"\n',
    ),
    "a.rb": (
        '# note\ns = "# nope"  # trailing\n',
        's = "# nope"\n',
    ),
    "a.pl": (
        '# note\nmy $s = "# nope";  # trailing\n',
        'my $s = "# nope";\n',
    ),
    "a.r": (
        '# note\ns <- "# nope"  # trailing\n',
        's <- "# nope"\n',
    ),
    "a.jl": (
        '# note\ns = "# nope"  # trailing\n',
        's = "# nope"\n',
    ),
    "a.ex": (
        '# note\ns = "# nope"  # trailing\n',
        's = "# nope"\n',
    ),
    "a.nix": (
        '# note\ns = "# nope";  # trailing\n',
        's = "# nope";\n',
    ),
    "a.tf": (
        '# note\nname = "# nope"  # trailing\n',
        'name = "# nope"\n',
    ),
    "a.sql": (
        '-- note\nSELECT \'-- nope\';  -- trailing\n',
        "SELECT '-- nope';\n",
    ),
    "a.lua": (
        '-- note\nlocal s = "-- nope"  -- trailing\n',
        'local s = "-- nope"\n',
    ),
    "a.hs": (
        '-- note\ns = "-- nope"  -- trailing\n',
        's = "-- nope"\n',
    ),
    "a.html": (
        '<!-- note -->\n<p title="&lt;!-- nope --&gt;">x</p>\n',
        '<p title="&lt;!-- nope --&gt;">x</p>\n',
    ),
    "a.xml": (
        '<!-- note -->\n<root><item>text</item></root>\n',
        '<root><item>text</item></root>\n',
    ),
    "a.vue": (
        '<!-- note -->\n<template><p>x</p></template>\n',
        '<template><p>x</p></template>\n',
    ),
    "a.svelte": (
        '<!-- note -->\n<p>x</p>\n',
        '<p>x</p>\n',
    ),
    "a.css": (
        '/* note */\n.a { content: "/* nope */"; }\n',
        '.a { content: "/* nope */"; }\n',
    ),
    "a.scss": (
        '// note\n.a { content: "// nope"; }  /* trailing */\n',
        '.a { content: "// nope"; }\n',
    ),
    "a.less": (
        '// note\n.a { color: red; }\n',
        '.a { color: red; }\n',
    ),
    "a.tex": (
        '% note\n\\section{Results}  % trailing\n',
        '\\section{Results}\n',
    ),
    "Dockerfile": (
        '# note\nRUN echo "# nope"  # trailing\n',
        'RUN echo "# nope"\n',
    ),
    "Makefile": (
        '# note\nall:\n\techo hi\n',
        'all:\n\techo hi\n',
    ),
    "a.php": (
        '// note\n$s = "// nope";  # trailing\n',
        '$s = "// nope";\n',
    ),
    "a.vim": (
        '" note\nset number\n',
        'set number\n',
    ),
}


@pytest.mark.parametrize("filename", sorted(FIXTURES))
def test_language_has_a_spec(filename):
    assert spec_for_path(filename) is not None, f"no comment syntax registered for {filename}"


@pytest.mark.parametrize("filename", sorted(FIXTURES))
def test_language_scrubs_as_documented(filename):
    source, expected = FIXTURES[filename]
    result, _ = scrub_text("", source, filename, Config())
    assert result == expected


# Cases where a marker-shaped sequence is not a comment. Each of these once
# deleted live code.
ADVERSARIAL: dict[str, tuple[str, str]] = {
    "esc.tex": (
        "Coverage is 100\\% today.\n% note\n",
        "Coverage is 100\\% today.\n",
    ),
    "str.vim": (
        'let s = "hello world"\n" note\n',
        'let s = "hello world"\n',
    ),
    "attr.php": (
        "<?php\n#[Attribute]\nclass A {}\n// note\n",
        "<?php\n#[Attribute]\nclass A {}\n",
    ),
    "url.scss": (
        ".a { background: url(//cdn.example.com/x.png); }\n// note\n",
        ".a { background: url(//cdn.example.com/x.png); }\n",
    ),
    "esc.mk": (
        "HASH := \\#\n# note\n",
        "HASH := \\#\n",
    ),
    "class.c": (
        "char slash = '/';  // note\n",
        "char slash = '/';\n",
    ),
    "nested.hs": (
        "s = 1\n{- outer {- inner -} still -}\n",
        "s = 1\n",
    ),
    "literal.toml": (
        "s = '''# nope'''\n# note\n",
        "s = '''# nope'''\n",
    ),
    "string.sql": (
        "SELECT 'a--b';\n-- note\n",
        "SELECT 'a--b';\n",
    ),
    "expr.jsx": (
        "const e = <div>{/* note */}</div>;\n",
        "const e = <div>{}</div>;\n",
    ),
}


@pytest.mark.parametrize("filename", sorted(ADVERSARIAL))
def test_marker_shaped_code_is_not_treated_as_a_comment(filename):
    source, expected = ADVERSARIAL[filename]
    result, _ = scrub_text("", source, filename, Config())
    assert result == expected
