from __future__ import annotations

import argparse
import os
import sys

from . import gitstate
from .config import load_config
from .languages import spec_for_path
from .runner import scrub_file
from .scrub import scrub_text


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="comment-deleter",
        description="Delete comments added or edited since a git baseline.",
    )
    parser.add_argument("paths", nargs="*", help="Files to scrub. Defaults to the dirty worktree.")
    parser.add_argument("--baseline", default="HEAD", help="Git ref to compare against.")
    parser.add_argument("--dry-run", action="store_true", help="Report without writing.")
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    cwd = os.getcwd()
    config = load_config(cwd)
    targets = [os.path.abspath(path) for path in arguments.paths] or gitstate.dirty_files(cwd)
    targets = [path for path in targets if spec_for_path(path) and not config.excludes(path)]

    if not targets:
        print("comment-deleter: nothing to scrub")
        return 0

    total = 0
    for path in targets:
        baseline = _baseline_text(cwd, path, arguments.baseline)
        removed = _count(path, baseline, config) if arguments.dry_run else scrub_file(path, baseline, config)
        if removed:
            total += removed
            print(f"{os.path.relpath(path, cwd)}: {removed} comment(s)")
    verb = "would remove" if arguments.dry_run else "removed"
    print(f"comment-deleter: {verb} {total} comment(s) across {len(targets)} file(s)")
    return 0


def _baseline_text(cwd: str, path: str, ref: str) -> str:
    content = gitstate.show(cwd, ref, path)
    return "" if content is None else content


def _count(path: str, baseline: str, config) -> int:
    try:
        with open(path, encoding="utf-8") as handle:
            current = handle.read()
    except (OSError, UnicodeDecodeError):
        return 0
    return scrub_text(baseline, current, path, config)[1]


if __name__ == "__main__":
    sys.exit(main())
