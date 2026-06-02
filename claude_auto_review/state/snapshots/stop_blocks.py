from __future__ import annotations

from claude_auto_review.state.records.edit import EditRecord, StopBlockedRecord
from claude_auto_review.state.records.review import ReviewMetadata
from claude_auto_review.state.records.events import StateEvent


def consecutive_stop_block_count(entries: list[StateEvent]) -> int:
    count = 0
    for entry in reversed(entries):
        if isinstance(entry, ReviewMetadata):
            continue
        if isinstance(entry, EditRecord) and not entry.reviewed:
            continue
        if isinstance(entry, StopBlockedRecord):
            count += 1
            continue
        break
    return count

