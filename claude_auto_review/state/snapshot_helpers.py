from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any, cast

from claude_auto_review.state.edit_record import EditRecord
from claude_auto_review.state.event_types import StateEvent
from claude_auto_review.paths.path_utils import is_runtime_relative_path
from claude_auto_review.timestamps import parse_iso_timestamp


def parsed_timestamp(timestamp: str) -> datetime | None:
    if not timestamp:
        return None
    try:
        return parse_iso_timestamp(timestamp)
    except (AttributeError, TypeError, ValueError):
        return None


def is_edit_entry(entry: StateEvent) -> bool:
    return isinstance(entry, EditRecord) and bool(entry.file) and bool(entry.hash)


def edit_entry_key(entry: StateEvent) -> tuple[str, str] | None:
    if not is_edit_entry(entry):
        return None
    return cast(EditRecord, entry).file, cast(EditRecord, entry).hash


def latest_by_key(
    entries: list[StateEvent],
    key_fn: Callable[[StateEvent], Any],
    timestamp_fn: Callable[[StateEvent], datetime | None] | None = None,
) -> dict[Any, StateEvent]:
    latest: dict[Any, StateEvent] = {}
    latest_timestamps: dict[Any, datetime | None] = {}
    for entry in entries:
        key = key_fn(entry)
        if key is None:
            continue
        entry_timestamp = timestamp_fn(entry) if timestamp_fn is not None else None
        current_entry = latest.get(key)
        if current_entry is None:
            latest[key] = entry
            latest_timestamps[key] = entry_timestamp
            continue
        current_timestamp = latest_timestamps.get(key)
        if current_timestamp is None or (entry_timestamp is not None and entry_timestamp >= current_timestamp):
            latest[key] = entry
            latest_timestamps[key] = entry_timestamp
    return latest


def latest_unreviewed_files(entries: list[StateEvent]) -> list[EditRecord]:
    latest_entries = {cast(EditRecord, entry).file: entry for entry in entries if is_edit_entry(entry)}
    return [
        entry
        for entry in latest_entries.values()
        if isinstance(entry, EditRecord) and not entry.reviewed and not entry.deleted and not is_runtime_relative_path(entry.file)
    ]


