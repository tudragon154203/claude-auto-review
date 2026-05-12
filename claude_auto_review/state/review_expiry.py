from datetime import datetime


def is_review_expired(review_entry, timeout_hours):
    """Return True if a pending review is older than timeout_hours."""
    if timeout_hours <= 0:
        return False
    timestamp_str = review_entry.get("timestamp")
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
