from datetime import datetime


def parse_iso_timestamp(ts_str: str) -> datetime:
    """Safely parse ISO timestamp strings, including a trailing 'Z' suffix.

    In Python versions < 3.11, fromisoformat does not support 'Z' automatically.
    """
    if ts_str.endswith("Z"):
        ts_str = ts_str[:-1] + "+00:00"
    return datetime.fromisoformat(ts_str)


def make_timezone_aware(dt: datetime) -> datetime:
    """Ensure datetime is timezone-aware, converting to local timezone if needed."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=datetime.now().astimezone().tzinfo)
    return dt.astimezone()


def hours_since(timestamp_str: str) -> float | None:
    """Calculate hours elapsed since an ISO timestamp. Returns None on parse error."""
    try:
        ts = parse_iso_timestamp(timestamp_str)
        ts = make_timezone_aware(ts)
        local_now = datetime.now().astimezone()
        return (local_now - ts).total_seconds() / 3600.0
    except (ValueError, TypeError):
        return None


def is_older_than_hours(timestamp_str: str, timeout_hours: float) -> bool:
    """Return True if timestamp is older than timeout_hours."""
    if timeout_hours <= 0:
        return False
    age = hours_since(timestamp_str)
    return age is not None and age > timeout_hours
