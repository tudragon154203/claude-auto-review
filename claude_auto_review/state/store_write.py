import json

from claude_auto_review.paths import client_state_path, local_now_iso
from claude_auto_review.runtime.setup import ensure_client_runtime
from claude_auto_review.runtime.helpers import resolve_client_id, resolve_project_root
from claude_auto_review.state.models import (
    EditRecord,
    ReviewMetadata,
    StateEvent,
)


def _append_jsonl_state(entry, project_root, client_id):
    ensure_client_runtime(project_root, client_id)
    state_file = client_state_path(project_root, client_id)
    with state_file.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(entry) + "\n")


def _review_file_entries(entries):
    return [{"file": entry["file"], "hash": entry["hash"]} for entry in entries]


def _review_state_entry(entries, review_id, review_path, client_id):
    return ReviewMetadata(
        timestamp=local_now_iso(),
        reviewId=review_id,
        reviewPath=str(review_path),
        files=_review_file_entries(entries),
        clientId=client_id,
    )


def _reviewed_edit_entry(entry, review_id, timestamp):
    return EditRecord(
        timestamp=timestamp,
        file=entry["file"],
        hash=entry["hash"],
        reviewed=True,
        reviewId=review_id,
    )


def _write_context(project_root, client_id):
    return resolve_project_root(project_root), resolve_client_id(client_id)


def append_state(event: StateEvent | dict, project_root=None, client_id=""):
    project_root, client_id = _write_context(project_root, client_id)
    if isinstance(event, dict):
        _append_jsonl_state(event, project_root, client_id)
    else:
        _append_jsonl_state(event.to_dict(), project_root, client_id)


def append_review_started(entries, review_id, review_path, project_root=None, client_id=""):
    project_root, client_id = _write_context(project_root, client_id)
    event = _review_state_entry(entries, review_id, review_path, client_id)
    _append_jsonl_state(event.to_dict(), project_root, client_id)


def mark_files_reviewed(entries, review_id, project_root=None, client_id="", timestamp=None):
    project_root, client_id = _write_context(project_root, client_id)
    timestamp = timestamp or local_now_iso()
    for entry in entries:
        event = _reviewed_edit_entry(entry, review_id, timestamp)
        _append_jsonl_state(event.to_dict(), project_root, client_id)
