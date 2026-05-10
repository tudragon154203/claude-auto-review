---
description: Cancel Claude Auto Review runtime state for this project.
---

Run the generated project-local wrapper:

```bash
python .claude/claude-auto-review/scripts/cancel_claude_auto_review.py
```

That wrapper calls `scripts/cancel_claude_auto_review.py`, which uses `scripts/runtime_cleanup.py` to clear runtime state.

If the project-local wrapper is not installed yet, run the plugin script directly:

```bash
python scripts/cancel_claude_auto_review.py
```
