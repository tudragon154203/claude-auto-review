# Claude Auto Review

Claude Code plugin for automatic review after Claude edits files.

After each file edit (Write/Edit/MultiEdit/Delete), the plugin tracks the file hash. When Claude tries to stop, the plugin blocks until the changes have been reviewed — either manually in-session or automatically via Claude CLI sub-agent.

## Architecture

The implementation is split into small modules instead of one monolith:

```mermaid
flowchart TD
    A[Claude edits file] --> B[PostToolUse hook]
    B --> C[Track file hash in client state]
    C --> D[Claude attempts stop]
    D --> E[Stop hook runs run_stop_flow]
    E --> F{Unreviewed files?}
    F -- No --> G[Allow stop]
    F -- Yes --> H{Pending review exists?}
    H -- Yes --> I[Reuse pending review]
    H -- No --> J[Run review prompt script]
    J --> K{Review generation succeeded?}
    K -- No --> L[Block stop]
    K -- Yes --> M{Review verdict clean?}
    I --> M
    M -- Yes --> G
    M -- No --> L
    L --> N[Classify last assistant message]
    N --> O[Return blocked stop response]
```

- **Hook entrypoints:** `hooks/post_tool_use.py`, `hooks/stop_hook.py`, `hooks/session_end.py`
- **Core config:** `config/constants.py`, `config/settings.py`, `paths/path_utils.py`, `paths/uri_utils.py`, `runtime/client_dirs.py`, `utils/bootstrap.py`
- **State bookkeeping:** `state/models.py`, `state/store_read.py`, `state/store_write.py`, `state/reviews.py`, `state/review_matching.py`, `state/review_expiry.py`, `state/hook_input.py`
- **Review generation:** `review/generation.py`, `review/prompt_flow.py`, `review/prompt.py`, `review/prompt_templates.py`, `review/completion.py`, `review/rendering.py`
- **Stop orchestration:** `stop/orchestration/flow.py`, `stop/orchestration/pending.py`, `stop/orchestration/finalize.py`, `stop/orchestration/context.py`, `stop/orchestration/resolution.py`, `stop/orchestration/response_actions.py`
- **Stop response:** `stop/feedback.py`, `stop/response.py`
- **Selection & autocomplete:** `stop/reviews/selection.py`, `stop/reviews/autocomplete.py`, `stop/reviews/prompt_runner.py`
- **Classifier:** `stop/classifier/last_assistant_message.py`, `stop/classifier/extraction.py`, `stop/classifier/client.py`, `stop/classifier/models.py`, `stop/classifier/request.py`, `stop/classifier/response.py`
- **Runtime:** `runtime/setup.py`, `runtime/cleanup.py`, `runtime/context.py`, `runtime/events.py`, `runtime/process.py`, `runtime/pending_cleanup.py`
- **Utilities:** `utils/shell_parsing.py`, `utils/datetime_utils.py`
- **Install:** `install/installer.py`, `install/shims.py`, `install/setup_cli.py`, `install/cancel_cli.py`
- **Support files:** `agents/reviewer.md`, `rules/review-rules.md`

**Commands:**
- `/claude-auto-review` — Complete manual review for current unreviewed files
- `/cancel-claude-auto-review` — Cancel all runtime state for the current session

## Installation

See [INSTALL.md](INSTALL.md) for full details.

```bash
python /path/to/claude-auto-review/install.py
```

The installer creates the local `.claude/claude-auto-review/` runtime tree (with `scripts/`, `agents/`, `clients/` subdirs; `clients/*/reviews/` and `clients/*/run/` created lazily per session), copies the default rules, configures `.claude/settings.json`, and updates `.gitignore`.

## Quick Start

```bash
# Run tests
python -m unittest discover -s tests
```

## Implementation

- Dependency-free Python (standard library only)
- Uses Claude Code PostToolUse, Stop, and SessionEnd hooks
- Client isolation per session via `CLAUDE_SESSION_ID`
- Circuit breaker after `maxStopPasses` blocks (default: 3)
- Auto-completion via Claude CLI sub-agent when available
- Reviewer hard-cap via `reviewerTimeoutSeconds` (default: 600 seconds)
