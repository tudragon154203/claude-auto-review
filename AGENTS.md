# Development Notes

This repository contains a Claude Code plugin. Keep this file focused on how the pieces fit together.

## System Graph

```mermaid
flowchart TD
  HookPost[hooks/post_tool_use.py] --> State["client state.jsonl"]
  HookStop[hooks/stop_hook.py] --> Flow[stop/orchestration/core/flow.py]
  HookEnd[hooks/session_end.py] --> Cleanup[runtime/cleanup/session.py]

  Flow --> Classifier[stop/classifier/core/last_assistant_message.py]
  Classifier --> State
  Flow --> Pending[stop/orchestration/pending.py]
  Pending --> ReviewGen[review/prompting/generation.py]
  Finalize --> AutoReview[stop/reviews/autocomplete.py]
  AutoReview --> ReviewComp[review/completion.py]
  Flow --> Finalize[stop/orchestration/finalize.py]

  ReviewGen --> ReviewFile["review prompt + result files"]
  ReviewComp --> State
  Cleanup --> State
```

## Entry Points

- `hooks/post_tool_use.py` records every edited file as an append-only state event.
- `hooks/stop_hook.py` decides whether Claude may stop, then routes into the stop orchestration flow.
- `hooks/session_end.py` removes the active client session data and prunes stale pending reviews.

## Core Subsystems

### State

- `claude_auto_review/state/models.py` defines the record shapes written to JSONL.
- `claude_auto_review/state/snapshot.py` indexes loaded events for lifecycle queries.
- `claude_auto_review/state/store/read.py` loads and filters client state.
- `claude_auto_review/state/store/write.py` appends events and computes file hashes.
- `claude_auto_review/state/store/rewrite.py` rewrites JSONL state while preserving invalid lines.
- `claude_auto_review/state/reviews/verdicts.py` parses and normalizes review verdicts.
- `claude_auto_review/state/review_matching.py` matches pending reviews to file entries.
- `claude_auto_review/state/review_expiry.py` handles review timeout logic.
- `claude_auto_review/state/hook_input.py` parses hook payloads.

### Runtime

- `claude_auto_review/runtime/setup.py` creates the per-client runtime tree under `.claude/claude-auto-review/`.
- `claude_auto_review/runtime/cleanup/session.py` removes per-client data.
- `claude_auto_review/runtime/cleanup/stale.py` prunes stale client directories.
- `claude_auto_review/runtime/hook_context.py` resolves hook project/client/settings context.
- `claude_auto_review/runtime/helpers.py` centralizes structured event logging.
- `claude_auto_review/runtime/pending_cleanup.py` handles pending review cleanup.

### Review Generation

- `claude_auto_review/review/prompting/generation.py` builds the prompt from git diff, file snapshots, and project rules.
- `claude_auto_review/review/prompting/flow.py` writes the prompt and review files.
- `claude_auto_review/review/prompt.py` is the subprocess entry point for running a review prompt.
- `claude_auto_review/review/prompting/templates.py` contains the prompt template strings.
- `claude_auto_review/review/prompting/rendering.py` formats file content for review prompts.
- `claude_auto_review/review/completion.py` reads review output and marks covered file hashes reviewed.

### Stop Flow

- `claude_auto_review/stop/orchestration/core/flow.py` coordinates the stop decision.
- `claude_auto_review/stop/orchestration/core/pending.py` resolves an existing pending review or creates a new one.
- `claude_auto_review/stop/orchestration/core/finalize.py` applies the review result, handles autocomplete, and finalizes the stop decision.
- `claude_auto_review/stop/orchestration/core/context.py` manages stop context.
- `claude_auto_review/stop/orchestration/core/resolution.py` defines resolution types.
- `claude_auto_review/stop/orchestration/core/response_actions.py` defines allow/block actions.
- `claude_auto_review/stop/reviews/core/selection.py` chooses which files still need review.
- `claude_auto_review/stop/reviews/core/autocomplete.py` exposes autocomplete compatibility imports.
- `claude_auto_review/stop/reviews/core/prompt_runner.py` resolves the review prompt runner path and runs Claude CLI autocomplete.
- `claude_auto_review/stop/feedback.py` formats the blocking message shown back to Claude.
- `claude_auto_review/stop/response.py` emits the JSON stop/block response.

### Classifier

- `claude_auto_review/stop/classifier/core/last_assistant_message.py` optionally classifies the last assistant message before pending-review resolution on unreviewed stop paths.
- `claude_auto_review/stop/classifier/core/extraction.py` extracts the message text from the hook payload.
- `claude_auto_review/stop/classifier/core/client.py` talks to the Anthropic API.
- `claude_auto_review/stop/classifier/core/models.py` defines classifier defaults and result objects.
- `claude_auto_review/stop/classifier/core/request.py` builds classifier API requests.
- `claude_auto_review/stop/classifier/core/response.py` parses classifier API responses.

### Paths & Utilities

- `claude_auto_review/paths/path_utils.py` defines shared path constants and helpers.
- `claude_auto_review/paths/uri_utils.py` normalizes file URIs to relative paths.
- `claude_auto_review/runtime/client_dirs.py` manages per-client runtime directories.
- `claude_auto_review/config/settings.py` loads plugin settings and resolves rules paths.
- `claude_auto_review/utils/shell_parsing.py` tokenizes shell commands for edit tracking.
- `claude_auto_review/utils/datetime_utils.py` provides ISO timestamp parsing and age helpers.

### Install

- `claude_auto_review/install/installer.py` installs runtime files and updates project settings.
- `claude_auto_review/install/shims.py` generates the runtime wrapper scripts.
- `claude_auto_review/install/setup_cli.py` and `claude_auto_review/install/cancel_cli.py` are the CLI entry points.

### Support Files

- `agents/reviewer.md` defines the review agent used by autocomplete.
- `rules/review-rules.md` is the default project rules file copied during setup.
- `.claude-plugin/plugin.json` declares hooks, commands, agents, and default plugin settings.

## Settings

`claude-auto-review` lives in `.claude/settings.json`.

| Key | Default | Meaning |
|-----|---------|---------|
| `enabled` | `true` | Enable or disable the plugin |
| `rulesFile` | `.claude/claude-auto-review/review-rules.md` | Path to the review rules file |
| `includeExtensions` | `[]` | Only track these suffixes when set |
| `skipExtensions` | `[]` | Never track these suffixes |
| `maxStopPasses` | `5` | Stop-block circuit breaker threshold |
| `pendingReviewTimeoutHours` | `1` | Age before a pending review expires |
| `reviewerTimeoutSeconds` | `600` | Hard cap for the review subprocess |
| `reviewFeedbackMaxChars` | `9000` | Maximum feedback copied back into Claude |
| `lastAssistantMessageClassifierEnabled` | `true` | Enable the stop-gate classifier before pending-review resolution on unreviewed stop paths |
| `lastAssistantMessageClassifierTimeoutSeconds` | `20` | Timeout for the classifier API call |
| `staleClientTimeoutHours` | `48` | Hours after which a client session is considered stale |

## Runtime Layout

```mermaid
flowchart LR
  Root[claude-auto-review runtime] --> Log[global log]
  Root --> Clients[client directories]
  Root --> Rules[resolved rules file]
  Root --> Scripts[generated scripts]

  Clients --> Client[one client]
  Client --> State[state.jsonl]
  Client --> Reviews[review files]
  Client --> Run[run metadata]
  Reviews --> Prompt[prompt file]
  Reviews --> Result[review output]
```

## Review Process

1. The post-tool hook appends file edits to the active client's state.
2. The stop hook finds unreviewed hashes for that client.
3. If needed, the review generator writes a prompt file and a pending-review record.
4. The reviewer subprocess or Claude CLI autocomplete writes the review result.
5. Finalization marks covered hashes reviewed and decides whether Claude may stop.
6. On unreviewed stop paths, the optional classifier runs before pending-review resolution; `incomplete` allows Claude to continue without invoking review generation, while `complete`, `unknown`, `error`, and `skipped` continue into the normal review/block flow. The result is also recorded in state/log telemetry.

## Testing Shape

- **Unit** tests cover individual modules and helpers.
- **Integration** tests cover state, runtime, and orchestration working together.
- **E2E** tests exercise the hook entry points through subprocesses.

Prefer concrete assertions around stop decisions, state transitions, and review coverage rather than broad snapshot-style checks.
