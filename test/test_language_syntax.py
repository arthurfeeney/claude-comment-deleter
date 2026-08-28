import functools
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from typing import Callable

import pytest

from comment_deleter.config import Config
from comment_deleter.scrub import scrub_text

PROBE_TIMEOUT_SECONDS = 30
CHECK_TIMEOUT_SECONDS = 120


@dataclass(frozen=True)
class SyntaxCase:
    name: str
    filename: str
    # First candidate that actually runs wins, so gcc or clang can stand in for
    # each other depending on what the machine has.
    candidates: tuple[str, ...]
    argv: Callable[[str, str], list[str]]
    source: str


@functools.lru_cache(maxsize=None)
def working_executable(candidates: tuple[str, ...]) -> str | None:
    for candidate in candidates:
        if shutil.which(candidate) is None:
            continue
        # Being on PATH is not enough: macOS ships a javac stub that resolves but
        # cannot run without a JDK behind it.
        for flag in ("--version", "-version"):
            try:
                probe = subprocess.run(
                    [candidate, flag],
                    capture_output=True,
                    timeout=PROBE_TIMEOUT_SECONDS,
                )
            except (OSError, subprocess.SubprocessError):
                continue
            if probe.returncode == 0:
                return candidate
    return None


CASES = (
    SyntaxCase(
        "c", "s.c", ("gcc", "clang", "cc"),
        lambda exe, path: [exe, "-fsyntax-only", path],
        '#include <stdio.h>\n'
        '/* header */\n'
        'int main(void) {\n'
        '    const char *s = "// not a comment /* nor this */";\n'
        "    char slash = '/';  // trailing\n"
        '    printf("%s%c", s, slash);\n'
        '    return 0;  /* done */\n'
        '}\n',
    ),
    SyntaxCase(
        "cpp", "s.cpp", ("g++", "clang++", "c++"),
        lambda exe, path: [exe, "-fsyntax-only", "-std=c++17", path],
        '#include <string>\n'
        '// note\n'
        'int main() {\n'
        '    std::string s = R"(// raw not a comment)";\n'
        '    auto n = s.size() / 2;  // trailing\n'
        '    return static_cast<int>(n);\n'
        '}\n',
    ),
    SyntaxCase(
        "objc", "s.m", ("clang", "gcc"),
        lambda exe, path: [exe, "-fsyntax-only", "-x", "objective-c", path],
        '// note\n'
        'int main(void) {\n'
        '    const char *s = "// nope";\n'
        '    return s[0];  /* trailing */\n'
        '}\n',
    ),
    SyntaxCase(
        "rust", "s.rs", ("rustc",),
        lambda exe, path: [
            exe, "--edition", "2021", "--crate-type", "lib", "--emit", "metadata",
            "-o", os.path.join(os.path.dirname(path), "out.rmeta"), path,
        ],
        '// note\n'
        "pub fn run<'a>(x: &'a str) -> usize {\n"
        '    let s = "// nope";\n'
        '    /* outer /* nested */ still */\n'
        '    x.len() + s.len()  // trailing\n'
        '}\n',
    ),
    SyntaxCase(
        "ruby", "s.rb", ("ruby",),
        lambda exe, path: [exe, "-c", path],
        '# note\ns = "# nope"\nputs s  # trailing\n',
    ),
    SyntaxCase(
        "perl", "s.pl", ("perl",),
        lambda exe, path: [exe, "-c", path],
        '# note\nmy $s = "# nope";\nprint $s;  # trailing\n1;\n',
    ),
    SyntaxCase(
        "swift", "s.swift", ("swiftc",),
        lambda exe, path: [exe, "-parse", path],
        '// note\nlet s = "// nope"\nlet n = s.count / 2  // trailing\nprint(n)\n',
    ),
    SyntaxCase(
        "java", "Sample.java", ("javac",),
        lambda exe, path: [exe, "-d", os.path.dirname(path), path],
        '// note\n'
        'class Sample {\n'
        '    static String s = "// nope";  /* trailing */\n'
        '    public static void main(String[] a) { System.out.println(s); }\n'
        '}\n',
    ),
    SyntaxCase(
        "javascript", "s.js", ("node",),
        lambda exe, path: [exe, "--check", path],
        '// note\n'
        'const re = /https:\\/\\//g;\n'
        'const t = `outer ${fn(`https://x`)} end`;\n'
        'const s = "// nope";  // trailing\n'
        'module.exports = { re, t, s };\n',
    ),
    SyntaxCase(
        "shell", "s.sh", ("bash",),
        lambda exe, path: [exe, "-n", path],
        '#!/usr/bin/env bash\n'
        '# note\n'
        'items=(a b)\n'
        'echo "${#items[@]}"  # trailing\n'
        "cat <<'EOF'\n"
        '# not a comment\n'
        'EOF\n',
    ),
    SyntaxCase(
        "xml", "s.xml", ("xmllint",),
        lambda exe, path: [exe, "--noout", path],
        '<?xml version="1.0"?>\n'
        '<!-- note -->\n'
        '<root><item name="value">text</item></root>\n',
    ),
    SyntaxCase(
        "sql", "s.sql", ("sqlite3",),
        lambda exe, path: [exe, ":memory:", f".read {path}"],
        '-- note\n'
        'CREATE TABLE t (a TEXT);\n'
        "INSERT INTO t VALUES ('-- not a comment');  -- trailing\n",
    ),
    SyntaxCase(
        "make", "Makefile", ("make", "gmake"),
        lambda exe, path: [exe, "-n", "-f", path, "all"],
        '# note\n'
        'HASH := \\#\n'
        'all:\n'
        '\t@echo "building $(HASH)"  # trailing\n',
    ),
)


def run_checker(argv):
    return subprocess.run(argv, capture_output=True, text=True, timeout=CHECK_TIMEOUT_SECONDS)


@pytest.mark.parametrize("case", CASES, ids=[case.name for case in CASES])
def test_scrubbed_source_still_parses(case):
    executable = working_executable(case.candidates)
    if executable is None:
        pytest.skip(f"no working {' / '.join(case.candidates)} on this machine")

    with tempfile.TemporaryDirectory() as directory:
        path = os.path.join(directory, case.filename)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(case.source)

        baseline = run_checker(case.argv(executable, path))
        # The toolchain works, so a fixture that will not compile is a bug in this
        # test file, not a missing dependency. Never hide it behind a skip.
        assert baseline.returncode == 0, (
            f"{case.name}: fixture does not compile with {executable}; fix the fixture\n"
            f"{baseline.stderr[:600]}"
        )

        scrubbed, removed = scrub_text("", case.source, case.filename, Config(preserve_directives=False))
        assert removed > 0, f"{case.name}: fixture contains no deletable comments"

        with open(path, "w", encoding="utf-8") as handle:
            handle.write(scrubbed)
        after = run_checker(case.argv(executable, path))

    assert after.returncode == 0, (
        f"{case.name}: scrubbed source no longer parses with {executable}\n"
        f"--- scrubbed ---\n{scrubbed}\n--- stderr ---\n{after.stderr[:600]}"
    )
