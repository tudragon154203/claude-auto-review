# Claude Code Hooks in `claude-auto-review`

This document describes the hooks this plugin actually installs, what each hook does at runtime, and how the hook behavior maps to the plugin's state and review flow.

## Hook overview

`claude-auto-review` uses three Claude Code lifecycle hooks:

- `PostToolUse` tracks file edits and deletions so later stop checks know what changed.
- `Stop` enforces the review gate before Claude is allowed to stop.
- `SessionEnd` cleans up the session's runtime state and stale pending-review artifacts.

The hook entrypoints are small wrappers under [`hooks/`](hooks) that import the real implementations from `claude_auto_review/hooks/`.

## Configuration source of truth

The installed hook wiring is defined in:

- [`.claude-plugin/plugin.json`](.claude-plugin/plugin.json)
- [`claude_auto_review/hooks/hooks.json`](claude_auto_review/hooks/hooks.json)
- [`hooks/hooks.json`](hooks/hooks.json)

Those files should stay in sync. `plugin.json` is the canonical package manifest, while the JSON files under `claude_auto_review/hooks/` and `hooks/` are the runtime hook configurations used during installation.

## Anthropic hook rules that apply here

These are the hook semantics from the official Claude Code docs that matter for this plugin:

- Hooks can live in user settings, project settings, local project settings, or plugin hook manifests.
- `timeout` is a standard handler field and `statusMessage` is the spinner text shown while the hook runs.
- `matcher` is interpreted by its shape:
  - `*`, empty, or omitted means match all events in that hook group.
  - A string made only of letters, digits, `_`, and `|` is treated as an exact value or `|`-separated list of exact values.
  - Any other character makes it a JavaScript regular expression.
- `Stop` and `SessionEnd` do not use matchers in the same way tool events do; in this repo, they are configured without a matcher.
- Command hooks receive event JSON on stdin.
- Exit code `0` allows the action to proceed.
- Exit code `2` is the blocking signal, but whether that blocks depends on the event:
  - `Stop` uses exit `2` to prevent Claude from stopping and continue the conversation.
  - `PostToolUse` does not block the already-completed tool call; exit `2` only feeds stderr back to Claude.
- For most events, any non-zero exit code other than `2` is treated as a non-blocking error.
- For structured control, Claude Code expects JSON on stdout when the hook exits `0`.

## `PostToolUse`

Configured matcher:

- `Write`
- `Edit`
- `MultiEdit`
- `Delete`
- `Remove`
- `Bash`
- `PowerShell`

Timeout:

- `10` seconds

Status message:

- `Claude Auto Review: tracking changed file...`

What it does:

1. Reads the hook payload and extracts file paths associated with the tool call.
2. Normalizes each candidate path relative to the project root.
3. Skips files excluded by plugin settings or files under the plugin's own runtime tree.
4. Looks up the current file hash.
5. Appends an edit event to the client's `state.jsonl`.

Behavior details:

- For an existing file, the hook stores the file path, hash, timestamp, and whether that hash was already reviewed.
- For a deletion, the hook records a deleted-file marker using `DELETED_FILE_HASH`.
- The hook is fail-open: if it errors, Claude is not blocked by the hook wrapper.
- The hook is intentionally not relied on for blocking; the official hook semantics treat `PostToolUse` as post-action feedback only.

Why it exists:

- The stop flow depends on append-only per-client state to know which files still need review.
- Tracking happens after the tool finishes so the state log reflects what Claude actually changed, not what it intended to change.

## `Stop`

Timeout:

- `660` seconds

Status message:

- `Claude Auto Review: checking review state...`

What it does:

1. Resolves the current project root, session payload, client id, and settings.
2. Loads the current client snapshot once for the stop attempt.
3. Computes the set of unreviewed files.
4. Allows stop immediately if there are no unreviewed files.
5. Applies the stop circuit breaker when the number of consecutive stop blocks reaches `maxStopPasses`.
6. Optionally runs the last-assistant-message classifier before pending-review resolution on unreviewed stop paths.
7. Reuses an existing pending review when possible, or generates a new review prompt if needed.
8. Finalizes the decision and either approves the stop or returns a blocking response.

Important behavior:

- If the classifier returns `incomplete`, Claude is allowed to continue without invoking review generation.
- Other classifier outcomes continue through the normal review path.
- The stop flow is also fail-open at the hook wrapper level, so a hook crash does not trap Claude in a broken state.
- The official hook contract allows `Stop` to block by exiting with code `2`, which is the behavior this plugin depends on when it needs to keep Claude in the conversation.

What gets written:

- Stop decisions are logged through the runtime event logger.
- Review generation can write prompt/result artifacts under the client's runtime directory.
- Finalization marks covered hashes reviewed in the client state.

## `SessionEnd`

Timeout:

- `10` seconds

Status message:

- `Claude Auto Review: cleaning session state...`

What it does:

1. Reads the session context without forcing client-runtime creation.
2. Removes expired pending review artifacts for the current client.
3. Prunes stale client directories across the project runtime tree.
4. Cancels the active client session directory.

What it cleans up:

- Per-session runtime directories under `.claude/claude-auto-review/`
- Expired pending reviews
- Stale client directories that exceed the configured stale-client threshold

Why it exists:

- It keeps the runtime tree from accumulating abandoned session state.
- It reduces the chance of an old pending review being reused after the session is gone.

## State and runtime effects

The hooks are designed around append-only state and per-client isolation:

- `PostToolUse` appends file activity to `state.jsonl`.
- `Stop` reads the accumulated state and decides whether Claude can stop.
- `SessionEnd` deletes runtime artifacts for the ending session.

The important contract is that review coverage is tracked by hash, not by filename alone. If a file changes again, the new hash becomes a new review target.

## Maintainer notes

- Keep `plugin.json`, `claude_auto_review/hooks/hooks.json`, and `hooks/hooks.json` aligned.
- Preserve the fail-open behavior unless there is a deliberate reason to change how hook failures are handled.
- Update this file whenever the stop flow, matcher set, or runtime cleanup behavior changes.

## Official Claude Code docs

These are the authoritative Claude Code hook references for the general API and configuration model:

- Hooks reference: https://docs.anthropic.com/en/docs/claude-code/hooks
- Hooks guide: https://docs.anthropic.com/en/docs/claude-code/hooks-guide
- Settings: https://docs.anthropic.com/en/docs/claude-code/settings
- Matcher patterns: https://code.claude.com/docs/en/hooks#matcher-patterns
- Hook input/output: https://code.claude.com/docs/en/hooks#hook-input-and-output
- Exit code behavior: https://code.claude.com/docs/en/hooks#exit-code-2-behavior-per-event
