from __future__ import annotations

from claude_auto_review.state.edit_record import EditRecord
from claude_auto_review.state.review_records import ReviewMetadata
from claude_auto_review.state.event_types import StateEvent


def consecutive_stop_block_count(entries: list[StateEvent]) -> int:
    count = 0
    for entry in reversed(entries):
        if isinstance(entry, ReviewMetadata):
            continue
        if isinstance(entry, EditRecord) and not entry.reviewed:
            continue
        if getattr(entry, "type", None) == "stop_blocked":
            count += 1
            continue
        break
    return count

