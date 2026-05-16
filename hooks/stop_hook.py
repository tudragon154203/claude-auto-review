#!/usr/bin/env python3
import sys
from pathlib import Path

_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from claude_auto_review.hooks.stop_hook import main

if __name__ == "__main__":
    raise SystemExit(main())
