import json
from pathlib import Path
from typing import Any

from claude_auto_review.paths import client_state_path, local_now_iso
from claude_auto_review.runtime.setup import ensure_client_runtime
from claude_auto_review.runtime.helpers import log_event, resolve_client_id, resolve_project_root
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


def apply_completed_review(project_root: Path, client_id: str, review_id: str, covered_entries: list[dict[str, str]]) -> list[dict[str, Any]]:
    from claude_auto_review.review.completion import (
        _apply_completed_review_validated,
        _validate_covered_entries,
    )

    validated_entries = _validate_covered_entries(covered_entries)
    # Keep the legacy telemetry hooks here while the completion module owns the state transition.
    log_event(project_root, "stop_approved", reason="review_completed", reviewId=review_id)
    remaining = _apply_completed_review_validated(project_root, client_id, review_id, validated_entries)

    if remaining:
        log_event(project_root, "stop_blocked_after_partial_review", reviewId=review_id, remaining=[e["file"] for e in remaining])

    return remaining
