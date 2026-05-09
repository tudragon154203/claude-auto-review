#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from state import cancel_session, get_client_id, get_project_root, log_event  # noqa: E402


def main():
    try:
        project_root = get_project_root()
        client_id = get_client_id()
        removed = cancel_session(project_root, client_id=client_id)
        if removed:
            log_event(
                project_root,
                "session_stop_cleanup",
                removed=[str(p) for p in removed],
                client_id=client_id,
            )
        return 0
    except Exception as error:
        try:
            log_event(get_project_root(), "session_stop_error", error=str(error))
        except Exception:
            pass
        return 0  # Fail open — never block session stop


if __name__ == "__main__":
    raise SystemExit(main())