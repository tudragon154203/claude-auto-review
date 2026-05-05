# Claude Auto Review

Claude Code plugin for automatic review after Claude edits files.

See [docs/README.md](docs/README.md) for behavior, [docs/INSTALL.md](docs/INSTALL.md) for installation, and [docs/RULES-GUIDE.md](docs/RULES-GUIDE.md) for writing project rules.

The plugin is implemented in dependency-free Python and uses Claude Code PostToolUse and Stop hooks.

## Development

```bash
python -m unittest discover -s tests
```
