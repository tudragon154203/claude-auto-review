"""State query functions operating on parsed snapshots.

These functions derive computed views from StateSnapshot instances.
Separated from store/read.py (raw I/O reads) to keep read and query
concerns independent.
"""

from __future__ import annotations

from claude_auto_review.state.records.edit import EditRecord
from claude_auto_review.state.records.events import StateEvent
from claude_auto_review.state.snapshots.snapshot import StateSnapshot


def _state_snapshot(state: list[StateEvent] | StateSnapshot) -> StateSnapshot:
    if isinstance(state, StateSnapshot):
        return state
    return StateSnapshot.from_events(state)


def ensure_state_snapshot(state_or_snapshot: list[StateEvent] | StateSnapshot) -> StateSnapshot:
    return _state_snapshot(state_or_snapshot)


def latest_entries_by_file(state_or_snapshot: list[StateEvent] | StateSnapshot) -> dict[str, StateEvent]:
    return ensure_state_snapshot(state_or_snapshot).latest_entries_by_file


def latest_review_entries_by_id(state_or_snapshot: list[StateEvent] | StateSnapshot) -> dict[str, StateEvent]:
    return ensure_state_snapshot(state_or_snapshot).latest_review_entries_by_id


def reviewed_hashes_by_file(state_or_snapshot: list[StateEvent] | StateSnapshot) -> dict[str, set[str]]:
    return ensure_state_snapshot(state_or_snapshot).reviewed_hashes_by_file


def was_hash_reviewed(state_or_snapshot: list[StateEvent] | StateSnapshot, file_path: str, file_hash: str) -> bool:
    return ensure_state_snapshot(state_or_snapshot).was_hash_reviewed(file_path, file_hash)


def get_unreviewed_files(state_or_snapshot: list[StateEvent] | StateSnapshot) -> list[EditRecord]:
    """Return file paths whose latest content hash has not been covered by a review."""
    return ensure_state_snapshot(state_or_snapshot).unreviewed_files


def consecutive_stop_blocks(state_or_snapshot: list[StateEvent] | StateSnapshot) -> int:
    """Count how many stop_blocked events appear at the tail of the event log."""
    return ensure_state_snapshot(state_or_snapshot).consecutive_stop_blocks

