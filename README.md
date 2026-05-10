# Claude Auto Review

Claude Code plugin for automatic review after Claude edits files.

## Overview

After each file edit (Write/Edit/MultiEdit/Delete), the plugin tracks the file hash. When Claude tries to stop, the plugin blocks until the changes have been reviewed — either manually in-session or automatically via Claude CLI sub-agent.

## Architecture

The implementation is split into small modules instead of one monolith:

- `hooks/stop_hook.py` and `hooks/post_tool_use.py` are thin entrypoints.
- `scripts/state.py` is a compatibility facade for the state helpers.
- `scripts/state_store.py`, `scripts/runtime.py`, and `scripts/settings.py` cover state, lifecycle, and config.
- `scripts/review_generation.py` renders prompts and review files.
- `scripts/stop_flow.py`, `scripts/stop_selection.py`, and `scripts/stop_autocomplete.py` cover stop-hook orchestration.
- `scripts/installer.py` handles project setup and generated shims.

**Commands:**
- `/claude-auto-review` — Run manual review for current unreviewed files
- `/cancel-claude-auto-review` — Cancel all runtime state for this project

## Quick Start

```bash
# Run tests
python -m unittest discover -s tests

# Install in a target project
python scripts/setup_claude_auto_review.py
```

The installer creates the local `.claude/claude-auto-review/` runtime tree and generated wrapper scripts in the target project.

## Documentation

| Doc | Description |
|-----|-------------|
| [docs/README.md](docs/README.md) | Behavior, state model, and configuration |
| [docs/INSTALL.md](docs/INSTALL.md) | Installation instructions |
| [docs/RULES-GUIDE.md](docs/RULES-GUIDE.md) | Writing project review rules |

## Implementation

- Dependency-free Python (standard library only)
- Uses Claude Code PostToolUse and Stop hooks
- Client isolation per session via `CLAUDE_SESSION_ID`
- Circuit breaker after 3 stop blocks (configurable)
- Auto-completion via Claude CLI sub-agent when available
