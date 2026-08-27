# claude-comment-deleter

This is a vibe-coded claude plugin automatically deletes any comments that
Claude writes or modifies. Comments that were already in the file and that 
Claude did not touch are not modified.

This should work for languages that use comments like `//`, `/* */`, `#`, etc.
It should also work for python docstrings using multiline strings `""" """`.

```
Why are claude's comments bad?
1. function docs often get way too huge and become basically nonsensical, especially if
   claude iterates on the same function multipe times.
2. claude's prose has gotten extremely bad...
3. claude's code is actually fairly readable, so a lot of explanations are pointless.
4. if some piece of code is really confusing... you can just ask claude
   to explain it...
5. claude's comments often reference the discussion or previous code that
   no longer exists..., which isn't very useful for people trying to understand
   the current code.
6. I suspect (but have no real evidence) that comments can waste context space...
7. The comments are sometimes wrong.
```

I have not found a way to force claude to write better comments, or
simply not less comments. Skill files and CLAUDE.md have not worked well in my experience.

This will also delete any modified comments. Even if they were originally written by a human.
I am assuming that if a comment is modified, the content of whatever it is documenting were
also modified and thus the original comment may be invalid now anyway...

## Example

Lets say we have a function that squares it input

```python
def square(a):
    return a ** 2
```

If we ask claude to go through and add type hints, it may try modify it like this:

```python
def square_claudified(a: Number) -> Number:
    """ Compute the square of the input ``a``, using type hints to make
    the resolve the real issue of function legibility: people should understand 
    the load-bearing input/output contract.
    Args:
        a: the load-bearing python Number that will be squared
    Returns:
        the square of the input Number ``a``
    """
    return a ** 2 # compute the square of a using the load-bearing operation ``**``
```

This plugin automatically cleans it up so the output will look like

```python
def square_claudified(a: Number) -> Number:
    return a ** 2
```

## Requirements

`python3` on `PATH`. No third-party packages — the hooks are stdlib only.

## Install

This repository is a **plugin marketplace** (`.claude-plugin/marketplace.json` at
the root) that publishes one plugin, `comment-deleter`, from
`plugins/comment-deleter/`. That is what makes it installable rather than a
loose skills directory.

### From GitHub

```bash
claude plugin marketplace add arthurfeeney/claude-comment-deleter
claude plugin install comment-deleter@afeeney-plugins
```

### From a local clone

```bash
claude plugin marketplace add /path/to/claude-comment-deleter
claude plugin install comment-deleter@afeeney-plugins
```

Add `--scope project` to the install to enable it only in the current repo
instead of user-wide.

### Without the CLI

If `claude` is not on your PATH — the desktop app, for instance — register the
marketplace and enable the plugin directly in `~/.claude/settings.json`:

```json
{
  "extraKnownMarketplaces": {
    "afeeney-plugins": {
      "source": {
        "source": "github",
        "repo": "arthurfeeney/claude-comment-deleter"
      }
    }
  },
  "enabledPlugins": {
    "comment-deleter@afeeney-plugins": true
  }
}
```

For a local checkout, swap the source for
`{ "source": "directory", "path": "/path/to/claude-comment-deleter" }`. The key
under `extraKnownMarketplaces` must match the `name` in `marketplace.json`.

To scope it to one project, put the same `enabledPlugins` entry in that repo's
`.claude/settings.json` (committed, for the team) or `.claude/settings.local.json`
(personal, gitignored). Settings load user → project → local, so a `false` in a
local file overrides a `true` from the project.

### Managing it

```bash
claude plugin list
claude plugin details comment-deleter@afeeney-plugins
claude plugin disable comment-deleter@afeeney-plugins
claude plugin marketplace update afeeney-plugins
```

Changes to a locally-sourced plugin are picked up with `/reload-plugins`, or by
restarting the session where that command is unavailable.

### Repository layout

```
claude-comment-deleter/
├── .claude-plugin/
│   └── marketplace.json          # the marketplace: lists the plugin below
├── plugins/
│   └── comment-deleter/          # the plugin itself
│       ├── .claude-plugin/
│       │   └── plugin.json
│       ├── hooks/hooks.json
│       ├── commands/
│       ├── scripts/
│       └── src/comment_deleter/
├── test/                         # not shipped with the plugin
└── README.md
```

A `.claude-plugin/` directory may contain `plugin.json` **or**
`marketplace.json`, never both — which is why the plugin lives one level down.

Two things bit us building this, both worth knowing if you fork it:

- `hooks/hooks.json` at the standard path is loaded **automatically**. Declaring
  `"hooks": "./hooks/hooks.json"` in `plugin.json` as well makes the loader read
  the same file twice and fail with "Duplicate hooks file detected". The manifest
  `hooks` key is only for *additional* hook files outside the standard path.
- The marketplace is resolved from what is **pushed**, not your working tree. A
  `marketplace.json` that exists only locally produces "Marketplace file not
  found" on `plugin marketplace add`.

## Verifying it works

### Without installing anything

The demo drives the real hook scripts with the same JSON Claude Code feeds them,
against a throwaway git repo, and prints what Claude wrote next to what actually
landed on disk:

```bash
python3 plugins/comment-deleter/scripts/demo.py
```

It covers an `Edit` call, a `Bash` heredoc append, and a comment of your own
surviving an edit to the line under it, then prints PASS/FAIL for each. Nothing
outside the temp directory is touched.

For the full suite:

```bash
python3 -m pytest test/
```

### On a file you care about

Point the manual pass at real work without writing anything:

```bash
python3 plugins/comment-deleter/scripts/delete_comments.py --dry-run
```

That reports what it *would* remove from your dirty worktree, compared against
`HEAD`. Use `--baseline main` to widen the window. Drop `--dry-run` when the
report looks right.

### In a live session

After installing, ask Claude to write something it will inevitably comment:

> add a function to this file that computes a rolling mean

Three things tell you the hook fired:

1. The comments and docstring are simply absent from the file.
2. The transcript shows `comment-deleter: removed N new comment(s) in <file>`.
3. Claude does not try to put them back, because it was told they were removed.

Now add a comment yourself, ask Claude to edit the line beneath it, and confirm
yours is still there. That is the behaviour that distinguishes this from a
blanket comment stripper.

If nothing happens, work down this list:

```bash
claude plugin list                    # is comment-deleter@skills-dir loaded?
/reload-plugins                       # pick up changes without restarting
echo $CLAUDE_COMMENT_DELETER          # "off" disables everything
python3 -c "import sys; print(sys.version)"   # hooks need python3 on PATH
```

Hooks swallow their own errors so they can never block a tool call, which also
means failures are quiet. To surface one, run both hooks by hand and read stderr.
The order matters: `post` only acts on a file that `pre` snapshotted first.

```bash
PLUGIN="$PWD/plugins/comment-deleter"
EVENT='{"session_id":"dbg","cwd":"'"$PWD"'","tool_name":"Edit","tool_input":{"file_path":"'"$PWD"'/some_file.py"},"tool_use_id":"t1"}'

echo "$EVENT" | CLAUDE_PLUGIN_ROOT="$PLUGIN" python3 "$PLUGIN/scripts/pre_tool_use.py"
# ...edit some_file.py, adding a comment...
echo "$EVENT" | CLAUDE_PLUGIN_ROOT="$PLUGIN" python3 "$PLUGIN/scripts/post_tool_use.py"
```

Silence from the second command means nothing was removed. A `comment-deleter:`
line on stderr is the hook reporting why it bailed.

## Usage

There is nothing to run. Once loaded, every file-modifying tool call is wrapped,
and comments Claude writes are gone before you ever see them.

When something is removed, the transcript shows a line like:

```
comment-deleter: removed 3 new comment(s) in src/model.py
```

Claude is told the same thing, so it does not re-add the comments or treat the
file as unexpectedly modified.

### What it looks like

You have this file, with a comment you wrote:

```python
# tolerance chosen to match the Flash-X reference
TOLERANCE = 1e-6

def solve(field):
    return field / TOLERANCE
```

Claude edits it and, as usual, decorates the change:

```python
# tolerance chosen to match the Flash-X reference
TOLERANCE = 1e-6

def solve(field):
    """Normalize a field by the tolerance.

    Args:
        field: The field to normalize.

    Returns:
        The normalized field.
    """
    # This mirrors the approach we discussed earlier.
    return field / TOLERANCE  # divide by tolerance
```

What lands on disk:

```python
# tolerance chosen to match the Flash-X reference
TOLERANCE = 1e-6

def solve(field):
    return field / TOLERANCE
```

Your comment is untouched. The docstring and both of Claude's comments are gone.

### Turning it off

For one session, no config file needed:

```bash
export CLAUDE_COMMENT_DELETER=off
```

Permanently for one project, in `.comment-deleter.json`:

```json
{ "enabled": false }
```

### Manual pass

To scrub comments added since a git ref without waiting for a hook — useful for
cleaning up work done before you installed the plugin:

```bash
python3 plugins/comment-deleter/scripts/delete_comments.py --dry-run
```

Drop `--dry-run` to write. With no arguments it scrubs the dirty worktree against
`HEAD`. Pass explicit paths to limit it, or `--baseline main` to compare against
another ref:

```bash
python3 plugins/comment-deleter/scripts/delete_comments.py --baseline main src/
```

The `/delete-comments` slash command wraps the same script.

## How it works

The plugin is a pair of hooks around every file-modifying tool call:

| Step | Event | What happens |
| --- | --- | --- |
| 1 | `PreToolUse` | Snapshot the file's exact content before Claude touches it. |
| 2 | Claude edits | `Edit`, `Write`, or a shell command changes the file. |
| 3 | `PostToolUse` | Diff against the snapshot, delete the new comments, rewrite the file. |
| 4 | `PostToolUse` output | Tell Claude what was removed so it doesn't re-add or get confused. |

A comment is deleted only if **both** are true:

1. It sits on a line the edit inserted or replaced, and
2. its exact text was not already somewhere in the pre-edit file.

The second rule is what keeps your comments safe. If Claude changes
`value = 1  # keeps the answer` to `value = 42  # keeps the answer`, the comment
text is unchanged, so it survives. Reindenting or moving an existing comment
survives too. Rewording it does not.

Writes are atomic (temp file plus `os.replace`) and preserve the file's mode and
its CRLF line endings. If either hook throws, it exits 0 and the tool call
proceeds untouched — the scrubber can fail, but it cannot block your work.

### Docstrings and other unused strings

A Python docstring is not a comment, so it needs its own rule. The plugin deletes
a string only when it is a **bare expression statement** — a string that is
evaluated and thrown away. In AST terms that is an `ast.Expr` wrapping a string
`Constant`. If the string were assigned, passed to a function, or returned it
would be an `Assign`, `Call`, or `Return` node instead, and it is left alone:

```python
"""Deleted: nobody's value."""

DOC = """Kept: assigned."""
parser.add_argument("--flag", help="""Kept: passed to a call.""")

def describe():
    return """Kept: returned."""
```

This covers module, class, and function docstrings, plus stray triple-quoted
blocks used as pseudo-comments. The same two rules as comments apply: the
docstring must sit on a touched line and its text must not already exist in the
pre-edit file, so a docstring you wrote survives Claude editing the function
under it.

Two cases get special handling:

- **A body that would be left empty** gets `pass`, so `class Failure(Exception):`
  with only a docstring becomes `class Failure(Exception): pass` rather than a
  syntax error. Function, class, `if`, `else`, `try`, `except`, and `finally`
  blocks are all covered.
- **A file that reads its own `__doc__`** — the `argparse.ArgumentParser(
  description=__doc__)` pattern — keeps all of its docstrings, because there the
  docstring genuinely is a value.

Docstrings containing doctests (`>>> `) are preserved: they are executable tests,
not prose. f-strings and `b""` byte strings are never touched. Set
`"strip_docstrings": false` to turn the whole behaviour off.

### Shell edits are covered too

Claude often edits files with `sed`, `python -c`, or a heredoc rather than the
`Edit` tool. For `Bash` calls the plugin snapshots the dirty files in the git
working tree beforehand, then compares each changed file against that snapshot —
or against `HEAD` for a file that was clean, or against nothing for a file the
command created. Outside a git repository, shell edits are skipped.

## What survives on purpose

Comment syntax is not always prose. These are preserved by default, because
deleting them changes what the code does:

- Shebangs (`#!/usr/bin/env python3`) and Python encoding cookies
- License and provenance headers: `SPDX-License-Identifier`, `Copyright`, `@license`, `DO NOT EDIT`, `@generated`
- Linter and type-checker pragmas: `# noqa`, `# type: ignore`, `# pylint:`, `# mypy:`, `# ruff:`, `# fmt: off`, `# nosec`
- Formatter and bundler directives: `// eslint-disable`, `// prettier-ignore`, `// @ts-ignore`, `/// <reference`, `// clang-format off`, `// NOLINT`
- Build constraints: `//go:build`, `// +build`, `// shellcheck disable`, `// rustfmt::skip`
- Docstrings holding doctests (`>>> `), and every docstring in a file that reads `__doc__`
- Anything containing `comment-deleter: keep`

Set `"preserve_directives": false` to delete these too.

## Supported languages

Python, C/C++/CUDA/Objective-C, Java, Kotlin, Scala, Swift, C#, JavaScript,
TypeScript, JSX/TSX, Go, Rust, shell, YAML, TOML, Ruby, Perl, R, Julia, Elixir,
Nix, Terraform, SQL, Lua, Haskell, HTML/XML/Vue/Svelte, CSS/SCSS/Less, LaTeX,
Dockerfile, Makefile, PHP, Vim.

Markdown, reStructuredText, plain text, JSON, and notebooks are never touched.

The scanners are string-aware, so markers inside string literals are safe:
`"https://x/#frag"`, JS template literals — including nested ones like
`` `${fn(`https://x`)}` `` — and regex literals (`/a\/\/b/`), shell heredocs and
`${#array[@]}`, Rust lifetimes (`&'a str`), and C character literals (`'/'`) are
all handled. After scrubbing a Python file the result is re-parsed with `ast`; if
it no longer compiles, the edit is reverted.

## Configuration

Optional `.comment-deleter.json` in the project root, or
`~/.claude/comment-deleter.json` for user-wide defaults. Project values win.

```json
{
  "enabled": true,
  "preserve_directives": true,
  "strip_docstrings": true,
  "scrub_bash_edits": true,
  "max_bash_files": 200,
  "exclude_globs": ["**/node_modules/**", "**/vendor/**"],
  "exclude_extensions": [".yaml", ".yml"],
  "preserve_patterns": ["TODO\\(", "^\\s*#\\s*Section:"]
}
```

| Key | Default | Meaning |
| --- | --- | --- |
| `enabled` | `true` | Master switch. |
| `preserve_directives` | `true` | Keep shebangs, license headers, tool pragmas, and doctests. |
| `strip_docstrings` | `true` | Also delete Python docstrings and other bare strings. |
| `scrub_bash_edits` | `true` | Also scrub files changed by `Bash` commands. |
| `max_bash_files` | `200` | Skip the `Bash` pass if the worktree is dirtier than this. |
| `exclude_globs` | vendor dirs | Paths never scrubbed. Replaces the default list. |
| `exclude_extensions` | `[]` | Extra extensions to leave alone. |
| `preserve_patterns` | `[]` | Regexes; a matching comment is kept. |

The default `exclude_globs` cover `node_modules`, `.venv`, `venv`, `vendor`,
`third_party`, `site-packages`, `.git`, `dist`, and `build`. Setting the key
replaces that list rather than adding to it.

## Tests

```bash
python3 -m pytest test/
```

94 unit and end-to-end tests, including the hook scripts driven over real stdin
JSON and the `Bash` path driven against a real git repository.

They are backed by a corpus check, because a bad scanner deletes *code*:

| Corpus | Removed | Invariant checked |
| --- | --- | --- |
| 129 real Python files | 1,317 | AST identical once bare strings are normalized away on both sides |
| 991 real JavaScript files | 14,372 | all still pass `node --check` |
| 7 real shell scripts | 242 | all still pass `bash -n` |

The Python invariant is the strict one: strip every bare string statement from
both the original and the scrubbed AST, and the two dumps must match exactly. That
proves the scrub removed comments and unused strings and touched nothing else. No
file broke and no file changed semantically.

The JavaScript corpus is what caught the nested-template-literal bug, where
`` `${fn(`https://x`)}` `` closed the outer template early and left a URL in code
mode, so `//` read as a comment and real code was deleted.

## Limits

- Deleting a docstring sets `__doc__` to `None`. If something reads it at runtime
  through a path the `__doc__` text check misses — Sphinx builds, `click` and
  `typer` help text, FastAPI endpoint descriptions — that text is gone. Set
  `"strip_docstrings": false` in those projects.
- A file whose entire content is one module docstring is left alone, because
  scrubbing it would empty the file and the empty-output guard reverts.
- A file edited by a shell command outside a git repository is not scrubbed.
- Files larger than 2 MB are skipped, as are snapshots over 8 MB. Stale snapshots
  are pruned after 6 hours.
- JavaScript regex-literal detection is heuristic. An exotic literal can hide a
  real comment from deletion; it never deletes code, so the failure mode is a
  comment that survives.
- The plugin has not been exercised inside a live Claude Code session — the hooks
  are tested by feeding the scripts the documented stdin JSON directly.
