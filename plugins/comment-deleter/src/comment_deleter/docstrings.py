from __future__ import annotations

import ast

from .scanner import CommentSpan, line_starts_of

# A string that is nobody's value: not assigned, not passed, not returned, just
# evaluated and dropped. Deleting it can only change __doc__.
BARE_STRING_KIND = "docstring"

# Bodies that must not be left empty. Module is absent on purpose: an empty
# module is legal, a function or class with no statements is not.
BLOCK_FIELDS = ("body", "orelse", "finalbody")


def find_bare_strings(text: str) -> list[CommentSpan]:
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        return []
    # A module that reads its own __doc__ (argparse description=__doc__ and
    # friends) is using the docstring as a value, so leave the whole file alone.
    if "__doc__" in text:
        return []

    line_starts = line_starts_of(text)
    needs_placeholder = _sole_statements(tree)
    spans: list[CommentSpan] = []
    for node in ast.walk(tree):
        if not _is_bare_string(node):
            continue
        start = _offset(text, line_starts, node.lineno, node.col_offset)
        end = _offset(text, line_starts, node.end_lineno, node.end_col_offset)
        replacement = "pass" if id(node) in needs_placeholder else ""
        spans.append(CommentSpan(start, end, BARE_STRING_KIND, text[start:end], replacement))
    return spans


def _is_bare_string(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    )


def _sole_statements(tree: ast.AST) -> set[int]:
    marked: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Module):
            continue
        for field in BLOCK_FIELDS:
            body = getattr(node, field, None)
            if isinstance(body, list) and len(body) == 1 and _is_bare_string(body[0]):
                marked.add(id(body[0]))
    return marked


def _offset(text: str, line_starts: list[int], lineno: int, column: int) -> int:
    line_start = line_starts[lineno - 1]
    line_end = text.find("\n", line_start)
    line = text[line_start : line_end if line_end >= 0 else len(text)]
    # ast reports columns as UTF-8 byte offsets, not character offsets.
    return line_start + len(line.encode("utf-8")[:column].decode("utf-8", "ignore"))
