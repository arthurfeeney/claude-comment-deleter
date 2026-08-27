#!/usr/bin/env python3
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _bootstrap import read_event  # noqa: E402

GUIDANCE = (
    "The comment-deleter plugin removed {total} comment(s) you just wrote or edited "
    "in {summary}. The files on disk no longer contain them. This is expected and "
    "correct: do not re-add the comments, and do not treat the files as unexpectedly "
    "modified. Pre-existing comments you did not touch were left alone."
)


def main() -> int:
    event = read_event()
    try:
        from comment_deleter.runner import run_post

        results = run_post(event)
    except Exception as error:  # a scrub failure must not fail the tool call
        print(f"comment-deleter: scrub skipped ({error})", file=sys.stderr)
        return 0

    if not results:
        return 0

    total = sum(results.values())
    cwd = event.get("cwd") or os.getcwd()
    summary = ", ".join(sorted(os.path.relpath(path, cwd) for path in results))
    message = GUIDANCE.format(total=total, summary=summary)
    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": message,
            },
            "systemMessage": f"comment-deleter: removed {total} new comment(s) in {summary}",
        },
        sys.stdout,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
