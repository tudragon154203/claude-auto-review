# Installation

## CLI Commands

| Command | Description |
| --- | --- |
| `claude-auto-review install` | Set up the plugin in the current project |
| `claude-auto-review cancel` | Cancel the active review session |
| `claude-auto-review prompt` | Manually trigger review prompt generation |
| `claude-auto-review uninstall` | Remove plugin from current project |

## Prerequisites

- **Claude Code** with plugin/hook support
- **Python 3.10+**
- **Git** (used for diff generation during reviews)

## Option A: pip install (recommended)

```bash
# Install from this repo (editable)
pip install -e /path/to/claude-auto-review

# Or install from git
pip install git+https://github.com/<user>/claude-auto-review.git
```

Then initialize the plugin in any project:

```bash
claude-auto-review install
```

This creates the local runtime tree and configures hooks. Run it from the project root where you want reviews to run.

## Option B: Run from a checkout

From inside the project where you want reviews to run:

```bash
pip install -e /path/to/claude-auto-review
claude-auto-review install
```

**What the installer does** (all changes are inside the target project):

1. Creates `.claude/claude-auto-review/` with `scripts/`, `agents/`, and `clients/` subdirectories (`clients/*/reviews/` and `clients/*/run/` are created lazily per session).
2. Copies default review rules from the plugin into `.claude/claude-auto-review/review-rules.md`.
3. Writes runtime shims under `scripts/` that delegate to the installed package.
4. Copies `agents/reviewer.md` into `.claude/claude-auto-review/agents/` (overwrites if content differs from the plugin source).
5. Adds hook definitions (`PostToolUse`, `Stop`, `SessionEnd`) to `.claude/settings.json` (additive — existing settings are preserved).
6. Appends runtime paths to `.gitignore`.

The installer is idempotent — running it again won't duplicate entries.

## Uninstall

```bash
claude-auto-review uninstall
```

This removes the `.claude/claude-auto-review/` directory, strips plugin hook entries from `.claude/settings.json`, and removes the gitignore entry.

## Verify it works

1. Start a Claude Code session in the target project.
2. Have Claude edit a tracked file.
3. Check that a new line appeared in the per-client event log at `.claude/claude-auto-review/clients/{session-id}/state.jsonl`.
4. When Claude tries to stop with unreviewed files, the stop hook first classifies the parent Claude session's last assistant message.
5. If the classifier returns `incomplete`, stop is allowed to continue without invoking review generation.
6. Otherwise, the stop hook continues into the normal review flow and will block until the unreviewed changes are reviewed.

Hook lifecycle events are logged to `.claude/claude-auto-review/claude-auto-review.log`.
