# Installation

## Prerequisites

- **Claude Code** with plugin/hook support
- **Python 3.10+**
- **Git** (used for diff generation during reviews)

## Install into a project

From inside the project where you want reviews to run:

```bash
python /path/to/claude-auto-review/claude_auto_review/install/setup_cli.py
```

Replace `/path/to/claude-auto-review` with the actual location of this repo on your machine.

**What it does** (all changes are inside the target project):

1. Creates `.claude/claude-auto-review/` with `scripts/` and `agents/` subdirectories (`clients/` and `reviews/` are created lazily per session).
2. Copies default review rules from the plugin into `.claude/claude-auto-review/rules.md`.
3. Writes runtime shims under `scripts/` that delegate back to the plugin source.
4. Copies `agents/reviewer.md` into `.claude/claude-auto-review/agents/` (overwrites if content differs from the plugin source).
5. Adds hook definitions (`PostToolUse`, `Stop`, `SessionEnd`) to `.claude/settings.json` (additive - existing settings are preserved).
6. Appends runtime paths to `.gitignore`.

The installer is idempotent - running it again won't duplicate entries.

## Uninstall

```bash
python /path/to/claude-auto-review/claude_auto_review/install/cancel_cli.py
```

This removes runtime state for the active session. Delete `.claude/claude-auto-review/` and remove the hook entries from `.claude/settings.json` to fully uninstall.

## Verify it works

1. Start a Claude Code session in the target project.
2. Have Claude edit a tracked file.
3. Check that a new line appeared in `.claude/claude-auto-review/clients/{session-id}/state.jsonl`.
4. When Claude tries to stop, the stop hook will block if any file is unreviewed, then auto-review it.

Hook lifecycle events are logged to `.claude/claude-auto-review/claude-auto-review.log`.
