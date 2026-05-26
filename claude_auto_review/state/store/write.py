import json
from pathlib import Path

from claude_auto_review.runtime.client_dirs import client_state_path
from claude_auto_review.paths.path_utils import local_now_iso
from claude_auto_review.runtime.setup import ensure_client_runtime
from claude_auto_review.runtime.context import resolve_client_id, resolve_project_root
from claude_auto_review.state.models import (
    EditRecord,
    ReviewMetadata,
    ReviewFileRecord,
    StateEvent,
)
from claude_auto_review.state.store.writer import StateEventWriter


def write_jsonl_line(path: Path, entry: dict):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(entry, separators=(",", ":"), default=str) + "\n")


def _review_file_entries(entries: list[EditRecord]) -> list[ReviewFileRecord]:
    return [ReviewFileRecord(file=entry.file, hash=entry.hash) for entry in entries]


def _review_state_entry(entries: list[EditRecord], review_id, review_path, client_id, project_root):
    review_path = Path(review_path)
    root = Path(project_root)
    if review_path.is_absolute():
        try:
            review_path = review_path.relative_to(root)
        except ValueError:
            review_path = review_path.relative_to(root.resolve())
    review_path = review_path.as_posix()
    return ReviewMetadata(
        timestamp=local_now_iso(),
        reviewId=review_id,
        reviewPath=review_path,
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


def _write_context(project_root, client_id):
    return resolve_project_root(project_root), resolve_client_id(client_id)


def append_state_event(event: StateEvent, project_root=None, client_id=""):
    project_root, client_id = _write_context(project_root, client_id)
    ensure_client_runtime(project_root, client_id)
    state_file = client_state_path(project_root, client_id)
    write_jsonl_line(state_file, event.to_dict())


def mark_files_reviewed(entries: list[EditRecord], review_id: str, project_root=None, client_id="", timestamp=None):
    project_root, client_id = _write_context(project_root, client_id)
    if not timestamp:
        timestamp = local_now_iso()
    writer = StateEventWriter(project_root, client_id)
    writer.append_marked_reviewed(entries, review_id, timestamp)


def append_review_started(entries: list[EditRecord], review_id: str, review_path: str, project_root=None, client_id=""):
    project_root, client_id = _write_context(project_root, client_id)
    StateEventWriter(project_root, client_id).append(_review_state_entry(entries, review_id, review_path, client_id, project_root))

