# Codex CLI Non-Interactive Mode

## Primary Command: `codex exec`

```bash
codex exec "Your task prompt"
```

## Stdin Piping (Equivalent to Claude's `-p`)

```bash
printf 'Refactor src/foo.py and add tests' | codex exec -

# with JSONL output for machine parsing
printf 'Summarize repo TODOs' | codex exec --json -
```

## Key Flags for Subprocess/Batch Use

| Flag | Purpose |
|------|---------|
| `--json` | Output as JSON Lines stream |
| `--output-last-message, -o <path>` | Write final message to file |
| `--sandbox <mode>` | `read-only`, `workspace-write`, or `danger-full-access` |
| `--ask-for-approval never` | Skip approval prompts |
| `--model, -m <string>` | Specify model |
| `--skip-git-repo-check` | Run outside git repos |
| `--ephemeral` | Don't persist session files |
| `--output-schema <path>` | Constrain final response to a JSON Schema |
| `--ignore-user-config` | Skip loading `$CODEX_HOME/config.toml` |
| `--ignore-rules` | Skip user and project `.rules` files |

## CI/Subprocess Template

```bash
codex exec \
  --json \
  --sandbox workspace-write \
  --ask-for-approval never \
  --output-last-message final.txt \
  "Implement task X and report changes"
```

## JSONL Output Event Types

When using `--json`, Codex emits a JSONL stream with event types like:
- `thread.started`
- `turn.started`
- `item.*`
- `turn.completed`
- `error`

## Structured Output via Schema

```bash
codex exec "Extract project metadata" \
  --output-schema ./schema.json \
  -o ./project-metadata.json
```

## Resuming a Session

```bash
codex exec "review the change for race conditions"
codex exec resume --last "fix the race conditions you found"
# or target a specific session
codex exec resume <SESSION_ID>
```

## Authentication in CI

`CODEX_API_KEY` is only supported in `codex exec`. Export the key in a preceding step to avoid leaking it into shell history or process listings:

```bash
export CODEX_API_KEY="your-api-key"
codex exec --json "triage open bug reports"
```

## Comparison with Claude CLI

| Feature | Claude CLI | Codex CLI |
|---------|-----------|-----------|
| Non-interactive | `claude -p <prompt>` | `codex exec <prompt>` |
| Stdin prompt | `claude -p - < file` | `codex exec - < file` |
| JSON output | `claude -p --print-format json` | `codex exec --json` |
| Model override | `claude -p -m claude-sonnet` | `codex exec -m <model>` |

## Review backend integration

The review runner now supports both backends through the `reviewerBackend` setting:

```json
{
  "claude-auto-review": {
    "reviewerBackend": "codex",
    "reviewerModel": "gpt-5"
  }
}
```

- `claude` keeps the current `claude -p` behavior.
- `codex` runs `codex exec --json` in non-interactive mode.
- `opencode` runs `opencode run --file <merged-prompt>` in non-interactive mode.
- Unsupported backend values fail closed instead of silently falling back.

## Key Subprocess Differences

- Codex streams progress to `stderr` and prints only the final agent message to `stdout`
- This makes it easy to capture results: `codex exec "task" | tee result.md`
- Stdin piping works both ways: prompt as argument with piped data as context, or stdin as the full prompt via `-` sentinel
- The review prompt file is still generated and passed into the reviewer flow so the system prompt remains part of the review context.

## Install

```bash
npm install -g @openai/codex
# or
brew install --cask codex
```

## Global Flags

- `--add-dir <path>`
- `--ask-for-approval, -a <untrusted|on-request|never>`
- `--cd, -C <path>`
- `--config, -c <key=value>`
- `--dangerously-bypass-approvals-and-sandbox`, `--yolo`
- `--disable <feature>` (repeatable)
- `--enable <feature>` (repeatable)
- `--image, -i <path[,path...]>` (repeatable)
- `--model, -m <string>`
- `--no-alt-screen`
- `--oss`
- `--profile, -p <string>`
- `--remote <ws://host:port|wss://host:port>`
- `--remote-auth-token-env <ENV_VAR>` (requires `--remote`)
- `--sandbox, -s <read-only|workspace-write|danger-full-access>`
- `--search`
- `PROMPT` (positional)

Sources:
- [Codex CLI Reference](https://developers.openai.com/codex/cli/reference)
- [Non-interactive Mode](https://developers.openai.com/codex/noninteractive)
- [GitHub Repository](https://github.com/openai/codex)
