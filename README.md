[![coverage](https://img.shields.io/badge/coverage-high-brightgreen?style=flat-square)](tests/)
[![PyPI version](https://img.shields.io/pypi/v/claude-auto-review.svg)](https://pypi.org/project/claude-auto-review/)

# Claude Auto Review

Claude Code plugin for automatic review after Claude edits files.

After each file edit (Write/Edit/MultiEdit/Delete), the plugin tracks the file hash. When Claude tries to stop, the plugin blocks until the changes have been reviewed — either manually in-session or automatically via a reviewer CLI backend.

## Features

- Tracks file edits through Claude Code hooks and blocks stop until changes are reviewed.
- Supports reviewer CLI backends via `reviewerBackend` (`claude`, `codex`, or `opencode`).
- Uses a last-message classifier to skip review generation when Claude should keep working.
- Enforces a stop circuit breaker with `maxStopPasses`.
- Live-reloads `.claude/settings.json` without a restart.
- Dependency-free Python (standard library only).
- Works inside git worktrees — resolves to the main repo's `.claude/claude-auto-review/` state via `git rev-parse --show-toplevel`.

## Installation

```bash
pip install claude-auto-review          # Install from PyPI
claude-auto-review install              # One-time init in project root
# or: car install
```

Creates `.claude/claude-auto-review/`, copies rules, and updates `.claude/settings.json`.

Then configure:

```bash
claude-auto-review config               # Interactive setup wizard
# or: car config
```

Prompts for the key settings — after that, Claude Code sessions **use the plugin automatically**.

See [INSTALL.md](INSTALL.md) for full details.

## Architecture

The implementation is split into small modules instead of one monolith. Below are focused diagrams covering each subsystem.

---

### 1. Hook Wiring

Claude Code calls three lifecycle hooks, each mapped to a plugin hook handler via `hooks.json`:

```mermaid
flowchart LR
    subgraph "Hooks.json Registration"
        direction TB
        PTU["PostToolUse"]
        STP["Stop ★"]
        SEND["SessionEnd"]
    end

    subgraph "Plugin Hook Handlers"
        direction TB
        PTU_H["post_tool_use.py<br/>Tracks file hashes<br/>for review workflow"]
        STP_H["stop_hook.py<br/>🚦 Decision engine → review<br/>generation → block / allow"]
        SEND_H["session_end.py<br/>Cleans up stale state"]
    end

    PTU -.-> PTU_H
    STP == "★ Reviews happen here ★" ===> STP_H
    SEND -.-> SEND_H

    style PTU fill:#e3f2fd,stroke:#1565c0,stroke-dasharray: 3 3
    style PTU_H fill:#e3f2fd,stroke:#1565c0,stroke-dasharray: 3 3
    style STP fill:#fff3e0,stroke:#e65100,stroke-width:4px
    style STP_H fill:#fff3e0,stroke:#e65100,stroke-width:4px
    style SEND fill:#f3e5f5,stroke:#7b1fa2,stroke-dasharray: 3 3
    style SEND_H fill:#f3e5f5,stroke:#7b1fa2,stroke-dasharray: 3 3
```

---

### 2. File Edit Tracking (PostToolUse)

Every time Claude edits a file, the PostToolUse hook captures the file hash and stores an event for later review:

```mermaid
flowchart TD
    EDIT["Claude edits file<br/>(Write / Edit / MultiEdit / Delete)"] --> EXTRACT["Extract file paths from hook input"]
    EXTRACT --> FILTER{"Should skip?"}
    FILTER -- "Runtime path or excluded pattern" --> SKIP["Log skipped file, continue"]
    FILTER -- "Tracked path" --> HASH["Get file hash from disk"]
    HASH -- "File missing (deleted)" --> DEL["Append EditRecord(deleted=True)"]
    HASH -- "Hash obtained" --> REVIEWED{"Already reviewed?"}
    REVIEWED -- "Yes" --> APPEND_R["Append EditRecord(reviewed=True)"]
    REVIEWED -- "No" --> APPEND_U["Append EditRecord(reviewed=False)"]
    APPEND_R --> DONE["Continue Claude session"]
    APPEND_U --> DONE
    DEL --> DONE
    SKIP --> DONE

    style EDIT fill:#e3f2fd,stroke:#1565c0
    style HASH fill:#e8f5e9,stroke:#2e7d32
    style APPEND_U fill:#ffebee,stroke:#c62828
    style APPEND_R fill:#e8f5e9,stroke:#2e7d32
    style DONE fill:#f5f5f5,stroke:#9e9e9e
```

---

### 3. Stop Flow — Decision Engine

When Claude attempts to stop, the Stop hook runs the stop-flow service through staged checks. Each stage decides whether to allow the stop, continue without review, or block for review:

```mermaid
flowchart TD
    STOP["Claude attempts stop"] --> CTX["Build RuntimeContext<br/>(project, client, settings)"]
    CTX --> ENABLED{"Plugin enabled?"}
    ENABLED -- "No" --> ALLOW_DISABLED["Allow stop (disabled)"]
    ENABLED -- "Yes" --> STATE["Load state snapshot"]
    STATE --> UNREVIEWED{"Unreviewed files?"}
    UNREVIEWED -- "No" --> ALLOW_CLEAN["Allow stop (clean)"]
    UNREVIEWED -- "Yes" --> BREAKER{"Circuit breaker hit?"}
    BREAKER -- "Yes (≥ maxStopPasses)" --> ALLOW_BREAKER["Allow stop (circuit breaker)"]
    BREAKER -- "No" --> CLASSIFIER{"Classifier status?"}
    CLASSIFIER -- "incomplete" --> ALLOW_INCOMPLETE["Allow stop —<br/>Claude still working"]
    CLASSIFIER -- "complete / unknown / error / skipped" --> PENDING{"Pending review reuse?"}
    PENDING -- "Yes (unexpired)" --> FINALIZE_OLD["Finalize with cached review"]
    PENDING -- "No" --> PROMPT["Generate review prompt"]
    PROMPT --> SUCCESS{"Review generated?"}
    SUCCESS -- "No" --> BLOCK["Block stop"]
    SUCCESS -- "Yes" --> BLOCK2{"Would stop be blocked?"}
    FINALIZE_OLD --> BLOCK2
    BLOCK2 -- "No" --> ALLOW_REVIEWED["Allow stop (reviewed)"]
    BLOCK2 -- "Yes" --> BLOCK
    BLOCK --> RETURN_BLOCKED["Return blocked stop response"]

    style STOP fill:#fff3e0,stroke:#e65100
    style ALLOW_DISABLED fill:#e8f5e9,stroke:#2e7d32
    style ALLOW_CLEAN fill:#e8f5e9,stroke:#2e7d32
    style ALLOW_BREAKER fill:#e8f5e9,stroke:#2e7d32
    style ALLOW_INCOMPLETE fill:#e8f5e9,stroke:#2e7d32
    style ALLOW_REVIEWED fill:#e8f5e9,stroke:#2e7d32
    style BLOCK fill:#ffebee,stroke:#c62828
    style RETURN_BLOCKED fill:#ffebee,stroke:#c62828
```

---

### 4. Review Prompt Generation

When a new review is needed, the plugin assembles context from rules and session-scoped diffs into a prompt for the reviewer backend:

```mermaid
flowchart LR
    subgraph inputs["① Review Inputs"]
        direction TB
        RULES["Review rules"]
        SNAPSHOTS["Session-scoped diff<br/>(captured before first edit)"]
        FILES["Unreviewed files"]
    end

    subgraph assembly["② Prompt Assembly"]
        direction TB
        TIMESTAMP("Gen ID + timestamp")
        BUILD["Build prompt"]
        WRITE_PROMPT["Write prompt file"]
        WRITE_REVIEW["Write review stub"]
    end

    subgraph backend["③ Reviewer Backend"]
        direction TB
        CLAUDE["Claude Code"]
        CODEX["Codex CLI"]
    end

    FILES --> TIMESTAMP
    RULES --> BUILD
    SNAPSHOTS --> BUILD
    TIMESTAMP --> BUILD
    BUILD --> WRITE_PROMPT
    BUILD --> WRITE_REVIEW
    WRITE_PROMPT --> CLAUDE
    WRITE_PROMPT --> CODEX

    style TIMESTAMP fill:#f3e5f5,stroke:#7b1fa2
    style inputs fill:#e3f2fd,stroke:#1565c0
    style assembly fill:#f3e5f5,stroke:#7b1fa2
    style backend fill:#e8f5e9,stroke:#2e7d32
```

---

### 5. State Management

All session events are recorded as JSONL entries. A snapshot is computed on each stop attempt for consistent queries:

```mermaid
flowchart LR
    subgraph writers["① Event Writers"]
        direction TB
        PTU_W["PostToolUse writes<br/>EditRecord"]
        STOP_W["Stop hook writes<br/>ReviewMetadata / StopBlocked"]
        SEND_W["SessionEnd writes<br/>cleanup events"]
    end

    subgraph storage["② State Storage"]
        direction TB
        CLI_STATE["Per-client state.jsonl"]
        GLOBAL_LOG["Project lifecycle log"]
    end

    subgraph reader["③ State Reader"]
        direction TB
        SNAPSHOT["StateSnapshot<br/>from events"]
        UNREVIEWED["Unreviewed files"]
        BLOCKS["Stop blocks count"]
        REVIEW_MATCH["Pending review match"]
    end

    PTU_W --> CLI_STATE
    STOP_W --> CLI_STATE
    SEND_W --> CLI_STATE
    PTU_W -.-> GLOBAL_LOG
    STOP_W -.-> GLOBAL_LOG
    SEND_W -.-> GLOBAL_LOG

    CLI_STATE --> SNAPSHOT
    SNAPSHOT --> UNREVIEWED
    SNAPSHOT --> BLOCKS
    SNAPSHOT --> REVIEW_MATCH

    style writers fill:#e3f2fd,stroke:#1565c0
    style storage fill:#fff3e0,stroke:#e65100
    style reader fill:#e8f5e9,stroke:#2e7d32
```


---

The classifier runs before pending-review resolution on unreviewed stop paths: `incomplete` lets Claude continue working without invoking review generation, while `complete`, `unknown`, `error`, and `skipped` continue into the normal review/block flow.

The stop flow reads the current client state into a snapshot once per stop attempt so lifecycle queries share one view of the session.

State events are written through a single semantic append path so the per-client `state.jsonl` log and the project-level lifecycle log stay aligned.

## Related Projects

This plugin was inspired by:

- [hamelsmu/claude-review-loop](https://github.com/hamelsmu/claude-review-loop) — a stop-hook-driven automated review loop that uses Claude Code lifecycle hooks to block stops until diffs are reviewed.
- [NTCoding/claude-skillz/automatic-code-review](https://github.com/NTCoding/claude-skillz/tree/main/automatic-code-review) — an automatic code review workflow built around session hooks, review rules, and tracked file changes.

Thanks to both projects for the ideas and patterns that influenced this plugin.



