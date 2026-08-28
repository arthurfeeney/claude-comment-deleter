from __future__ import annotations

import io
import re
import token as token_module
import tokenize
from dataclasses import dataclass

from .languages import LanguageSpec, StringSpec

WORD_BOUNDARY_BEFORE = frozenset(" \t\n\r;&|(")
HEREDOC_START = re.compile(r"<<[-~]?\s*(?:(['\"])([A-Za-z_][A-Za-z0-9_]*)\1|([A-Za-z_][A-Za-z0-9_]*))")
CHAR_LITERAL_WINDOW = 12
MAX_NESTING = 24


@dataclass(frozen=True)
class CommentSpan:
    start: int
    end: int
    kind: str
    text: str
    replacement: str = ""

    def line_range(self, line_starts: list[int]) -> tuple[int, int]:
        return (line_index(line_starts, self.start), line_index(line_starts, self.end - 1))

    def normalized(self) -> str:
        return "\n".join(line.strip() for line in self.text.strip().splitlines())


def line_starts_of(text: str) -> list[int]:
    starts = [0]
    for index, character in enumerate(text):
        if character == "\n":
            starts.append(index + 1)
    return starts


def line_index(line_starts: list[int], offset: int) -> int:
    low, high = 0, len(line_starts) - 1
    while low < high:
        middle = (low + high + 1) // 2
        if line_starts[middle] <= offset:
            low = middle
        else:
            high = middle - 1
    return low


def find_comments(text: str, spec: LanguageSpec) -> list[CommentSpan]:
    if spec.name == "python":
        python_spans = _find_python_comments(text)
        if python_spans is not None:
            return python_spans
    return _scan(text, spec)


def _find_python_comments(text: str) -> list[CommentSpan] | None:
    line_starts = line_starts_of(text)
    spans: list[CommentSpan] = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(text).readline):
            if tok.type != token_module.COMMENT:
                continue
            row, column = tok.start
            start = line_starts[row - 1] + column
            spans.append(CommentSpan(start, start + len(tok.string), "line", tok.string))
    except (tokenize.TokenError, IndentationError, SyntaxError, ValueError):
        return None
    return spans


def _token_table(spec: LanguageSpec) -> list[tuple[str, str, object]]:
    table: list[tuple[str, str, object]] = []
    for string_spec in spec.strings:
        table.append((string_spec.open, "string", string_spec))
    for open_token, close_token in spec.block_comments:
        table.append((open_token, "block", (open_token, close_token)))
    for marker in spec.line_comments:
        table.append((marker, "line", marker))
    table.sort(key=lambda entry: len(entry[0]), reverse=True)
    return table


def _scan(text: str, spec: LanguageSpec) -> list[CommentSpan]:
    table = _token_table(spec)
    spans: list[CommentSpan] = []
    length = len(text)
    index = 0
    while index < length:
        if spec.protect_urls and text.startswith("url(", index):
            closing = text.find(")", index)
            index = length if closing < 0 else closing + 1
            continue
        if spec.heredocs and text.startswith("<<", index):
            skipped = _skip_heredoc(text, index)
            if skipped is not None:
                index = skipped
                continue
        if spec.regex_literals and text[index] == "/":
            skipped = _skip_regex_literal(text, index)
            if skipped is not None:
                index = skipped
                continue
        entry = _match_token(text, index, table)
        if entry is None:
            index += 1
            continue
        token, kind, payload = entry
        if kind == "string":
            consumed = _skip_string(text, index, payload, table)
            if consumed is None:
                index += 1
                continue
            index = consumed
        elif kind == "block":
            end = _skip_block(text, index, payload, spec.nested_blocks)
            spans.append(CommentSpan(index, end, "block", text[index:end]))
            index = end
        else:
            if not _line_comment_starts_here(text, index, token, spec):
                index += len(token)
                continue
            end = text.find("\n", index)
            end = length if end < 0 else end
            # Leave a CRLF's carriage return out of the span so removing a trailing
            # comment does not silently convert that one line to a bare LF.
            stop = end - 1 if end > index and text[end - 1] == "\r" else end
            spans.append(CommentSpan(index, stop, "line", text[index:stop]))
            index = end
    return spans


def _match_token(
    text: str, index: int, table: list[tuple[str, str, object]]
) -> tuple[str, str, object] | None:
    for token, kind, payload in table:
        if text.startswith(token, index):
            return (token, kind, payload)
    return None


def _line_comment_starts_here(text: str, index: int, token: str, spec: LanguageSpec) -> bool:
    if spec.boundary_required and not _at_word_boundary(text, index):
        return False
    if spec.line_comment_escape and _is_escaped(text, index, spec.line_comment_escape):
        return False
    if spec.line_comment_at_line_start and text[:index].rsplit("\n", 1)[-1].strip():
        return False
    return not any(text.startswith(exception, index) for exception in spec.line_comment_exceptions)


def _is_escaped(text: str, index: int, escape: str) -> bool:
    count = 0
    cursor = index - 1
    while cursor >= 0 and text[cursor] == escape:
        count += 1
        cursor -= 1
    return count % 2 == 1


def _at_word_boundary(text: str, index: int) -> bool:
    return index == 0 or text[index - 1] in WORD_BOUNDARY_BEFORE


def _skip_string(
    text: str,
    index: int,
    string_spec: StringSpec,
    table: list[tuple[str, str, object]] | None = None,
    depth: int = 0,
) -> int | None:
    length = len(text)
    cursor = index + len(string_spec.open)
    limit = cursor + CHAR_LITERAL_WINDOW if string_spec.char_literal else length
    while cursor < length and cursor <= limit:
        character = text[cursor]
        if string_spec.escape and character == string_spec.escape:
            cursor += 2
            continue
        if not string_spec.multiline and character == "\n":
            return None if string_spec.char_literal else cursor
        if string_spec.substitutions and text.startswith("${", cursor) and depth < MAX_NESTING:
            cursor = _skip_substitution(text, cursor + 2, table, depth + 1)
            continue
        if text.startswith(string_spec.close, cursor):
            return cursor + len(string_spec.close)
        cursor += 1
    if string_spec.char_literal:
        return None
    return length


def _skip_substitution(
    text: str, cursor: int, table: list[tuple[str, str, object]] | None, depth: int
) -> int:
    length = len(text)
    braces = 1
    while cursor < length:
        character = text[cursor]
        if character == "{":
            braces += 1
        elif character == "}":
            braces -= 1
            if braces == 0:
                return cursor + 1
        elif table is not None:
            entry = _match_token(text, cursor, table)
            if entry is not None and entry[1] == "string":
                consumed = _skip_string(text, cursor, entry[2], table, depth)
                if consumed is not None:
                    cursor = consumed
                    continue
        cursor += 1
    return length


def _skip_block(text: str, index: int, tokens: tuple[str, str], nested: bool) -> int:
    open_token, close_token = tokens
    length = len(text)
    depth = 1
    cursor = index + len(open_token)
    while cursor < length:
        if nested and text.startswith(open_token, cursor):
            depth += 1
            cursor += len(open_token)
            continue
        if text.startswith(close_token, cursor):
            depth -= 1
            cursor += len(close_token)
            if depth == 0:
                return cursor
            continue
        cursor += 1
    return length


def _skip_heredoc(text: str, index: int) -> int | None:
    match = HEREDOC_START.match(text, index)
    if match is None:
        return None
    terminator = match.group(2) or match.group(3)
    body_start = text.find("\n", match.end())
    if body_start < 0:
        return len(text)
    closing = re.compile(rf"^[ \t]*{re.escape(terminator)}[ \t]*$", re.MULTILINE)
    closing_match = closing.search(text, body_start + 1)
    if closing_match is None:
        return len(text)
    return closing_match.end()


REGEX_ALLOWED_AFTER = frozenset("(,=:[!&|?{};+-*%^~<>")
REGEX_ALLOWED_KEYWORDS = frozenset(
    {
        "return", "typeof", "case", "in", "of", "do", "else", "yield",
        "await", "new", "delete", "void", "throw", "instanceof",
    }
)


def _skip_regex_literal(text: str, index: int) -> int | None:
    if text[index + 1 : index + 2] in {"/", "*", ""}:
        return None
    if not _regex_position(text, index):
        return None
    cursor = index + 1
    length = len(text)
    in_class = False
    while cursor < length:
        character = text[cursor]
        if character == "\\":
            cursor += 2
            continue
        if character == "\n":
            return None
        if character == "[":
            in_class = True
        elif character == "]":
            in_class = False
        elif character == "/" and not in_class:
            cursor += 1
            while cursor < length and text[cursor].isalpha():
                cursor += 1
            return cursor
        cursor += 1
    return None


def _regex_position(text: str, index: int) -> bool:
    cursor = index - 1
    while cursor >= 0 and text[cursor] in " \t\r\n":
        cursor -= 1
    if cursor < 0:
        return True
    character = text[cursor]
    if character in REGEX_ALLOWED_AFTER:
        return True
    if not (character.isalnum() or character == "_"):
        return False
    end = cursor + 1
    while cursor >= 0 and (text[cursor].isalnum() or text[cursor] == "_"):
        cursor -= 1
    return text[cursor + 1 : end] in REGEX_ALLOWED_KEYWORDS
