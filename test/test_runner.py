import json
import os
import subprocess
import sys

import pytest

from comment_deleter.runner import run_post, run_pre

PLUGIN_ROOT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "plugins", "comment-deleter"
)


@pytest.fixture(autouse=True)
def isolated_snapshots(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(tmp_path / "plugin-data"))
    monkeypatch.delenv("CLAUDE_COMMENT_DELETER", raising=False)


def edit_event(cwd, path, tool="Edit"):
    return {
        "session_id": "session-1",
        "cwd": str(cwd),
        "tool_name": tool,
        "tool_input": {"file_path": str(path)},
        "tool_use_id": "toolu_1",
    }


def test_edit_flow_deletes_only_the_new_comment(tmp_path):
    source = tmp_path / "module.py"
    source.write_text("# original\nvalue = 1\n", encoding="utf-8")
    event = edit_event(tmp_path, source)

    run_pre(event)
    source.write_text("# original\n# claude added this\nvalue = 2\n", encoding="utf-8")
    results = run_post(event)

    assert source.read_text(encoding="utf-8") == "# original\nvalue = 2\n"
    assert results == {str(source): 1}


def test_write_of_a_new_file_deletes_every_comment(tmp_path):
    source = tmp_path / "fresh.py"
    event = edit_event(tmp_path, source, tool="Write")

    run_pre(event)
    source.write_text("# a\nvalue = 1  # b\n", encoding="utf-8")
    run_post(event)

    assert source.read_text(encoding="utf-8") == "value = 1\n"


def test_post_without_a_snapshot_is_a_no_op(tmp_path):
    source = tmp_path / "module.py"
    source.write_text("# untouched\nvalue = 1\n", encoding="utf-8")

    assert run_post(edit_event(tmp_path, source)) == {}
    assert source.read_text(encoding="utf-8") == "# untouched\nvalue = 1\n"


def test_disabled_by_environment_variable(tmp_path, monkeypatch):
    source = tmp_path / "module.py"
    source.write_text("value = 1\n", encoding="utf-8")
    event = edit_event(tmp_path, source)
    run_pre(event)
    source.write_text("# added\nvalue = 1\n", encoding="utf-8")

    monkeypatch.setenv("CLAUDE_COMMENT_DELETER", "off")
    assert run_post(event) == {}
    assert source.read_text(encoding="utf-8") == "# added\nvalue = 1\n"


def test_project_config_can_disable_the_plugin(tmp_path):
    (tmp_path / ".comment-deleter.json").write_text('{"enabled": false}', encoding="utf-8")
    source = tmp_path / "module.py"
    source.write_text("value = 1\n", encoding="utf-8")
    event = edit_event(tmp_path, source)
    run_pre(event)
    source.write_text("# added\nvalue = 1\n", encoding="utf-8")

    assert run_post(event) == {}


def test_file_permissions_are_preserved(tmp_path):
    source = tmp_path / "script.py"
    source.write_text("value = 1\n", encoding="utf-8")
    source.chmod(0o755)
    event = edit_event(tmp_path, source)

    run_pre(event)
    source.write_text("# added\nvalue = 1\n", encoding="utf-8")
    run_post(event)

    assert source.stat().st_mode & 0o777 == 0o755


def run_git(cwd, *arguments):
    subprocess.run(("git", *arguments), cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def git_repository(tmp_path):
    run_git(tmp_path, "init", "-q")
    run_git(tmp_path, "config", "user.email", "test@example.com")
    run_git(tmp_path, "config", "user.name", "Test")
    (tmp_path / "tracked.py").write_text("# committed note\nvalue = 1\n", encoding="utf-8")
    run_git(tmp_path, "add", "tracked.py")
    run_git(tmp_path, "commit", "-q", "-m", "initial")
    return tmp_path


def bash_event(cwd):
    return {
        "session_id": "session-1",
        "cwd": str(cwd),
        "tool_name": "Bash",
        "tool_input": {"command": "true"},
        "tool_use_id": "toolu_bash",
    }


def test_bash_edit_to_a_clean_tracked_file_is_scrubbed(git_repository):
    event = bash_event(git_repository)
    run_pre(event)

    target = git_repository / "tracked.py"
    target.write_text("# committed note\n# bash added this\nvalue = 2\n", encoding="utf-8")
    results = run_post(event)

    assert target.read_text(encoding="utf-8") == "# committed note\nvalue = 2\n"
    assert results == {str(target): 1}


def test_bash_created_file_loses_all_comments(git_repository):
    event = bash_event(git_repository)
    run_pre(event)

    target = git_repository / "created.py"
    target.write_text("# brand new\nvalue = 1\n", encoding="utf-8")
    run_post(event)

    assert target.read_text(encoding="utf-8") == "value = 1\n"


def test_bash_leaves_pre_existing_uncommitted_comments_alone(git_repository):
    target = git_repository / "tracked.py"
    target.write_text("# committed note\n# user wrote this\nvalue = 1\n", encoding="utf-8")

    event = bash_event(git_repository)
    run_pre(event)
    target.write_text(
        "# committed note\n# user wrote this\nvalue = 1\nextra = 2\n", encoding="utf-8"
    )
    run_post(event)

    assert target.read_text(encoding="utf-8") == (
        "# committed note\n# user wrote this\nvalue = 1\nextra = 2\n"
    )


def test_bash_outside_a_git_repository_is_a_no_op(tmp_path):
    source = tmp_path / "module.py"
    source.write_text("value = 1\n", encoding="utf-8")
    event = bash_event(tmp_path)
    run_pre(event)
    source.write_text("# added\nvalue = 1\n", encoding="utf-8")

    assert run_post(event) == {}
    assert source.read_text(encoding="utf-8") == "# added\nvalue = 1\n"


def run_hook(script, event):
    return subprocess.run(
        (sys.executable, os.path.join(PLUGIN_ROOT, "scripts", script)),
        input=json.dumps(event),
        capture_output=True,
        text=True,
        env={**os.environ, "CLAUDE_PLUGIN_ROOT": PLUGIN_ROOT},
    )


def test_hook_scripts_run_end_to_end(tmp_path):
    source = tmp_path / "module.py"
    source.write_text("value = 1\n", encoding="utf-8")
    event = edit_event(tmp_path, source)

    assert run_hook("pre_tool_use.py", event).returncode == 0
    source.write_text("# added by claude\nvalue = 1\n", encoding="utf-8")
    completed = run_hook("post_tool_use.py", event)

    assert completed.returncode == 0
    assert source.read_text(encoding="utf-8") == "value = 1\n"
    payload = json.loads(completed.stdout)
    assert payload["hookSpecificOutput"]["hookEventName"] == "PostToolUse"
    assert "module.py" in payload["hookSpecificOutput"]["additionalContext"]


def test_hook_script_stays_silent_when_nothing_is_removed(tmp_path):
    source = tmp_path / "module.py"
    source.write_text("value = 1\n", encoding="utf-8")
    event = edit_event(tmp_path, source)

    run_hook("pre_tool_use.py", event)
    source.write_text("value = 2\n", encoding="utf-8")
    completed = run_hook("post_tool_use.py", event)

    assert completed.returncode == 0
    assert completed.stdout == ""


def test_hook_script_survives_malformed_input():
    completed = subprocess.run(
        (sys.executable, os.path.join(PLUGIN_ROOT, "scripts", "post_tool_use.py")),
        input="not json",
        capture_output=True,
        text=True,
        env={**os.environ, "CLAUDE_PLUGIN_ROOT": PLUGIN_ROOT},
    )
    assert completed.returncode == 0


def test_crlf_file_keeps_its_line_endings_on_disk(tmp_path):
    source = tmp_path / "module.py"
    source.write_bytes(b"value = 1\r\n")
    event = edit_event(tmp_path, source)

    run_pre(event)
    source.write_bytes(b"# added\r\nvalue = 1\r\nother = 2\r\n")
    run_post(event)

    assert source.read_bytes() == b"value = 1\r\nother = 2\r\n"


def test_oversized_files_are_skipped(tmp_path, monkeypatch):
    import comment_deleter.runner as runner_module

    monkeypatch.setattr(runner_module, "MAX_SCRUB_BYTES", 16)
    source = tmp_path / "module.py"
    source.write_text("value = 1\n", encoding="utf-8")
    event = edit_event(tmp_path, source)

    run_pre(event)
    large = "# added\n" + "value = 1\n" * 10
    source.write_text(large, encoding="utf-8")
    run_post(event)

    assert source.read_text(encoding="utf-8") == large
