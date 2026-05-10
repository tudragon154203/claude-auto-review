# Claude Auto Review

Claude Code plugin for automatic review after Claude edits files.

## Overview

After each file edit (Write/Edit/MultiEdit/Delete), the plugin tracks the file hash. When Claude tries to stop, the plugin blocks until the changes have been reviewed — either manually in-session or automatically via Claude CLI sub-agent.

## Architecture

The implementation is split into small modules instead of one monolith:

- `hooks/stop_hook.py` and `hooks/post_tool_use.py` are thin entrypoints.
- `claude_auto_review/state.py` is a compatibility facade for the state helpers.
- `claude_auto_review/runtime.py` is a compatibility facade for runtime helpers; `claude_auto_review/runtime_setup.py` and `claude_auto_review/runtime_cleanup.py` own setup and cleanup.
- `claude_auto_review/state_store.py` and `claude_auto_review/settings.py` cover state bookkeeping and config.
- `claude_auto_review/review_generation.py` provides shared prompt and file helpers.
- `claude_auto_review/review_prompt_flow.py` builds the manual review prompt and review file.
- `claude_auto_review/stop_flow_logic.py` resolves pending reviews and stop decisions.
- `claude_auto_review/stop_flow.py`, `claude_auto_review/stop_selection.py`, and `claude_auto_review/stop_autocomplete.py` cover stop-hook orchestration.
- `claude_auto_review/installer.py` handles project setup and generated shims.

**Commands:**
- `/claude-auto-review` — Run manual review for current unreviewed files
- `/cancel-claude-auto-review` — Cancel all runtime state for this project

## Quick Start

```bash
# Run tests
python -m unittest discover -s tests

# Install in a target project
python claude_auto_review/setup_claude_auto_review.py
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

