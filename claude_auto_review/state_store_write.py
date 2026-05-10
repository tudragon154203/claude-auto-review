import json

from claude_auto_review.paths import client_state_path, utc_now_iso
from claude_auto_review.runtime_setup import ensure_client_runtime
from claude_auto_review.runtime_helpers import log_event, resolve_client_id, resolve_project_root


def append_state(entry, project_root=None, client_id=""):
    project_root = resolve_project_root(project_root)
    client_id = resolve_client_id(client_id)
    ensure_client_runtime(project_root, client_id)
    state_file = client_state_path(project_root, client_id)
    with state_file.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(entry) + "\n")


def append_review_started(entries, review_id, review_path, project_root=None, client_id=""):
    client_id = resolve_client_id(client_id)
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
    client_id = resolve_client_id(client_id)
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

