# Claude Auto Review

Claude Code plugin for automatic review after Claude edits files.

## Overview

After each file edit (Write/Edit/MultiEdit/Delete), the plugin tracks the file hash. When Claude tries to stop, the plugin blocks until the changes have been reviewed — either manually in-session or automatically via Claude CLI sub-agent.

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