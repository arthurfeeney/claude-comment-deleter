import os
import subprocess

import pytest

from comment_deleter.cli import main


def run_git(cwd, *arguments):
    subprocess.run(("git", *arguments), cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def repository(tmp_path, monkeypatch):
    run_git(tmp_path, "init", "-q")
    run_git(tmp_path, "config", "user.email", "test@example.com")
    run_git(tmp_path, "config", "user.name", "Test")
    (tmp_path / "tracked.py").write_text("# committed\nvalue = 1\n", encoding="utf-8")
    run_git(tmp_path, "add", "tracked.py")
    run_git(tmp_path, "commit", "-q", "-m", "initial")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(tmp_path / "plugin-data"))
    return tmp_path


def test_cli_scrubs_dirty_worktree_against_head(repository, capsys):
    target = repository / "tracked.py"
    target.write_text("# committed\n# new note\nvalue = 2\n", encoding="utf-8")

    assert main([]) == 0
    assert target.read_text(encoding="utf-8") == "# committed\nvalue = 2\n"
    assert "removed 1 comment(s)" in capsys.readouterr().out


def test_cli_dry_run_leaves_the_file_alone(repository, capsys):
    target = repository / "tracked.py"
    modified = "# committed\n# new note\nvalue = 2\n"
    target.write_text(modified, encoding="utf-8")

    assert main(["--dry-run"]) == 0
    assert target.read_text(encoding="utf-8") == modified
    assert "would remove 1 comment(s)" in capsys.readouterr().out


def test_cli_accepts_explicit_paths(repository):
    target = repository / "tracked.py"
    target.write_text("# committed\nvalue = 2  # inline\n", encoding="utf-8")

    assert main([os.fspath(target)]) == 0
    assert target.read_text(encoding="utf-8") == "# committed\nvalue = 2\n"


def test_cli_reports_when_there_is_nothing_to_do(repository, capsys):
    assert main([]) == 0
    assert "nothing to scrub" in capsys.readouterr().out
