from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class StringSpec:
    open: str
    close: str
    escape: str | None = "\\"
    multiline: bool = False
    # Character literals ('a', '\n') look like strings but a bare quote is also
    # Rust lifetime syntax and C++ digit separators, so they only count as a
    # string when the closing quote shows up almost immediately.
    char_literal: bool = False
    # Template literals interpolate code, which may open further strings: the body
    # of `${...}` has to be skipped as code, not as string content.
    substitutions: bool = False


@dataclass(frozen=True)
class LanguageSpec:
    name: str
    line_comments: tuple[str, ...] = ()
    block_comments: tuple[tuple[str, str], ...] = ()
    strings: tuple[StringSpec, ...] = ()
    nested_blocks: bool = False
    heredocs: bool = False
    # JS regex literals can contain '/' and '*', which otherwise read as comments.
    regex_literals: bool = False
    # In shell and YAML a '#' only opens a comment at the start of a word.
    boundary_required: bool = False


DOUBLE = StringSpec('"', '"')
SINGLE = StringSpec("'", "'")
CHAR = StringSpec("'", "'", char_literal=True)
TEMPLATE = StringSpec("`", "`", multiline=True, substitutions=True)
RAW_BACKTICK = StringSpec("`", "`", escape=None, multiline=True)
PY_TRIPLE_DOUBLE = StringSpec('"""', '"""', multiline=True)
PY_TRIPLE_SINGLE = StringSpec("'''", "'''", multiline=True)

C_STYLE_STRINGS = (DOUBLE, CHAR)
SLASH_STAR = (("/*", "*/"),)

PYTHON = LanguageSpec(
    name="python",
    line_comments=("#",),
    strings=(PY_TRIPLE_DOUBLE, PY_TRIPLE_SINGLE, DOUBLE, SINGLE),
)

C_FAMILY = LanguageSpec(
    name="c-family",
    line_comments=("//",),
    block_comments=SLASH_STAR,
    strings=C_STYLE_STRINGS,
)

JAVASCRIPT = LanguageSpec(
    name="javascript",
    line_comments=("//",),
    block_comments=SLASH_STAR,
    strings=(TEMPLATE, DOUBLE, SINGLE),
    regex_literals=True,
)

GO = LanguageSpec(
    name="go",
    line_comments=("//",),
    block_comments=SLASH_STAR,
    strings=(RAW_BACKTICK, DOUBLE, CHAR),
)

RUST = LanguageSpec(
    name="rust",
    line_comments=("//",),
    block_comments=SLASH_STAR,
    strings=(DOUBLE, CHAR),
    nested_blocks=True,
)

SHELL = LanguageSpec(
    name="shell",
    line_comments=("#",),
    strings=(DOUBLE, SINGLE),
    heredocs=True,
    boundary_required=True,
)

YAML = LanguageSpec(
    name="yaml",
    line_comments=("#",),
    strings=(DOUBLE, SINGLE),
    boundary_required=True,
)

TOML = LanguageSpec(
    name="toml",
    line_comments=("#",),
    strings=(PY_TRIPLE_DOUBLE, PY_TRIPLE_SINGLE, DOUBLE, SINGLE),
)

HASH_ONLY = LanguageSpec(
    name="hash",
    line_comments=("#",),
    strings=(DOUBLE, SINGLE),
)

RUBY = LanguageSpec(
    name="ruby",
    line_comments=("#",),
    strings=(DOUBLE, SINGLE),
    heredocs=True,
)

SQL = LanguageSpec(
    name="sql",
    line_comments=("--",),
    block_comments=SLASH_STAR,
    strings=(SINGLE, DOUBLE),
)

LUA = LanguageSpec(
    name="lua",
    line_comments=("--",),
    block_comments=(("--[[", "]]"),),
    strings=(DOUBLE, SINGLE),
)

HASKELL = LanguageSpec(
    name="haskell",
    line_comments=("--",),
    block_comments=(("{-", "-}"),),
    strings=(DOUBLE, CHAR),
    nested_blocks=True,
)

MARKUP = LanguageSpec(
    name="markup",
    block_comments=(("<!--", "-->"),),
    strings=(),
)

CSS = LanguageSpec(name="css", block_comments=SLASH_STAR, strings=(DOUBLE, SINGLE))

SCSS = LanguageSpec(
    name="scss",
    line_comments=("//",),
    block_comments=SLASH_STAR,
    strings=(DOUBLE, SINGLE),
)

PERCENT = LanguageSpec(name="percent", line_comments=("%",), strings=(DOUBLE, SINGLE))

VIM = LanguageSpec(name="vim", line_comments=('"',), strings=(SINGLE,))

EXTENSION_SPECS: dict[str, LanguageSpec] = {
    ".py": PYTHON,
    ".pyi": PYTHON,
    ".pyx": PYTHON,
    ".c": C_FAMILY,
    ".h": C_FAMILY,
    ".cc": C_FAMILY,
    ".cpp": C_FAMILY,
    ".cxx": C_FAMILY,
    ".hpp": C_FAMILY,
    ".hh": C_FAMILY,
    ".cu": C_FAMILY,
    ".cuh": C_FAMILY,
    ".m": C_FAMILY,
    ".mm": C_FAMILY,
    ".java": C_FAMILY,
    ".kt": C_FAMILY,
    ".kts": C_FAMILY,
    ".scala": C_FAMILY,
    ".swift": C_FAMILY,
    ".cs": C_FAMILY,
    ".php": LanguageSpec(
        name="php",
        line_comments=("//", "#"),
        block_comments=SLASH_STAR,
        strings=(DOUBLE, SINGLE),
    ),
    ".js": JAVASCRIPT,
    ".jsx": JAVASCRIPT,
    ".mjs": JAVASCRIPT,
    ".cjs": JAVASCRIPT,
    ".ts": JAVASCRIPT,
    ".tsx": JAVASCRIPT,
    ".mts": JAVASCRIPT,
    ".cts": JAVASCRIPT,
    ".go": GO,
    ".rs": RUST,
    ".sh": SHELL,
    ".bash": SHELL,
    ".zsh": SHELL,
    ".ksh": SHELL,
    ".fish": SHELL,
    ".yaml": YAML,
    ".yml": YAML,
    ".toml": TOML,
    ".rb": RUBY,
    ".pl": HASH_ONLY,
    ".pm": HASH_ONLY,
    ".r": HASH_ONLY,
    ".jl": HASH_ONLY,
    ".ex": HASH_ONLY,
    ".exs": HASH_ONLY,
    ".nix": HASH_ONLY,
    ".tf": HASH_ONLY,
    ".hcl": HASH_ONLY,
    ".dockerfile": HASH_ONLY,
    ".mk": HASH_ONLY,
    ".cmake": HASH_ONLY,
    ".sql": SQL,
    ".lua": LUA,
    ".hs": HASKELL,
    ".html": MARKUP,
    ".htm": MARKUP,
    ".xml": MARKUP,
    ".vue": MARKUP,
    ".svelte": MARKUP,
    ".css": CSS,
    ".scss": SCSS,
    ".less": SCSS,
    ".sass": SCSS,
    ".tex": PERCENT,
    ".erl": PERCENT,
    ".vim": VIM,
}

BASENAME_SPECS: dict[str, LanguageSpec] = {
    "dockerfile": HASH_ONLY,
    "makefile": HASH_ONLY,
    "gnumakefile": HASH_ONLY,
    "cmakelists.txt": HASH_ONLY,
    ".gitignore": HASH_ONLY,
    ".dockerignore": HASH_ONLY,
    ".env": SHELL,
    ".bashrc": SHELL,
    ".zshrc": SHELL,
    ".bash_profile": SHELL,
}

# Prose and data formats where a "comment" is either content or does not exist.
NEVER_SCRUB_EXTENSIONS = frozenset(
    {".md", ".mdx", ".markdown", ".rst", ".txt", ".ipynb", ".json", ".lock", ".csv", ".tsv"}
)


def spec_for_path(path: str) -> LanguageSpec | None:
    basename = os.path.basename(path)
    lowered = basename.lower()
    _, extension = os.path.splitext(lowered)
    if extension in NEVER_SCRUB_EXTENSIONS:
        return None
    if lowered in BASENAME_SPECS:
        return BASENAME_SPECS[lowered]
    if lowered.startswith("dockerfile"):
        return HASH_ONLY
    return EXTENSION_SPECS.get(extension)
