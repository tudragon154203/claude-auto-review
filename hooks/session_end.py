#!/usr/bin/env python3
import sys

from bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from claude_auto_review.runtime.core.client_dirs import get_client_id
from claude_auto_review.paths.core.path_utils import get_project_root
from claude_auto_review.runtime.cleanup.session import cancel_session
from claude_auto_review.runtime.cleanup.stale import cleanup_stale_clients
from claude_auto_review.runtime.pending_cleanup import cleanup_expired_pending_reviews
from claude_auto_review.runtime.core.context import get_payload_session_id, read_json_payload
from claude_auto_review.runtime.core.events import log_event
from claude_auto_review.runtime.core.process import run_fail_open


def _run_session_end():
    project_root = get_project_root()
    raw = sys.stdin.read()
    payload = read_json_payload(raw)
    client_id = get_client_id(get_payload_session_id(payload))
    expired_removed = cleanup_expired_pending_reviews(project_root, client_id=client_id)
    stale_removed = cleanup_stale_clients(project_root)
    removed = cancel_session(project_root, client_id=client_id)
    if removed or expired_removed or stale_removed:
        log_event(
            project_root,
            "session_end_cleanup",
            removed=[str(p) for p in removed],
            expired_removed=expired_removed,
            stale_removed=[str(p) for p in stale_removed],
            client_id=client_id,
        )
    return 0


def main():
    return run_fail_open(_run_session_end, event_type="session_end_error")


if __name__ == "__main__":
    raise SystemExit(main())
