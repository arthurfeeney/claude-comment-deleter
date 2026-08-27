from __future__ import annotations

import ast
import difflib
from collections import Counter

from .config import Config
from .directives import KEEP_MARKER, is_directive, matches_any
from .docstrings import find_bare_strings
from .languages import LanguageSpec, spec_for_path
from .scanner import CommentSpan, find_comments, line_starts_of

PYTHON_SUFFIXES = (".py", ".pyi")


def touched_lines(old_lines: list[str], new_lines: list[str]) -> set[int]:
    matcher = difflib.SequenceMatcher(None, old_lines, new_lines, autojunk=False)
    touched: set[int] = set()
    for tag, _, _, new_start, new_end in matcher.get_opcodes():
        if tag in ("insert", "replace"):
            touched.update(range(new_start, new_end))
    return touched


def deletable_spans(text: str, spec: LanguageSpec, config: Config) -> list[CommentSpan]:
    spans = find_comments(text, spec)
    if config.strip_docstrings and spec.name == "python":
        spans = spans + find_bare_strings(text)
        spans.sort(key=lambda span: span.start)
    return spans


def select_deletions(
    old_text: str, new_text: str, spec: LanguageSpec, config: Config
) -> list[CommentSpan]:
    new_spans = deletable_spans(new_text, spec, config)
    if not new_spans:
        return []

    # A comment survives if its exact text was already somewhere in the old file,
    # so reindenting or editing the code around a comment does not condemn it.
    surviving = Counter(span.normalized() for span in deletable_spans(old_text, spec, config))
    touched = touched_lines(old_text.splitlines(), new_text.splitlines())
    line_starts = line_starts_of(new_text)

    candidates: list[CommentSpan] = []
    for span in new_spans:
        first_line, last_line = span.line_range(line_starts)
        if touched.intersection(range(first_line, last_line + 1)):
            candidates.append(span)
        elif surviving[span.normalized()]:
            surviving[span.normalized()] -= 1

    deletions: list[CommentSpan] = []
    for span in candidates:
        key = span.normalized()
        if surviving[key] > 0:
            surviving[key] -= 1
            continue
        if config.preserve_directives and is_directive(span):
            continue
        if KEEP_MARKER.search(span.text) or matches_any(span, config.preserve_patterns):
            continue
        deletions.append(span)
    return deletions


def apply_deletions(text: str, spans: list[CommentSpan]) -> str:
    result = text
    for span in sorted(spans, key=lambda span: span.start, reverse=True):
        if span.replacement:
            result = result[: span.start] + span.replacement + result[span.end :]
            continue
        # Deleting right-to-left keeps earlier offsets valid, so measure against
        # the in-progress result: a comment already removed from this line may have
        # just made the line blank.
        start, end = _removal_range(result, span)
        result = result[:start] + result[end:]
    return result


def _removal_range(text: str, span: CommentSpan) -> tuple[int, int]:
    line_start = text.rfind("\n", 0, span.start) + 1
    line_end = text.find("\n", span.end)
    line_end = len(text) if line_end < 0 else line_end
    before = text[line_start : span.start]
    after = text[span.end : line_end]

    if not before.strip() and not after.strip():
        end = line_end + 1 if line_end < len(text) else line_end
        return (line_start, end)

    start = span.start
    while start > line_start and text[start - 1] in " \t":
        start -= 1
    if start == span.start:
        # Nothing separated the comment from the code on its left, so collapse the
        # gap on its right instead: "f(/* c */ bar)" must not become "f( bar)".
        end = span.end
        while end < line_end and text[end] in " \t":
            end += 1
        return (start, end)
    return (start, span.end)


def scrub_text(old_text: str, new_text: str, path: str, config: Config) -> tuple[str, int]:
    spec = spec_for_path(path)
    if spec is None or config.excludes(path):
        return new_text, 0
    deletions = select_deletions(old_text, new_text, spec, config)
    if not deletions:
        return new_text, 0
    scrubbed = apply_deletions(new_text, deletions)
    if not _is_safe(new_text, scrubbed, path):
        return new_text, 0
    return scrubbed, len(deletions)


def _is_safe(before: str, after: str, path: str) -> bool:
    if before.strip() and not after.strip():
        return False
    if path.lower().endswith(PYTHON_SUFFIXES):
        return _python_still_parses(before, after)
    return True


def _python_still_parses(before: str, after: str) -> bool:
    try:
        ast.parse(before)
    except SyntaxError:
        return True
    try:
        ast.parse(after)
    except SyntaxError:
        return False
    return True
