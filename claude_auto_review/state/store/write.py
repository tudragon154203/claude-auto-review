from __future__ import annotations

import json
from pathlib import Path

from claude_auto_review.runtime.client_dirs import client_state_path
from claude_auto_review.runtime.context import resolve_client_id, resolve_project_root
from claude_auto_review.runtime.setup import ensure_client_runtime
from claude_auto_review.state.records.edit import EditRecord
from claude_auto_review.state.records.events import StateEvent
from claude_auto_review.state.records.file import ReviewFileRecord
from claude_auto_review.state.records.review import ReviewMetadata
from claude_auto_review.timestamps import local_now_iso


def write_jsonl_line(path: Path, entry: dict):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(entry, separators=(",", ":"), default=str) + "\n")


def _normalize_review_path(review_path: str | Path, project_root: str | Path) -> str:
    review_path = Path(review_path)
    root = Path(project_root)
    if review_path.is_absolute():
        try:
            review_path = review_path.relative_to(root)
        except ValueError:
            review_path = review_path.relative_to(root.resolve())
    return review_path.as_posix()


def _review_file_entries(entries: list[EditRecord]) -> list[ReviewFileRecord]:
    return [ReviewFileRecord(file=entry.file, hash=entry.hash) for entry in entries]


def _review_state_entry(entries: list[EditRecord], review_id, review_path, client_id, project_root):
    return ReviewMetadata(
        timestamp=local_now_iso(),
        reviewId=review_id,
        reviewPath=_normalize_review_path(review_path, project_root),
        files=_review_file_entries(entries),
        clientId=client_id,
    )


def _reviewed_edit_entry(entry: EditRecord, review_id: str, timestamp: str) -> EditRecord:
    return EditRecord(
        timestamp=timestamp,
        file=entry.file,
        hash=entry.hash,
        reviewed=True,
        reviewId=review_id,
    )


def _resolve_state_file(project_root=None, client_id="") -> tuple[Path, Path, str]:
    resolved_root: Path = resolve_project_root(project_root)
    resolved_client: str = resolve_client_id(client_id)
    return resolved_root, client_state_path(resolved_root, resolved_client), resolved_client


def append_state_event(event: StateEvent, project_root=None, client_id=""):
    """Append a state event to the client JSONL state file."""
    resolved_root, state_file, resolved_client = _resolve_state_file(project_root, client_id)
    ensure_client_runtime(resolved_root, resolved_client)
    write_jsonl_line(state_file, event.to_dict())


def mark_files_reviewed(entries: list[EditRecord], review_id: str, project_root=None, client_id="", timestamp=None):
    """Write reviewed-edit entries for each entry to the state file."""
    if not timestamp:
        timestamp = local_now_iso()
    for entry in entries:
        append_state_event(_reviewed_edit_entry(entry, review_id, timestamp), project_root, client_id=client_id)


def append_review_started(entries: list[EditRecord], review_id: str, review_path: str, project_root=None, client_id=""):
    """Write a review-started metadata entry to the state file."""
    resolved_root, state_file, resolved_client = _resolve_state_file(project_root, client_id)
    ensure_client_runtime(resolved_root, resolved_client)
    write_jsonl_line(
        state_file,
        _review_state_entry(entries, review_id, review_path, resolved_client, resolved_root).to_dict(),
    )
