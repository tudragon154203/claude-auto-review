#!/usr/bin/env python3
import sys

from bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from claude_auto_review.paths.path_utils import get_project_root
from claude_auto_review.runtime.context import read_json_payload
from claude_auto_review.runtime.process import run_fail_open
from claude_auto_review.stop.orchestration.core.flow import run_stop_flow


def _run_stop_hook():
    project_root = get_project_root()
    raw = sys.stdin.read()
    payload = read_json_payload(raw)
    return run_stop_flow(project_root, payload)


def main():
    return run_fail_open(_run_stop_hook, event_type="stop_error")


if __name__ == "__main__":
    raise SystemExit(main())
