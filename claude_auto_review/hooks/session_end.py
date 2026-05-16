#!/usr/bin/env python3
import sys

from claude_auto_review.runtime.cleanup.session import cancel_session
from claude_auto_review.runtime.cleanup.stale import cleanup_stale_clients
from claude_auto_review.runtime.events import log_event
from claude_auto_review.runtime.hook_context import build_hook_runtime_context
from claude_auto_review.runtime.pending_cleanup import cleanup_expired_pending_reviews
from claude_auto_review.runtime.process import run_fail_open


def _run_session_end():
    ctx = build_hook_runtime_context(sys.stdin.read(), ensure_client=False)
    project_root = ctx.project_root
    client_id = ctx.client_id
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
