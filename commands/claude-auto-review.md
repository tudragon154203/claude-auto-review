---
description: Run Claude Auto Review for files changed since the last review.
---

Run the generated project-local wrapper:

```bash
python .claude/claude-auto-review/scripts/review_prompt.py
```

That wrapper calls `scripts/review_prompt.py`, which uses `scripts/review_prompt_flow.py` to build the prompt and initialize the review file.

If the project-local wrapper is not installed yet, run the plugin script directly from the plugin checkout.

Then read the generated prompt, complete the initialized review file, and fix any agreed CRITICAL or HIGH findings before stopping.
