# Install

## Prerequisites

- Claude Code with plugin support
- Python 3.10 or newer
- Git for diff generation

## Plugin Installation

Install via Claude Code's plugin marketplace. The plugin manifest at `.claude-plugin/plugin.json` is automatically detected.

## Manual Installation

From a target project:

```bash
python path/to/claude-auto-review/scripts/setup_claude_auto_review.py
```

The installer:

1. Creates `.claude/claude-auto-review/` runtime directory
2. Copies default rules to `.claude/claude-auto-review/rules.md`
3. Creates `scripts/` and `agents/` shim directories
4. Adds plugin settings to `.claude/settings.json`
5. Appends runtime paths to `.gitignore`

**Note:** If using Claude Code's plugin marketplace, the hooks are configured automatically from the manifest. For completely manual setups, add hook definitions from `hooks/hooks.json` to `.claude/settings.json`.

## Verify Installation

After Claude edits a tracked file, the post-tool hook appends a JSON line to:

```text
.claude/claude-auto-review/clients/{client-id}/state.jsonl
```

When Claude tries to stop with unreviewed files, the stop hook returns exit code `2` with a blocking message containing the review file location.

Hook lifecycle events are logged to:

```text
.claude/claude-auto-review/claude-auto-review.log
```