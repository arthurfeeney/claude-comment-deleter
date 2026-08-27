#!/usr/bin/env python3
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _bootstrap import read_event  # noqa: E402


def main() -> int:
    event = read_event()
    try:
        from comment_deleter.runner import run_pre

        run_pre(event)
    except Exception as error:  # never let the scrubber block a tool call
        print(f"comment-deleter: snapshot skipped ({error})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
