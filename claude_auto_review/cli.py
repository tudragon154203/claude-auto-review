#!/usr/bin/env python3
"""Single entry point for ``claude-auto-review`` CLI with subcommands.

Subcommands are registered via :func:`register_subcommand` (or the
``SUBCOMMANDS`` built-in default table). Third-party integrations can
register additional commands without modifying this file — the OCP
extension point.
"""

from __future__ import annotations

import importlib
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

_BUILTIN_SUBCOMMANDS: dict[str, str] = {
    "config": "claude_auto_review.install.cli.config",
    "install": "claude_auto_review.install.cli.setup",
    "cancel": "claude_auto_review.install.cli.cancel",
    "prompt": "claude_auto_review.review.prompt",
    "uninstall": "claude_auto_review.install.cli.uninstall",
    "update": "claude_auto_review.install.cli.update",
}

_BUILTIN_HELP: dict[str, str] = {
    "config": "Guide setup and configure important project settings",
    "install": "Set up the plugin in the current project",
    "cancel": "Cancel the active review session",
    "prompt": "Manually trigger review prompt generation",
    "uninstall": "Remove plugin from current project",
    "update": "Pull latest plugin checkout and refresh current project setup",
}

_SUBCOMMANDS: dict[str, str] = dict(_BUILTIN_SUBCOMMANDS)
_HELP: dict[str, str] = dict(_BUILTIN_HELP)


def register_subcommand(name: str, module_path: str, help_text: str = "") -> None:
    """Register a CLI subcommand (OCP extension point).

    Calling code can also rely on the Python entry-points group
    ``claude_auto_review.subcommands`` for plugin discovery.
    """
    _SUBCOMMANDS[name] = module_path
    if help_text:
        _HELP[name] = help_text


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
    for name, desc in sorted(_HELP.items()):
        print(f"  {name:<10} {desc}", file=sys.stderr)
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

    if arg == "help":
        return _print_help()
    if arg == "version":
        print(f"claude-auto-review version {_get_version()}")
        return 0

    module_path = _SUBCOMMANDS.get(arg)
    if module_path is None:
        print(f"Unknown subcommand: {arg}", file=sys.stderr)
        return _print_help(exit_code=1)

    sys.argv = [sys.argv[0]] + sys.argv[2:]

    mod = importlib.import_module(module_path)
    return mod.main()


if __name__ == "__main__":
    raise SystemExit(main())
