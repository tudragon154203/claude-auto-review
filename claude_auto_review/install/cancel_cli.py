#!/usr/bin/env python3
import sys
from pathlib import Path

# Ensure repo root is on path so claude_auto_review package is importable
_repo_root = Path(__file__).resolve().parent.parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))
from claude_auto_review.utils.bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from claude_auto_review.runtime.client_dirs import get_client_id
from claude_auto_review.paths.path_utils import get_project_root
from claude_auto_review.runtime.cleanup.session import cancel_runtime
from claude_auto_review.runtime.events import log_event


def main():
    project_root = get_project_root()
    client_id = get_client_id()
    removed = cancel_runtime(project_root, client_id=client_id)
    log_event(project_root, "cancel_completed", removed=[str(path) for path in removed])
    if removed:
        print("Claude Auto Review cancelled. Removed:")
        for path in removed:
            print(f"- {path}")
    else:
        print("Claude Auto Review: no active runtime state found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
