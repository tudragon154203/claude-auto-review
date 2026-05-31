from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
from typing import cast

from claude_auto_review.state.edit_record import EditRecord
from claude_auto_review.state.event_types import StateEvent
from claude_auto_review.state.review_records import ReviewMetadata
from claude_auto_review.state.snapshot_helpers import (
    consecutive_stop_block_count,
    edit_entry_key,
    is_edit_entry,
    latest_by_key,
    latest_unreviewed_files,
    parsed_timestamp,
)


@dataclass(frozen=True)
class StateSnapshot:
    """Immutable view over the append-only event log, with cached property accessors."""

    events: list[StateEvent]

    @classmethod
    def from_events(cls, events: list[StateEvent]) -> StateSnapshot:
        return cls(events=list(events))

    @cached_property
    def latest_entries_by_file(self) -> dict[str, StateEvent]:
        return {cast(EditRecord, entry).file: entry for entry in self.events if is_edit_entry(entry)}

    @cached_property
    def latest_review_entries_by_id(self) -> dict[str, StateEvent]:
        return latest_by_key(
            self.events,
            key_fn=lambda e: e.reviewId if isinstance(e, ReviewMetadata) and e.reviewId else None,
            timestamp_fn=lambda e: parsed_timestamp(e.timestamp),
        )

    @cached_property
    def reviewed_hashes_by_file(self) -> dict[str, set[str]]:
        reviewed: dict[str, set[str]] = {}
        for entry in self.events:
            key = edit_entry_key(entry)
            if key is None or not cast(EditRecord, entry).reviewed:
                continue
            file_path, file_hash = key
            reviewed.setdefault(file_path, set()).add(file_hash)
        return reviewed

    def was_hash_reviewed(self, file_path: str, file_hash: str) -> bool:
        return file_hash in self.reviewed_hashes_by_file.get(file_path, set())

    @cached_property
    def unreviewed_files(self) -> list[EditRecord]:
        return latest_unreviewed_files(self.events)

    @cached_property
    def consecutive_stop_blocks(self) -> int:
        return consecutive_stop_block_count(self.events)
