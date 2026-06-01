"""State store read operations — raw I/O reads and snapshot loading.

Query functions (get_unreviewed_files, consecutive_stop_blocks, etc.)
live in claude_auto_review/state/store/queries.py.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from claude_auto_review.paths.uri_utils import normalize_relative_path
from claude_auto_review.runtime.context import resolve_client_id, resolve_project_root
from claude_auto_review.state.event_types import StateEvent
from claude_auto_review.state.snapshot import StateSnapshot
from claude_auto_review.state.store.jsonl import parse_jsonl_state_records


def read_jsonl_records(path: str | Path) -> list[tuple[str, dict[str, Any] | None]]:
    """Parse a JSONL file into (raw_line, parsed_dict | None) tuples."""
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


def load_state_snapshot(project_root: str | Path | None = None, client_id: str | None = None) -> StateSnapshot:
    """Load and rebuild the current state snapshot for a client session."""
    from claude_auto_review.runtime.client_dirs import client_state_path

    resolved_root: Path = resolve_project_root(project_root)
    resolved_client: str = resolve_client_id(client_id)
    state_file = client_state_path(resolved_root, resolved_client)
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

