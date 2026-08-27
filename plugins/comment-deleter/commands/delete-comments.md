---
description: Delete comments added or edited in the working tree since a git baseline.
argument-hint: "[--dry-run] [--baseline <ref>] [paths...]"
allowed-tools: Bash(python3 *)
---

Run the comment-deleter pass over the working tree:

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/delete_comments.py" $ARGUMENTS
```

This compares each changed file against the git baseline (`HEAD` by default) and
deletes only the comments that were added or reworded since then. Report which
files changed and how many comments were removed. Do not re-add the comments.
