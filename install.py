#!/usr/bin/env python3
"""Root-level shim for installing the plugin into the current project."""
import runpy
import sys
from pathlib import Path

_this = Path(__file__).resolve()
_installer = _this.parent / "claude_auto_review" / "install" / "setup_cli.py"
sys.argv = [str(_installer)] + sys.argv[1:]
runpy.run_path(str(_installer), run_name="__main__")
