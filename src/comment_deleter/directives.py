from __future__ import annotations

import re

from .scanner import CommentSpan

# Comments whose deletion changes how a tool, compiler, or loader behaves. These
# are directives wearing comment syntax, not prose, so they survive by default.
DIRECTIVE_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"^\s*(?:#|//)!",
        r"\bcoding[:=]\s*[-\w.]+",
        r"\bspdx-license-identifier\b",
        r"\bcopyright\b",
        r"\blicensed under\b",
        r"\ball rights reserved\b",
        r"@license\b",
        r"@generated\b",
        r"\bdo not edit\b",
        r"\bcode generated\b",
        r"\bnoqa\b",
        r"\bnosec\b",
        r"\bnolint\b",
        r"\bnoinspection\b",
        r"\btype:\s*ignore\b",
        r"^\s*(?:#|//)\s*type:\s",
        r"\b(?:pylint|mypy|pyright|ruff|flake8|isort|bandit|pyre|yapf|black|autopep8):",
        r"\bpragma:\s*no\s*cover\b",
        r"\bfmt:\s*(?:on|off|skip)\b",
        r"\beslint-(?:disable|enable)",
        r"\beslint-env\b",
        r"\bprettier-ignore\b",
        r"\bbiome-ignore\b",
        r"\boxlint-disable\b",
        r"\bjshint\b",
        r"\bjslint\b",
        r"^\s*/\*\s*global\s",
        r"@ts-(?:ignore|expect-error|nocheck|check)\b",
        r"^\s*///\s*<reference\b",
        r"\bwebpackchunkname\b",
        r"\b(?:istanbul|c8|v8)\s+ignore\b",
        r"^\s*//go:",
        r"^\s*//\s*\+build\b",
        r"\bclang-format\s+(?:on|off)\b",
        r"\bNOLINTNEXTLINE\b",
        r"\biwyu pragma:",
        r"\bshellcheck\s+(?:disable|shell|source)",
        r"\byamllint\b",
        r"\brustfmt::skip\b",
        r"\bclippy::",
        r"\bsourcemappingurl\b",
        r"\bvim:\s*set\b",
        r"^\s*(?:#|//)\s*-\*-",
    )
)

KEEP_MARKER = re.compile(r"comment-deleter:\s*keep", re.IGNORECASE)

# Doctests inside a docstring are executable tests, not prose.
DOCTEST = re.compile(r"^\s*>>> ", re.MULTILINE)


def is_directive(span: CommentSpan) -> bool:
    if span.kind == "docstring" and DOCTEST.search(span.text):
        return True
    return any(pattern.search(span.text) for pattern in DIRECTIVE_PATTERNS)


def matches_any(span: CommentSpan, patterns: tuple[re.Pattern[str], ...]) -> bool:
    return any(pattern.search(span.text) for pattern in patterns)
