from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from fnmatch import fnmatch
from pathlib import Path

CONFIG_FILENAME = ".comment-deleter.json"
USER_CONFIG_PATH = Path.home() / ".claude" / "comment-deleter.json"
DISABLE_ENVIRONMENT_VARIABLE = "CLAUDE_COMMENT_DELETER"


@dataclass
class Config:
    enabled: bool = True
    preserve_directives: bool = True
    strip_docstrings: bool = True
    scrub_bash_edits: bool = True
    max_bash_files: int = 200
    exclude_globs: tuple[str, ...] = (
        "**/node_modules/**",
        "**/.venv/**",
        "**/venv/**",
        "**/vendor/**",
        "**/third_party/**",
        "**/site-packages/**",
        "**/.git/**",
        "**/dist/**",
        "**/build/**",
    )
    preserve_patterns: tuple[re.Pattern[str], ...] = field(default_factory=tuple)
    exclude_extensions: tuple[str, ...] = ()

    def excludes(self, path: str) -> bool:
        _, extension = os.path.splitext(path.lower())
        if extension in self.exclude_extensions:
            return True
        posix = Path(path).as_posix()
        return any(_glob_matches(posix, pattern) for pattern in self.exclude_globs)


def _glob_matches(posix_path: str, pattern: str) -> bool:
    if fnmatch(posix_path, pattern):
        return True
    # "**/vendor/**" should also catch a relative path that starts at "vendor/".
    return pattern.startswith("**/") and fnmatch(posix_path, pattern[3:])


def load_config(project_directory: str | None) -> Config:
    config = Config()
    for candidate in _candidate_paths(project_directory):
        raw = _read_json(candidate)
        if raw:
            _apply(config, raw)
    if os.environ.get(DISABLE_ENVIRONMENT_VARIABLE, "").strip().lower() in {"0", "off", "false"}:
        config.enabled = False
    return config


def _candidate_paths(project_directory: str | None) -> list[Path]:
    paths = [USER_CONFIG_PATH]
    if project_directory:
        paths.append(Path(project_directory) / CONFIG_FILENAME)
        paths.append(Path(project_directory) / ".claude" / CONFIG_FILENAME)
    return paths


def _read_json(path: Path) -> dict | None:
    try:
        with path.open(encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _apply(config: Config, raw: dict) -> None:
    for name in ("enabled", "preserve_directives", "scrub_bash_edits", "strip_docstrings"):
        if isinstance(raw.get(name), bool):
            setattr(config, name, raw[name])
    if isinstance(raw.get("max_bash_files"), int):
        config.max_bash_files = raw["max_bash_files"]
    if isinstance(raw.get("exclude_globs"), list):
        config.exclude_globs = tuple(str(item) for item in raw["exclude_globs"])
    if isinstance(raw.get("exclude_extensions"), list):
        config.exclude_extensions = tuple(str(item).lower() for item in raw["exclude_extensions"])
    if isinstance(raw.get("preserve_patterns"), list):
        config.preserve_patterns = tuple(
            compiled
            for compiled in (_compile(str(item)) for item in raw["preserve_patterns"])
            if compiled is not None
        )


def _compile(pattern: str) -> re.Pattern[str] | None:
    try:
        return re.compile(pattern)
    except re.error:
        return None
