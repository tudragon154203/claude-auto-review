---
description: Cancel Claude Auto Review runtime state for this project.
---

Run the generated project-local wrapper:

```bash
python .claude/claude-auto-review/scripts/cancel_claude_auto_review.py
```

That wrapper calls `claude_auto_review/install/cancel_cli.py`, which uses `claude_auto_review/runtime/cleanup.py` to clear runtime state.

If the project-local wrapper is not installed yet, run the plugin script directly:

```bash
python claude_auto_review/install/cancel_cli.py
```

