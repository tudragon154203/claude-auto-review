from datetime import datetime

from claude_auto_review.paths import local_now_iso
from claude_auto_review.state.store_read import get_unreviewed_files, load_state
from claude_auto_review.state.store_write import append_state, log_event, mark_files_reviewed


def _review_entry_for_id(state, review_id):
    for entry in reversed(state):
        if isinstance(entry, dict) and entry.get("type") == "review" and entry.get("reviewId") == review_id:
            return entry
    return None


def _duration_seconds(start_timestamp, end_timestamp):
    if not start_timestamp:
        return None
    try:
        started = datetime.fromisoformat(start_timestamp)
        completed = datetime.fromisoformat(end_timestamp)
    except ValueError:
        return None
    return max(0.0, round((completed - started).total_seconds(), 3))


def _format_duration(seconds):
    total_seconds = max(0, int(round(seconds)))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    parts = []
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if seconds or not parts:
        parts.append(f"{seconds}s")
    return " ".join(parts)


def _review_completed_entry(review_id, covered_entries, state, timestamp, client_id):
    review = _review_entry_for_id(state, review_id)
    entry = {
        "type": "review_completed",
        "reviewId": review_id,
        "timestamp": timestamp,
        "files": [{"file": item["file"], "hash": item["hash"]} for item in covered_entries],
        "clientId": client_id,
    }
    duration = _duration_seconds(review.get("timestamp") if review else None, timestamp)
    if duration is not None:
        entry["duration"] = _format_duration(duration)
        entry["durationSeconds"] = duration
    return entry


def apply_completed_review(project_root, client_id, review_id, covered_entries):
    state_before = load_state(project_root, client_id)
    timestamp = local_now_iso()
    append_state(
        _review_completed_entry(review_id, covered_entries, state_before, timestamp, client_id),
        project_root,
        client_id=client_id,
    )
    mark_files_reviewed(covered_entries, review_id, project_root, client_id=client_id, timestamp=timestamp)
    log_event(project_root, "stop_approved", reason="review_completed", reviewId=review_id)
    remaining = get_unreviewed_files(load_state(project_root, client_id))
    if remaining:
        log_event(project_root, "stop_blocked_after_partial_review", remaining=[entry["file"] for entry in remaining])
        append_state({"type": "stop_blocked", "reason": "partial_review", "timestamp": local_now_iso()}, project_root, client_id=client_id)
    return remaining
