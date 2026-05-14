from datetime import datetime

from claude_auto_review.state.models import ReviewMetadata


def _timestamp_str(review_entry: ReviewMetadata) -> str:
    return review_entry.timestamp


def is_review_expired(review_entry: ReviewMetadata, timeout_hours: float | int) -> bool:
    """Return True if a pending review is older than timeout_hours."""
    if timeout_hours <= 0:
        return False
    if not isinstance(review_entry, ReviewMetadata):
        return False
    timestamp_str = _timestamp_str(review_entry)
    if not timestamp_str:
        return False
    try:
        ts_str = timestamp_str
        if ts_str.endswith("Z"):
            ts_str = ts_str[:-1] + "+00:00"
        ts = datetime.fromisoformat(ts_str)
        local_now = datetime.now().astimezone()
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=local_now.tzinfo)
        else:
            ts = ts.astimezone(local_now.tzinfo)
        age_hours = (local_now - ts).total_seconds() / 3600.0
        return age_hours > timeout_hours
    except (ValueError, TypeError):
        return False
