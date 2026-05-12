#!/usr/bin/env python3
"""Root-level shim for cancelling the plugin's runtime state."""
import runpy
import sys
from pathlib import Path

_this = Path(__file__).resolve()
_canceller = _this.parent / "claude_auto_review" / "install" / "cancel_cli.py"
sys.argv = [str(_canceller)] + sys.argv[1:]
runpy.run_path(str(_canceller), run_name="__main__")
