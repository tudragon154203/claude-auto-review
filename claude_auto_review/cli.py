#!/usr/bin/env python3
"""Single entry point for ``claude-auto-review`` CLI with subcommands."""

import sys
from pathlib import Path
from importlib.metadata import version, PackageNotFoundError


SUBCOMMANDS = {
    "config": "claude_auto_review.install.config_cli",
    "install": "claude_auto_review.install.setup_cli",
    "cancel": "claude_auto_review.install.cancel_cli",
    "prompt": "claude_auto_review.review.prompt",
    "uninstall": "claude_auto_review.install.uninstall_cli",
    "update": "claude_auto_review.install.update_cli",
}


def _get_version():
    try:
        return version("claude-auto-review")
    except PackageNotFoundError:
        return "unknown"


def _print_help(exit_code=0):
    self = Path(__file__).name if Path(__file__).exists() else "claude-auto-review"
    print(f"Usage: {self} <subcommand> [args]", file=sys.stderr)
    print(file=sys.stderr)
    print("Subcommands:", file=sys.stderr)
    print("  config     Guide setup and configure important project settings", file=sys.stderr)
    print("  install    Set up the plugin in the current project", file=sys.stderr)
    print("  cancel     Cancel the active review session", file=sys.stderr)
    print("  prompt     Manually trigger review prompt generation", file=sys.stderr)
    print("  uninstall  Remove plugin from current project", file=sys.stderr)
    print("  update     Pull latest plugin checkout and refresh current project setup", file=sys.stderr)
    print("  help       Show this help message", file=sys.stderr)
    print("  version    Show version information", file=sys.stderr)
    return exit_code


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        return _print_help()

    arg = sys.argv[1]
    if arg in ("-v", "--version"):
        print(f"claude-auto-review version {_get_version()}")
        return 0

    subcommand = arg

    if subcommand == "help":
        return _print_help()
    if subcommand == "version":
        print(f"claude-auto-review version {_get_version()}")
        return 0

    module_path = SUBCOMMANDS.get(subcommand)
    if module_path is None:
        print(f"Unknown subcommand: {subcommand}", file=sys.stderr)
        return _print_help(exit_code=1)

    # Remove the subcommand arg so downstream sees clean argv
    sys.argv = [sys.argv[0]] + sys.argv[2:]

    import importlib
    mod = importlib.import_module(module_path)
    return mod.main()


if __name__ == "__main__":
    raise SystemExit(main())
