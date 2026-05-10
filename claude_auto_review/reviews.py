from datetime import datetime, timezone
from pathlib import Path


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
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        else:
            ts = ts.astimezone(timezone.utc)
        age_hours = (datetime.now(timezone.utc) - ts).total_seconds() / 3600.0
        return age_hours > timeout_hours
    except (ValueError, TypeError):
        return False


def pending_reviews_for_entries(state, entries):
    needed = {(entry["file"], entry["hash"]) for entry in entries}
    matches = []
    for entry in state:
        if not isinstance(entry, dict) or entry.get("type") != "review" or entry.get("status") != "pending":
            continue
        covered = {
            (item.get("file"), item.get("hash"))
            for item in entry.get("files", [])
            if isinstance(item, dict)
        }
        if needed and needed.issubset(covered):
            matches.append(entry)
    return sorted(matches, key=lambda e: e.get("timestamp", ""), reverse=True)


def is_review_complete(review_path):
    path = Path(review_path)
    if not path.is_file():
        return False
    content = path.read_text(encoding="utf-8", errors="replace")
    if "## Verdict" not in content:
        return False
    verdict = content.split("## Verdict", 1)[1].strip()
    if not verdict:
        return False
    return verdict.lower() not in ("pending", "pending.")
