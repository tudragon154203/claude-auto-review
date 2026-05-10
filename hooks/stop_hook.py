#!/usr/bin/env python3
import json
import sys

from bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from claude_auto_review.paths import get_project_root
from claude_auto_review.stop_flow import run_stop_flow


def main():
    try:
        project_root = get_project_root()
        raw = sys.stdin.read().strip()
        payload = json.loads(raw) if raw else {}
        return run_stop_flow(project_root, payload)
    except Exception as error:
        try:
            log_event(get_project_root(), "stop_error", error=str(error))
        except Exception:
            pass
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

