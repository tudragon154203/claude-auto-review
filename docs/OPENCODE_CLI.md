# OpenCode CLI Backend

The `opencode` reviewer backend runs [OpenCode](https://opencode.ai) as a non-interactive subprocess to auto-complete code reviews.

## How it works

1. The stop hook combines the generated review prompt with the user prompt into a merged prompt file.
2. The merged file is written to the client's `run/` directory (project-scoped, not system temp).
3. OpenCode is invoked as:

```
opencode run --file <merged-prompt-file>
```

4. The `--file` flag attaches the merged prompt so the full review context (rules, diffs, instructions) is available to the model without hitting OS command-line length limits.
5. OpenCode uses its own configuration (`~/.config/opencode/opencode.json` or `.opencode.json`) for model and provider selection. The `reviewerModel` setting in claude-auto-review is informational for display but does not override the opencode config.

## Configuration

### claude-auto-review side

```json
{
  "claude-auto-review": {
    "reviewerBackend": "opencode",
    "reviewerModel": "opencode/big-pickle"
  }
}
```

Or via CLI:

```bash
claude-auto-review config --backend opencode --non-interactive
```

### OpenCode side

OpenCode needs a valid provider and model configured. Create or edit `~/.config/opencode/opencode.json`:

```json
{
  "model": "provider/model-name",
  "provider": {
    "openrouter": {
      "apiKey": "{env:OPENROUTER_API_KEY}"
    }
  }
}
```

See the [OpenCode documentation](https://opencode.ai) for supported providers and configuration options.

## Requirements

- `opencode` CLI installed and on PATH (`npm install -g opencode-ai`)
- At least one AI provider configured in opencode
- The `opencode run` subcommand must be available (OpenCode v1.0+)

## Differences from other backends

| Aspect | Claude | Codex | OpenCode |
|--------|--------|-------|----------|
| CLI invocation | `claude --print --bare --append-system-prompt-file` | `codex exec --json --sandbox read-only` | `opencode run --file` |
| Prompt delivery | System prompt file + CLI arg | Stdin | Merged prompt file via `--file` |
| Model selection | `--model` flag | `--model` flag | opencode config |
| Permissions | `--allowedTools` whitelist | `--sandbox read-only` | `--pure` (no plugins) |
| Default model | `claude-sonnet-4-6` | `gpt-5.4-mini` | `opencode/big-pickle` |
