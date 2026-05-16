#!/usr/bin/env python3
"""Single entry point for ``claude-auto-review`` CLI with subcommands."""

import sys
from pathlib import Path


SUBCOMMANDS = {
    "install": "claude_auto_review.install.setup_cli",
    "cancel": "claude_auto_review.install.cancel_cli",
    "prompt": "claude_auto_review.review.prompt",
    "uninstall": "claude_auto_review.install.uninstall_cli",
}


def _print_help():
    self = Path(__file__).name if Path(__file__).exists() else "claude-auto-review"
    print(f"Usage: {self} <subcommand>", file=sys.stderr)
    print(file=sys.stderr)
    print("Subcommands:", file=sys.stderr)
    for name in SUBCOMMANDS:
        print(f"  {name}", file=sys.stderr)
    return 1


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        return _print_help()

    subcommand = sys.argv[1]
    module_path = SUBCOMMANDS.get(subcommand)
    if module_path is None:
        print(f"Unknown subcommand: {subcommand}", file=sys.stderr)
        return _print_help()

    # Remove the subcommand arg so downstream sees clean argv
    sys.argv = [sys.argv[0]] + sys.argv[2:]

    import importlib
    mod = importlib.import_module(module_path)
    return mod.main()


if __name__ == "__main__":
    raise SystemExit(main())
