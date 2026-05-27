from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from claude_auto_review.paths.uri_utils import normalize_relative_path
from claude_auto_review.runtime.context import resolve_client_id, resolve_project_root
from claude_auto_review.state.models import StateEvent
from claude_auto_review.state.snapshot import StateSnapshot
from claude_auto_review.state.store.jsonl import parse_jsonl_state_records


def read_jsonl_records(path: str | Path) -> list[tuple[str, dict[str, Any] | None]]:
    path = Path(path)
    if not path.exists():
        return []
    records: list[tuple[str, dict[str, Any] | None]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            entry = None
        records.append((line, entry))
    return records


def read_last_jsonl_record(path: str | Path) -> dict[str, Any] | None:
    try:
        last_entry: dict[str, Any] | None = None
        for _, raw in read_jsonl_records(path):
            if isinstance(raw, dict):
                last_entry = raw
        return last_entry
    except OSError:
        return None


def read_jsonl_state_records(path: str | Path) -> list[Any]:
    return parse_jsonl_state_records(read_jsonl_records(path))


def _load_state_events(state_file: str | Path) -> list[StateEvent]:
    return [record.event for record in read_jsonl_state_records(state_file) if record.event is not None]


def _state_snapshot(state: list[StateEvent] | StateSnapshot) -> StateSnapshot:
    if isinstance(state, StateSnapshot):
        return state
    return StateSnapshot.from_events(state)


def ensure_state_snapshot(state_or_snapshot: list[StateEvent] | StateSnapshot) -> StateSnapshot:
    return _state_snapshot(state_or_snapshot)


def load_state_snapshot(project_root: str | Path | None = None, client_id: str | None = None) -> StateSnapshot:
    from claude_auto_review.runtime.client_dirs import client_state_path

    project_root = resolve_project_root(project_root)
    client_id = resolve_client_id(client_id)
    state_file = client_state_path(project_root, client_id)
    return StateSnapshot.from_events(_load_state_events(state_file))


def get_file_hash(file_path: str | Path, project_root: str | Path | None = None) -> str | None:
    project_root = resolve_project_root(project_root)
    relative = normalize_relative_path(file_path, project_root)
    if not relative:
        return None
    full_path = project_root / relative
    if not full_path.is_file():
        return None
    return hashlib.sha256(full_path.read_bytes()).hexdigest()[:8]


def load_state(project_root: str | Path | None = None, client_id: str | None = None) -> list[StateEvent]:
    return list(load_state_snapshot(project_root, client_id).events)


def latest_entries_by_file(state_or_snapshot: list[StateEvent] | StateSnapshot) -> dict[str, StateEvent]:
    return ensure_state_snapshot(state_or_snapshot).latest_entries_by_file


def latest_review_entries_by_id(state_or_snapshot: list[StateEvent] | StateSnapshot) -> dict[str, StateEvent]:
    return ensure_state_snapshot(state_or_snapshot).latest_review_entries_by_id


def reviewed_hashes_by_file(state_or_snapshot: list[StateEvent] | StateSnapshot) -> dict[str, set[str]]:
    return ensure_state_snapshot(state_or_snapshot).reviewed_hashes_by_file


def was_hash_reviewed(state_or_snapshot: list[StateEvent] | StateSnapshot, file_path: str, file_hash: str) -> bool:
    return ensure_state_snapshot(state_or_snapshot).was_hash_reviewed(file_path, file_hash)


def get_unreviewed_files(state_or_snapshot: list[StateEvent] | StateSnapshot) -> list[Any]:
    return ensure_state_snapshot(state_or_snapshot).unreviewed_files


def consecutive_stop_blocks(state_or_snapshot: list[StateEvent] | StateSnapshot) -> int:
    return ensure_state_snapshot(state_or_snapshot).consecutive_stop_blocks
