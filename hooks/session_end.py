#!/usr/bin/env python3
import sys

from bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from claude_auto_review.paths import get_client_id, get_project_root
from claude_auto_review.runtime.cleanup import cancel_session, cleanup_expired_pending_reviews
from claude_auto_review.runtime.helpers import get_payload_session_id, read_json_payload, run_fail_open
from claude_auto_review.runtime.helpers import log_event


def _run_session_end():
    project_root = get_project_root()
    raw = sys.stdin.read()
    payload = read_json_payload(raw)
    client_id = get_client_id(get_payload_session_id(payload))
    expired_removed = cleanup_expired_pending_reviews(project_root, client_id=client_id)
    removed = cancel_session(project_root, client_id=client_id)
    if removed or expired_removed:
        log_event(
            project_root,
            "session_end_cleanup",
            removed=[str(p) for p in removed],
            expired_removed=expired_removed,
            client_id=client_id,
        )
    return 0


def main():
    return run_fail_open(_run_session_end, event_type="session_end_error")


if __name__ == "__main__":
    raise SystemExit(main())

