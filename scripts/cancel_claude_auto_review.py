#!/usr/bin/env python3
from state import cancel_runtime, get_client_id, get_project_root, log_event


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
