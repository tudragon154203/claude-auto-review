# Claude Auto Review

Claude Auto Review is a Claude Code plugin that tracks files edited during a session and blocks session stop until each changed file has a review pass. It is intentionally diff-focused.

## How It Works

### Edit Tracking

The `PostToolUse` hook runs after Write/Edit/MultiEdit/Delete/Remove operations. It records each changed file's path and SHA-256 hash in `.claude/claude-auto-review/clients/{client-id}/state.jsonl`. Each edit appends a JSON object:

```json
{"type": "edit", "file": "src/main.py", "hash": "a1b2c3d4", "timestamp": "2026-05-09T10:00:00Z", "reviewed": false}
```

Deleted files are tracked with the special hash `__deleted__`.

File extension filtering:
- If `includeExtensions` is non-empty, only matching extensions are tracked.
- Files matching `skipExtensions` are always excluded.

### Stop Blocking

When Claude tries to end the session, the `Stop` hook:

1. Loads the latest hash per file from state.
2. Checks whether each hash has been marked `reviewed: true`.
3. If any hash is unreviewed, creates a review prompt and blocks stop (exit code 2) with feedback containing the review file location.
4. If the `claude` CLI is available, spawns a sub-agent to auto-complete the review.
5. Circuit breaker: after `maxStopPasses` consecutive blocks (default 3), allows stop regardless.
6. Pending reviews expire after `pendingReviewTimeoutHours` (default 1 hour).

### Configuration

Settings are stored in `.claude/settings.json` under the `claude-auto-review` key:

| Setting | Default | Description |
|---------|---------|-------------|
| `enabled` | `true` | Enable/disable the plugin |
| `rulesFile` | `.claude/claude-auto-review/rules.md` | Path to project review rules |
| `includeExtensions` | `[]` | Only track files with these extensions (empty = all) |
| `skipExtensions` | `[]` | Never track files with these extensions |
| `minSeverity` | `MEDIUM` | Minimum severity for findings |
| `autoFix` | `true` | Allow auto-fix of findings |
| `maxStopPasses` | `3` | Circuit breaker threshold |
| `pendingReviewTimeoutHours` | `1` | Hours before pending reviews expire |

## Commands

- `/claude-auto-review` — Manually run the review prompt generator for unreviewed files
- `/cancel-claude-auto-review` — Cancel all runtime state for this project

## Runtime Files

### Commit-friendly (project rules)

```text
.claude/claude-auto-review/rules.md
```

### Local runtime (gitignored)

```text
.claude/claude-auto-review/clients/
.claude/claude-auto-review/clients/{client-id}/run/
.claude/claude-auto-review/clients/{client-id}/reviews/
.claude/claude-auto-review/scripts/
.claude/claude-auto-review/agents/
.claude/claude-auto-review/claude-auto-review.log
```

## Logging

Lifecycle events are written to `.claude/claude-auto-review/claude-auto-review.log`. Key events:

| Event | Meaning |
|-------|---------|
| `post_tool_use_skipped_file` | File matched `skipExtensions` |
| `stop_approved` | Stop allowed |
| `stop_blocked` | Stop blocked, review pending |
| `stop_review_expired` | Pending review timed out and was skipped |
| `circuit_breaker` | Circuit breaker threshold reached, stop allowed |
| `stop_hook_claude_cli_done` | Auto-completion sub-agent completed |
| `expired_reviews_cleaned` | Stale pending reviews purged |

## Testing

```bash
python -m unittest discover -s tests
```

Test suites:
- `tests/test_rules.py` — Rules and configuration
- `tests/test_integration.py` — Cross-function state interactions
- `tests/test_concurrency.py` — Client/session isolation
- `tests/test_e2e.py` — Full lifecycle via subprocesses
