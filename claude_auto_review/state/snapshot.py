from dataclasses import dataclass
from functools import cached_property

from claude_auto_review.paths.path_utils import is_runtime_relative_path
from claude_auto_review.state.models import EditRecord, ReviewMetadata, StateEvent, StopBlockedRecord
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


@dataclass(frozen=True)
class StateSnapshot:
    events: list[StateEvent]

    @classmethod
    def from_events(cls, events: list[StateEvent]):
        return cls(events=list(events))

    @cached_property
    def latest_entries_by_file(self) -> dict[str, StateEvent]:
        latest: dict[str, StateEvent] = {}
        for entry in self.events:
            if _is_edit_entry(entry):
                latest[entry.file] = entry
        return latest

    @cached_property
    def latest_review_entries_by_id(self) -> dict[str, StateEvent]:
        latest: dict[str, StateEvent] = {}
        latest_keys: dict[str, tuple[object, object]] = {}
        for entry in self.events:
            if not isinstance(entry, ReviewMetadata):
                continue
            review_id = entry.reviewId
            if not review_id:
                continue
            entry_key = _timestamp_sort_key(entry)
            current_key = latest_keys.get(review_id)
            if current_key is None or entry_key >= current_key:
                latest[review_id] = entry
                latest_keys[review_id] = entry_key
        return latest

    @cached_property
    def reviewed_hashes_by_file(self) -> dict[str, set[str]]:
        reviewed: dict[str, set[str]] = {}
        for entry in self.events:
            key = _edit_entry_key(entry)
            if key is None or not entry.reviewed:
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
        last_reviewed_idx = -1
        for idx, entry in enumerate(self.events):
            if _is_edit_entry(entry) and entry.reviewed:
                last_reviewed_idx = idx

        count = 0
        for entry in self.events[last_reviewed_idx + 1 :]:
            if isinstance(entry, StopBlockedRecord):
                count += 1
        return count
