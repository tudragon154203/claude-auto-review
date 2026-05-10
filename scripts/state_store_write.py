import json
from pathlib import Path

from scripts.paths import client_state_path, get_client_id, get_log_path, utc_now_iso
from scripts.runtime_setup import ensure_client_runtime


def _resolve_project_root(project_root=None):
    from scripts.paths import get_project_root

    return Path(project_root or get_project_root())


def _resolve_client_id(client_id=""):
    return client_id or get_client_id()


def log_event(project_root, event_type, **kwargs):
    try:
        log_path = get_log_path(project_root)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        entry = {"timestamp": utc_now_iso(), "event": event_type, **kwargs}
        with log_path.open("a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(entry, separators=(",", ":")) + "\n")
    except OSError:
        pass


def append_state(entry, project_root=None, client_id=""):
    project_root = _resolve_project_root(project_root)
    client_id = _resolve_client_id(client_id)
    ensure_client_runtime(project_root, client_id)
    state_file = client_state_path(project_root, client_id)
    with state_file.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(entry) + "\n")


def append_review_started(entries, review_id, review_path, project_root=None, client_id=""):
    client_id = _resolve_client_id(client_id)
    append_state(
        {
            "type": "review",
            "reviewId": review_id,
            "reviewPath": str(review_path),
            "timestamp": utc_now_iso(),
            "status": "pending",
            "files": [{"file": entry["file"], "hash": entry["hash"]} for entry in entries],
            "clientId": client_id,
        },
        project_root,
        client_id=client_id,
    )


def mark_files_reviewed(entries, review_id, project_root=None, client_id=""):
    client_id = _resolve_client_id(client_id)
    timestamp = utc_now_iso()
    for entry in entries:
        append_state(
            {
                "type": "edit",
                "file": entry["file"],
                "hash": entry["hash"],
                "timestamp": timestamp,
                "reviewed": True,
                "reviewId": review_id,
            },
            project_root,
            client_id=client_id,
        )
