#!/usr/bin/env python3
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.paths import get_client_id, get_project_root
from scripts.state import (  # noqa: E402
    cancel_session,
    cleanup_expired_pending_reviews,
    log_event,
)


def main():
    try:
        project_root = get_project_root()
        raw = sys.stdin.read().strip()
        payload = json.loads(raw) if raw else {}
        client_id = get_client_id(payload.get("session_id") if isinstance(payload, dict) else None)
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
    except Exception as error:
        try:
            log_event(get_project_root(), "session_end_error", error=str(error))
        except Exception:
            pass
        return 0  # Fail open — never block session end


if __name__ == "__main__":
    raise SystemExit(main())
