import json

from claude_auto_review.paths import client_state_path, utc_now_iso
from claude_auto_review.runtime.setup import ensure_client_runtime
from claude_auto_review.runtime.helpers import log_event, resolve_client_id, resolve_project_root


def _append_jsonl_state(entry, project_root, client_id):
    ensure_client_runtime(project_root, client_id)
    state_file = client_state_path(project_root, client_id)
    with state_file.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(entry) + "\n")


def _review_file_entries(entries):
    return [{"file": entry["file"], "hash": entry["hash"]} for entry in entries]


def _review_state_entry(entries, review_id, review_path, client_id):
    return {
        "type": "review",
        "reviewId": review_id,
        "reviewPath": str(review_path),
        "timestamp": utc_now_iso(),
        "status": "pending",
        "files": _review_file_entries(entries),
        "clientId": client_id,
    }


def _reviewed_edit_entry(entry, review_id, timestamp):
    return {
        "type": "edit",
        "file": entry["file"],
        "hash": entry["hash"],
        "timestamp": timestamp,
        "reviewed": True,
        "reviewId": review_id,
    }


def _write_context(project_root, client_id):
    return resolve_project_root(project_root), resolve_client_id(client_id)


def append_state(entry, project_root=None, client_id=""):
    project_root, client_id = _write_context(project_root, client_id)
    _append_jsonl_state(entry, project_root, client_id)


def append_review_started(entries, review_id, review_path, project_root=None, client_id=""):
    project_root, client_id = _write_context(project_root, client_id)
    _append_jsonl_state(_review_state_entry(entries, review_id, review_path, client_id), project_root, client_id)


def mark_files_reviewed(entries, review_id, project_root=None, client_id=""):
    project_root, client_id = _write_context(project_root, client_id)
    timestamp = utc_now_iso()
    for entry in entries:
        _append_jsonl_state(_reviewed_edit_entry(entry, review_id, timestamp), project_root, client_id)
