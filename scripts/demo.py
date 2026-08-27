#!/usr/bin/env python3
"""Drive the real hooks the way Claude Code does, and show what changes."""

import json
import os
import shutil
import subprocess
import sys
import tempfile

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
PLUGIN_ROOT = os.path.dirname(SCRIPTS)

BEFORE = '''# tolerance chosen to match the Flash-X reference
TOLERANCE = 1e-6


def solve(field):
    return field / TOLERANCE
'''

CLAUDE_WROTE = '''# tolerance chosen to match the Flash-X reference
TOLERANCE = 1e-6


def solve(field):
    """Normalize a field by the tolerance.

    Args:
        field: The field to normalize.

    Returns:
        The normalized field.
    """
    # Divide by the tolerance to avoid blowups.
    # This mirrors the approach we discussed earlier.
    return field / TOLERANCE  # scale it
'''


def run_hook(script, event):
    return subprocess.run(
        [sys.executable, os.path.join(SCRIPTS, script)],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        env={**os.environ, "CLAUDE_PLUGIN_ROOT": PLUGIN_ROOT},
    )


def show(title, body):
    print(f"\n\033[1m{title}\033[0m")
    print("-" * 62)
    print(body if body.endswith("\n") else body + "\n", end="")
    print("-" * 62)


def scenario(name, description):
    print(f"\n\n\033[1;36m### {name}\033[0m\n{description}")


def git(cwd, *arguments):
    subprocess.run(("git", *arguments), cwd=cwd, check=True, capture_output=True)


def edit_scenario(workspace):
    scenario("1. Edit tool", "Claude adds a docstring and three comments to a file.")
    path = os.path.join(workspace, "model.py")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(BEFORE)

    event = {
        "session_id": "demo",
        "cwd": workspace,
        "tool_name": "Edit",
        "tool_input": {"file_path": path},
        "tool_use_id": "toolu_demo_edit",
    }
    run_hook("pre_tool_use.py", event)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(CLAUDE_WROTE)
    show("What Claude wrote", CLAUDE_WROTE)

    completed = run_hook("post_tool_use.py", event)
    with open(path, encoding="utf-8") as handle:
        result = handle.read()
    show("What landed on disk", result)

    if completed.stdout:
        payload = json.loads(completed.stdout)
        show("What Claude was told", payload["hookSpecificOutput"]["additionalContext"])
    return result == BEFORE


def bash_scenario(workspace):
    scenario("2. Bash edit", "Claude appends a commented function with a shell heredoc.")
    git(workspace, "init", "-q")
    git(workspace, "config", "user.email", "demo@example.com")
    git(workspace, "config", "user.name", "Demo")
    path = os.path.join(workspace, "model.py")
    git(workspace, "add", "model.py")
    git(workspace, "commit", "-q", "-m", "initial")

    event = {
        "session_id": "demo",
        "cwd": workspace,
        "tool_name": "Bash",
        "tool_input": {"command": "cat >> model.py"},
        "tool_use_id": "toolu_demo_bash",
    }
    run_hook("pre_tool_use.py", event)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write('\n\ndef scale(field):\n    """Scale a field."""\n    # helper\n    return field * 2\n')
    run_hook("post_tool_use.py", event)

    with open(path, encoding="utf-8") as handle:
        result = handle.read()
    show("What landed on disk", result)
    return "helper" not in result and "Scale a field" not in result


def survival_scenario(workspace):
    scenario("3. Your comments survive", "Claude edits the code under a comment you wrote.")
    path = os.path.join(workspace, "yours.py")
    original = "# my hand-written note about the constant below\nLIMIT = 10\n"
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(original)

    event = {
        "session_id": "demo",
        "cwd": workspace,
        "tool_name": "Edit",
        "tool_input": {"file_path": path},
        "tool_use_id": "toolu_demo_survive",
    }
    run_hook("pre_tool_use.py", event)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("# my hand-written note about the constant below\nLIMIT = 25\n")
    run_hook("post_tool_use.py", event)

    with open(path, encoding="utf-8") as handle:
        result = handle.read()
    show("What landed on disk", result)
    return result == "# my hand-written note about the constant below\nLIMIT = 25\n"


def main():
    workspace = tempfile.mkdtemp(prefix="comment-deleter-demo-")
    try:
        outcomes = {
            "Edit tool": edit_scenario(workspace),
            "Bash edit": bash_scenario(workspace),
            "Your comments survive": survival_scenario(workspace),
        }
    finally:
        shutil.rmtree(workspace, ignore_errors=True)

    print("\n")
    for name, passed in outcomes.items():
        print(f"  {'PASS' if passed else 'FAIL'}  {name}")
    return 0 if all(outcomes.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
