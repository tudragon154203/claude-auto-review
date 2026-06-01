from __future__ import annotations

from datetime import datetime

from claude_auto_review.config.constants.time_units import DURATION_ROUND_PRECISION, SECONDS_PER_HOUR, SECONDS_PER_MINUTE


def local_now_iso():
    return datetime.now().astimezone().isoformat()


def parse_iso_timestamp(ts_str: str) -> datetime:
    """Safely parse ISO timestamp strings, including a trailing 'Z' suffix.

    In Python versions < 3.11, fromisoformat does not support 'Z' automatically.
    """
    if ts_str.endswith("Z"):
        ts_str = ts_str[:-1] + "+00:00"
    return datetime.fromisoformat(ts_str)


def make_timezone_aware(dt: datetime) -> datetime:
    """Ensure datetime is timezone-aware, attaching local timezone to naive datetimes."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=datetime.now().astimezone().tzinfo)
    return dt


def hours_since(timestamp_str: str | None) -> float | None:
    """Calculate hours elapsed since an ISO timestamp. Returns None on parse error."""
    if timestamp_str is None:
        return None
    try:
        ts = parse_iso_timestamp(timestamp_str)
        ts = make_timezone_aware(ts)
        local_now = datetime.now().astimezone()
        return (local_now - ts).total_seconds() / 3600.0
    except (AttributeError, ValueError, TypeError):
        return None


def is_older_than_hours(timestamp_str: str, timeout_hours: float) -> bool:
    """Return True if timestamp is older than timeout_hours."""
    if timeout_hours <= 0:
        return False
    age = hours_since(timestamp_str)
    return age is not None and age > timeout_hours


def duration_seconds(start_timestamp: str | None, end_timestamp: str) -> float | None:
    if not start_timestamp:
        return None
    try:
        started = parse_iso_timestamp(start_timestamp)
        completed = parse_iso_timestamp(end_timestamp)
    except (ValueError, TypeError):
        return None
    return max(0.0, round((completed - started).total_seconds(), DURATION_ROUND_PRECISION))


def format_duration(seconds: float) -> str:
    total_seconds = max(0, round(seconds))
    hours, remainder = divmod(total_seconds, SECONDS_PER_HOUR)
    minutes, seconds = divmod(remainder, SECONDS_PER_MINUTE)
    parts: list[str] = []
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if seconds or not parts:
        parts.append(f"{seconds}s")
    return " ".join(parts)
