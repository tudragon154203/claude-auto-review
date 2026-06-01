from __future__ import annotations

from claude_auto_review.state.records.review import ReviewMetadata
from claude_auto_review.timestamps import is_older_than_hours


def is_review_expired(review_entry: ReviewMetadata, timeout_hours: float | int) -> bool:
    """Return True if a pending review is older than timeout_hours."""
    if timeout_hours <= 0:
        return False
    if not isinstance(review_entry, ReviewMetadata):
        return False
    timestamp_str = review_entry.timestamp
    if not timestamp_str:
        return False
    return is_older_than_hours(timestamp_str, float(timeout_hours))

