from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from . import gitstate, snapshots
from .config import Config, load_config
from .languages import spec_for_path
from .scrub import scrub_text

EDIT_TOOLS = frozenset({"Edit", "Write", "MultiEdit", "NotebookEdit"})
MAX_SCRUB_BYTES = 2 * 1024 * 1024


def resolve_path(cwd: str, raw_path: str | None) -> str | None:
    if not raw_path:
        return None
    return os.path.abspath(os.path.join(cwd or os.getcwd(), raw_path))


def scrub_file(path: str, old_text: str, config: Config) -> int:
    if spec_for_path(path) is None or config.excludes(path):
        return 0
    try:
        if os.path.getsize(path) > MAX_SCRUB_BYTES:
            return 0
        # newline="" keeps CRLF intact; the default would rewrite the whole file to LF.
        with open(path, encoding="utf-8", newline="") as handle:
            new_text = handle.read()
    except (OSError, UnicodeDecodeError):
        return 0
    scrubbed, removed = scrub_text(old_text, new_text, path, config)
    if removed == 0 or scrubbed == new_text:
        return 0
    return removed if _write_atomically(path, scrubbed) else 0


def _write_atomically(path: str, content: str) -> bool:
    directory = os.path.dirname(path) or "."
    try:
        mode = os.stat(path).st_mode
        handle, temporary = tempfile.mkstemp(dir=directory, prefix=".comment-deleter-")
        with os.fdopen(handle, "w", encoding="utf-8", newline="") as stream:
            stream.write(content)
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    except OSError:
        return False
    return True


def run_pre(event: dict) -> None:
    cwd = event.get("cwd") or os.getcwd()
    config = load_config(cwd)
    if not config.enabled:
        return
    session_id = event.get("session_id", "")
    tool_name = event.get("tool_name", "")
    snapshots.prune()

    if tool_name in EDIT_TOOLS:
        path = resolve_path(cwd, (event.get("tool_input") or {}).get("file_path"))
        if path and spec_for_path(path) is not None and not config.excludes(path):
            snapshots.store(session_id, path)
        return

    if tool_name == "Bash" and config.scrub_bash_edits:
        _snapshot_working_tree(event, cwd, config, session_id)


def _snapshot_working_tree(event: dict, cwd: str, config: Config, session_id: str) -> None:
    dirty = [path for path in gitstate.dirty_files(cwd) if _is_scrubbable(path, config)]
    if len(dirty) > config.max_bash_files:
        return
    for path in dirty:
        snapshots.store(session_id, path)
    _write_bash_record(session_id, event.get("tool_use_id", ""), dirty)


def _is_scrubbable(path: str, config: Config) -> bool:
    return spec_for_path(path) is not None and not config.excludes(path)


def _bash_record_path(session_id: str, tool_use_id: str) -> Path:
    return snapshots.session_directory(session_id) / f"bash-{tool_use_id or 'unknown'}.json"


def _write_bash_record(session_id: str, tool_use_id: str, dirty: list[str]) -> None:
    record = _bash_record_path(session_id, tool_use_id)
    try:
        record.parent.mkdir(parents=True, exist_ok=True)
        record.write_text(json.dumps(dirty), encoding="utf-8")
    except OSError:
        return


def _read_bash_record(session_id: str, tool_use_id: str) -> list[str] | None:
    record = _bash_record_path(session_id, tool_use_id)
    try:
        data = json.loads(record.read_text(encoding="utf-8"))
        record.unlink(missing_ok=True)
    except (OSError, ValueError):
        return None
    return data if isinstance(data, list) else None


def run_post(event: dict) -> dict[str, int]:
    cwd = event.get("cwd") or os.getcwd()
    config = load_config(cwd)
    if not config.enabled:
        return {}
    session_id = event.get("session_id", "")
    tool_name = event.get("tool_name", "")

    if tool_name in EDIT_TOOLS:
        return _post_edit(event, cwd, config, session_id)
    if tool_name == "Bash" and config.scrub_bash_edits:
        return _post_bash(event, cwd, config, session_id)
    return {}


def _post_edit(event: dict, cwd: str, config: Config, session_id: str) -> dict[str, int]:
    path = resolve_path(cwd, (event.get("tool_input") or {}).get("file_path"))
    if not path:
        return {}
    old_text = snapshots.load(session_id, path)
    snapshots.discard(session_id, path)
    if old_text is None:
        return {}
    removed = scrub_file(path, old_text, config)
    return {path: removed} if removed else {}


def _post_bash(event: dict, cwd: str, config: Config, session_id: str) -> dict[str, int]:
    previously_dirty = _read_bash_record(session_id, event.get("tool_use_id", ""))
    if previously_dirty is None:
        return {}
    known = set(previously_dirty)
    results: dict[str, int] = {}
    dirty_now = [path for path in gitstate.dirty_files(cwd) if _is_scrubbable(path, config)]
    if len(dirty_now) > config.max_bash_files:
        return {}
    for path in dirty_now:
        old_text = snapshots.load(session_id, path) if path in known else _clean_baseline(cwd, path)
        if old_text is None:
            continue
        removed = scrub_file(path, old_text, config)
        if removed:
            results[path] = removed
    for path in known:
        snapshots.discard(session_id, path)
    return results


def _clean_baseline(cwd: str, path: str) -> str:
    # The file was clean before the command ran, so HEAD is its exact prior state;
    # a file with no HEAD version is one the command just created.
    content = gitstate.head_content(cwd, path)
    return "" if content is None else content
