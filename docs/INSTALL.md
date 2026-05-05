# Install

## Prerequisites

- Claude Code with plugin support
- Node.js 18 or newer
- Git for diff generation

## Plugin Install

Install the plugin through Claude Code using the repository marketplace flow, then verify `.claude-plugin/plugin.json` is detected.

## Manual Install

From a target project:

```bash
node path/to/claude-auto-review/scripts/setup-claude-auto-review.js
```

Then add the hook definitions from `hooks/hooks.json` to the target project's Claude settings, adjusting command paths if needed.

## Verify

After Claude edits a tracked file, the post tool hook should append a JSON line to:

```text
.claude/claude-auto-review/state.jsonl
```

When Claude tries to stop, the stop hook should return exit code `2` with a JSON block message until the review prompt script has been run.
