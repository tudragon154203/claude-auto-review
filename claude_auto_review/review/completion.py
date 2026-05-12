from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from claude_auto_review.paths import local_now_iso
from claude_auto_review.state.models import ReviewCompletedRecord, StopBlockedRecord
from claude_auto_review.state.store_read import get_unreviewed_files, load_state
from claude_auto_review.state.store_write import append_state, mark_files_reviewed


def _review_entry_for_id(state: list[dict[str, Any]], review_id: str) -> dict[str, Any] | None:
    for entry in reversed(state):
        if isinstance(entry, dict) and entry.get("type") == "review" and entry.get("reviewId") == review_id:
            return entry
    return None


def _duration_seconds(start_timestamp: str | None, end_timestamp: str) -> float | None:
    if not start_timestamp:
        return None
    try:
        started = datetime.fromisoformat(start_timestamp)
        completed = datetime.fromisoformat(end_timestamp)
    except ValueError:
        return None
    return max(0.0, round((completed - started).total_seconds(), 3))


def _format_duration(seconds: float) -> str:
    total_seconds = max(0, int(round(seconds)))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    parts: list[str] = []
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if seconds or not parts:
        parts.append(f"{seconds}s")
    return " ".join(parts)


def _review_completed_entry(
    review_id: str,
    covered_entries: list[dict[str, str]],
    state: list[dict[str, Any]],
    timestamp: str,
    client_id: str,
) -> ReviewCompletedRecord:
    review = _review_entry_for_id(state, review_id)
    duration = _duration_seconds(review.get("timestamp") if review else None, timestamp)
    return ReviewCompletedRecord(
        timestamp=timestamp,
        reviewId=review_id,
        files=[{"file": item["file"], "hash": item["hash"]} for item in covered_entries],
        clientId=client_id,
        duration=_format_duration(duration) if duration is not None else None,
        durationSeconds=duration,
    )


def apply_completed_review(
    project_root: Path,
    client_id: str,
    review_id: str,
    covered_entries: list[dict[str, str]],
) -> list[dict[str, Any]]:
    for item in covered_entries:
        if not isinstance(item, dict) or "file" not in item or "hash" not in item:
            raise ValueError(f"covered_entries item missing 'file' or 'hash': {item!r}")

    state_before = load_state(project_root, client_id)
    timestamp = local_now_iso()
    append_state(
        _review_completed_entry(review_id, covered_entries, state_before, timestamp, client_id),
        project_root,
        client_id=client_id,
    )
    mark_files_reviewed(covered_entries, review_id, project_root, client_id=client_id, timestamp=timestamp)
    remaining = get_unreviewed_files(load_state(project_root, client_id))
    if remaining:
        append_state(
            StopBlockedRecord(timestamp=local_now_iso(), reason="partial_review", reviewId=review_id, files=[e["file"] for e in remaining]),
            project_root,
            client_id=client_id,
        )
    return remaining
