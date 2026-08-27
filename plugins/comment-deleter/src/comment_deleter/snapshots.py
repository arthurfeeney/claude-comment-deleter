from __future__ import annotations

import hashlib
import os
import shutil
import time
from pathlib import Path

ABSENT_SUFFIX = ".absent"
MAX_SNAPSHOT_AGE_SECONDS = 6 * 60 * 60
MAX_SNAPSHOT_BYTES = 8 * 1024 * 1024


def snapshot_root() -> Path:
    configured = os.environ.get("CLAUDE_PLUGIN_DATA")
    base = Path(configured) if configured else Path.home() / ".cache" / "claude-comment-deleter"
    return base / "snapshots"


def session_directory(session_id: str) -> Path:
    return snapshot_root() / (session_id or "no-session")


def _key(path: str) -> str:
    return hashlib.sha1(os.path.abspath(path).encode("utf-8")).hexdigest()


def store(session_id: str, path: str) -> None:
    directory = session_directory(session_id)
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except OSError:
        return
    target = directory / _key(path)
    absent_marker = Path(str(target) + ABSENT_SUFFIX)
    try:
        if not os.path.isfile(path):
            target.unlink(missing_ok=True)
            absent_marker.touch()
            return
        if os.path.getsize(path) > MAX_SNAPSHOT_BYTES:
            return
        absent_marker.unlink(missing_ok=True)
        shutil.copyfile(path, target)
    except OSError:
        return


def load(session_id: str, path: str) -> str | None:
    directory = session_directory(session_id)
    target = directory / _key(path)
    if Path(str(target) + ABSENT_SUFFIX).exists():
        return ""
    try:
        with target.open(encoding="utf-8", newline="") as handle:
            return handle.read()
    except (OSError, UnicodeDecodeError):
        return None


def discard(session_id: str, path: str) -> None:
    directory = session_directory(session_id)
    target = directory / _key(path)
    for candidate in (target, Path(str(target) + ABSENT_SUFFIX)):
        try:
            candidate.unlink(missing_ok=True)
        except OSError:
            pass


def prune(now: float | None = None) -> None:
    root = snapshot_root()
    cutoff = (now or time.time()) - MAX_SNAPSHOT_AGE_SECONDS
    try:
        sessions = list(root.iterdir())
    except OSError:
        return
    for session in sessions:
        try:
            if session.stat().st_mtime < cutoff:
                shutil.rmtree(session, ignore_errors=True)
        except OSError:
            continue
