from __future__ import annotations

import os
import subprocess

GIT_TIMEOUT_SECONDS = 10


def _git(cwd: str, *arguments: str) -> subprocess.CompletedProcess | None:
    try:
        return subprocess.run(
            ("git", *arguments),
            cwd=cwd,
            capture_output=True,
            timeout=GIT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError):
        return None


def repository_root(cwd: str) -> str | None:
    result = _git(cwd, "rev-parse", "--show-toplevel")
    if result is None or result.returncode != 0:
        return None
    return result.stdout.decode("utf-8", "replace").strip() or None


def dirty_files(cwd: str) -> list[str]:
    root = repository_root(cwd)
    if root is None:
        return []
    result = _git(cwd, "status", "--porcelain", "-z", "--untracked-files=all")
    if result is None or result.returncode != 0:
        return []
    return [os.path.join(root, relative) for relative in _parse_porcelain(result.stdout)]


def _parse_porcelain(payload: bytes) -> list[str]:
    fields = payload.decode("utf-8", "replace").split("\0")
    paths: list[str] = []
    index = 0
    while index < len(fields):
        entry = fields[index]
        index += 1
        if len(entry) < 4:
            continue
        status, path = entry[:2], entry[3:]
        if status[0] in ("R", "C"):
            # Rename and copy entries are followed by their source path.
            index += 1
        if status != "D " and status != " D":
            paths.append(path)
    return paths


def head_content(cwd: str, path: str) -> str | None:
    return show(cwd, "HEAD", path)


def show(cwd: str, ref: str, path: str) -> str | None:
    root = repository_root(cwd)
    if root is None:
        return None
    relative = os.path.relpath(os.path.abspath(path), root)
    result = _git(cwd, "show", f"{ref}:{relative}")
    if result is None or result.returncode != 0:
        return None
    try:
        return result.stdout.decode("utf-8")
    except UnicodeDecodeError:
        return None
