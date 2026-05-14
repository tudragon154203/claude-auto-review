import hashlib
import json
from pathlib import Path

from claude_auto_review.paths import is_runtime_relative_path, normalize_relative_path
from claude_auto_review.runtime.context import resolve_client_id, resolve_project_root
from claude_auto_review.state.models import (
    EditRecord,
    ReviewMetadata,
    StateEvent,
    StopBlockedRecord,
    parse_event,
)
from claude_auto_review.utils.datetime_utils import parse_iso_timestamp


def _timestamp_value(entry: StateEvent) -> str:
    return entry.timestamp if hasattr(entry, "timestamp") else ""


def _timestamp_sort_key(entry: StateEvent):
    timestamp = _timestamp_value(entry)
    if not timestamp:
        return (0, "")
    try:
        return (1, parse_iso_timestamp(timestamp))
    except (TypeError, ValueError):
        return (0, timestamp)


def _is_edit_entry(entry: StateEvent) -> bool:
    return isinstance(entry, EditRecord) and bool(entry.file) and bool(entry.hash)


def _edit_entry_key(entry: StateEvent) -> tuple[str, str] | None:
    if not _is_edit_entry(entry):
        return None
    return entry.file, entry.hash


def read_jsonl_records(path):
    path = Path(path)
    if not path.exists():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            entry = None
        records.append((line, entry))
    return records


def get_file_hash(file_path, project_root=None):
    project_root = resolve_project_root(project_root)
    relative = normalize_relative_path(file_path, project_root)
    if not relative:
        return None
    full_path = project_root / relative
    if not full_path.is_file():
        return None
    return hashlib.sha256(full_path.read_bytes()).hexdigest()[:8]


def load_state(project_root=None, client_id=None):
    from claude_auto_review.paths import client_state_path

    project_root = resolve_project_root(project_root)
    client_id = resolve_client_id(client_id)
    state_file = client_state_path(project_root, client_id)
    state: list[StateEvent] = []
    for line, raw in read_jsonl_records(state_file):
        if not isinstance(raw, dict):
            continue
        event = parse_event(raw)
        if event is not None:
            state.append(event)
    return state


def latest_entries_by_file(state: list[StateEvent]) -> dict[str, StateEvent]:
    latest: dict[str, StateEvent] = {}
    for entry in state:
        if _is_edit_entry(entry):
            file_path = entry.file
            latest[file_path] = entry
    return latest


def latest_review_entries_by_id(state: list[StateEvent]) -> dict[str, StateEvent]:
    latest: dict[str, StateEvent] = {}
    for entry in state:
        if not isinstance(entry, ReviewMetadata):
            continue
        review_id = entry.reviewId
        if not review_id:
            continue
        current = latest.get(review_id)
        if current is None or _timestamp_sort_key(entry) >= _timestamp_sort_key(current):
            latest[review_id] = entry
    return latest


def reviewed_hashes_by_file(state: list[StateEvent]) -> dict[str, set[str]]:
    reviewed: dict[str, set[str]] = {}
    for entry in state:
        key = _edit_entry_key(entry)
        if key is None or not entry.reviewed:
            continue
        file_path, file_hash = key
        reviewed.setdefault(file_path, set()).add(file_hash)
    return reviewed


def was_hash_reviewed(state: list[StateEvent], file_path: str, file_hash: str) -> bool:
    return file_hash in reviewed_hashes_by_file(state).get(file_path, set())


def get_unreviewed_files(state: list[StateEvent]) -> list[EditRecord]:
    return [
        entry
        for entry in latest_entries_by_file(state).values()
        if isinstance(entry, EditRecord)
        and not entry.reviewed
        and not entry.deleted
        and not is_runtime_relative_path(entry.file)
    ]


def consecutive_stop_blocks(state: list[StateEvent]) -> int:
    last_reviewed_idx = -1
    for idx, entry in enumerate(state):
        if _is_edit_entry(entry) and entry.reviewed:
            last_reviewed_idx = idx

    count = 0
    for entry in state[last_reviewed_idx + 1 :]:
        if isinstance(entry, StopBlockedRecord):
            count += 1
    return count
