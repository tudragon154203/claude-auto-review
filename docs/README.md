# Claude Auto Review

Claude Auto Review is a Claude Code plugin that tracks files changed by Claude and blocks session stop until those changed hashes have a review pass.

It is intentionally diff-focused:

- `PostToolUse` records changed file hashes in `.claude/claude-auto-review/state.jsonl`.
- `Stop` checks the latest hash for each edited file.
- If any latest hash is unreviewed, the stop hook blocks and tells Claude to run the review prompt script.
- The prompt script writes a review request under `.claude/claude-auto-review/run/`, initializes a review file under `.claude/claude-auto-review/reviews/`, and marks the reviewed snapshot.
- Any fixes create new hashes and trigger another review cycle.
- Runtime events are logged to `.claude/claude-auto-review/claude-auto-review.log`.

## Quick Start

```bash
python -m unittest discover -s tests
python scripts/setup_claude_auto_review.py
```

For plugin installation, use `.claude-plugin/plugin.json`. For manual hook wiring, use `hooks/hooks.json` as the project settings template.

## Runtime Files

Committed project rules live at:

```text
.claude/claude-auto-review/rules.md
```

Local runtime files should stay ignored:

```text
.claude/claude-auto-review/state.jsonl
.claude/claude-auto-review/run/
.claude/claude-auto-review/reviews/
.claude/claude-auto-review/claude-auto-review.log
```

## Configuration

Project overrides can be added to `.claude/settings.json`:

```json
{
  "claude-auto-review": {
    "enabled": true,
    "rulesFile": ".claude/claude-auto-review/rules.md",
    "includeExtensions": ["py", "ts", "tsx"],
    "skipExtensions": ["md", "json", "yaml", "yml", "css", "scss"],
    "minSeverity": "MEDIUM",
    "autoFix": true
  }
}
```

`enabled`, `includeExtensions`, and `skipExtensions` are enforced by the current hooks. If `includeExtensions` is non-empty, only matching extensions are tracked. `skipExtensions` always excludes matching files. `minSeverity` and `autoFix` are documented for reviewer behavior and future native agent dispatch.

## Cancel Runtime State

```bash
python scripts/cancel_claude_auto_review.py
```

In an initialized project, use:

```bash
python .claude/claude-auto-review/scripts/cancel_claude_auto_review.py
```
