from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from functools import cached_property
from typing import Any, cast

from claude_auto_review.paths.path_utils import is_runtime_relative_path
from claude_auto_review.state.models import EditRecord, ReviewMetadata, StateEvent, StopBlockedRecord
from claude_auto_review.timestamps import parse_iso_timestamp


def _parsed_timestamp(timestamp: str) -> datetime | None:
    if not timestamp:
        return None
    try:
        return parse_iso_timestamp(timestamp)
    except (AttributeError, TypeError, ValueError):
        return None


def _is_edit_entry(entry: StateEvent) -> bool:
    return isinstance(entry, EditRecord) and bool(entry.file) and bool(entry.hash)


def _edit_entry_key(entry: StateEvent) -> tuple[str, str] | None:
    if not _is_edit_entry(entry):
        return None
    return cast(EditRecord, entry).file, cast(EditRecord, entry).hash


def _latest_by_key(
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


@dataclass(frozen=True)
class StateSnapshot:
    """Immutable view over the append-only event log, with cached property accessors."""

    events: list[StateEvent]

    @classmethod
    def from_events(cls, events: list[StateEvent]) -> StateSnapshot:
        return cls(events=list(events))

    @cached_property
    def latest_entries_by_file(self) -> dict[str, StateEvent]:
        return {cast(EditRecord, entry).file: entry for entry in self.events if _is_edit_entry(entry)}

    @cached_property
    def latest_review_entries_by_id(self) -> dict[str, StateEvent]:
        return _latest_by_key(
            self.events,
            key_fn=lambda e: e.reviewId if isinstance(e, ReviewMetadata) and e.reviewId else None,
            timestamp_fn=lambda e: _parsed_timestamp(e.timestamp),
        )

    @cached_property
    def reviewed_hashes_by_file(self) -> dict[str, set[str]]:
        reviewed: dict[str, set[str]] = {}
        for entry in self.events:
            key = _edit_entry_key(entry)
            if key is None or not cast(EditRecord, entry).reviewed:
                continue
            file_path, file_hash = key
            reviewed.setdefault(file_path, set()).add(file_hash)
        return reviewed

    def was_hash_reviewed(self, file_path: str, file_hash: str) -> bool:
        return file_hash in self.reviewed_hashes_by_file.get(file_path, set())

    @cached_property
    def unreviewed_files(self) -> list[EditRecord]:
        return [
            entry
            for entry in self.latest_entries_by_file.values()
            if isinstance(entry, EditRecord)
            and not entry.reviewed
            and not entry.deleted
            and not is_runtime_relative_path(entry.file)
        ]

    @cached_property
    def consecutive_stop_blocks(self) -> int:
        count = 0
        for entry in reversed(self.events):
            if isinstance(entry, StopBlockedRecord):
                count += 1
                continue
            if isinstance(entry, ReviewMetadata) or (isinstance(entry, EditRecord) and not entry.reviewed):
                continue
            break
        return count
