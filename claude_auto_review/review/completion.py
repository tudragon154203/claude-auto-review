from __future__ import annotations

from pathlib import Path

from claude_auto_review.paths.path_utils import local_now_iso
from claude_auto_review.state.edit_record import EditRecord, StopBlockedRecord
from claude_auto_review.state.file_record import ReviewFileRecord
from claude_auto_review.state.review_records import ReviewCompletedRecord, ReviewMetadata
from claude_auto_review.state.event_types import StateEvent
from claude_auto_review.state.store.queries import get_unreviewed_files
from claude_auto_review.state.store.read import load_state, load_state_snapshot
from claude_auto_review.state.store.write import append_state_event, mark_files_reviewed
from claude_auto_review.timestamps import duration_seconds, format_duration

REASON_PARTIAL_REVIEW = "partial_review"


def _review_entry_for_id(state: list[StateEvent], review_id: str) -> ReviewMetadata | None:
    for entry in reversed(state):
        if isinstance(entry, ReviewMetadata) and entry.reviewId == review_id:
            return entry
    return None


def _validate_covered_entries(covered_entries: list[EditRecord]) -> list[EditRecord]:
    validated: list[EditRecord] = []
    for item in covered_entries:
        if isinstance(item, EditRecord):
            validated.append(item)
            continue
        raise ValueError("covered_entries must contain EditRecord instances")
    return validated


def _review_completed_entry(
    review_id: str,
    validated_entries: list[EditRecord],
    state_before: list[StateEvent],
    timestamp: str,
    client_id: str,
) -> ReviewCompletedRecord:
    review = _review_entry_for_id(state_before, review_id)
    duration = duration_seconds(review.timestamp if review else None, timestamp)
    return ReviewCompletedRecord(
        timestamp=timestamp,
        reviewId=review_id,
        files=[ReviewFileRecord(file=entry.file, hash=entry.hash) for entry in validated_entries],
        clientId=client_id,
        duration=format_duration(duration) if duration is not None else None,
        durationSeconds=duration,
    )


def _review_status_completed_entry(review_id: str, client_id: str) -> ReviewMetadata:
    return ReviewMetadata(
        timestamp=local_now_iso(),
        reviewId=review_id,
        reviewPath="",
        files=[],
        clientId=client_id,
        status="completed",
    )


def record_completed_review(
    project_root: Path,
    client_id: str,
    review_id: str,
    covered_entries: list[EditRecord],
) -> None:
    """Append a ReviewCompletedRecord and mark covered file hashes as reviewed."""
    validated_entries = _validate_covered_entries(covered_entries)
    state_before = load_state(project_root, client_id)
    timestamp = local_now_iso()
    completed_review = _review_status_completed_entry(review_id, client_id)
    append_state_event(completed_review, project_root, client_id=client_id)
    append_state_event(
        _review_completed_entry(review_id, validated_entries, state_before, timestamp, client_id),
        project_root,
        client_id=client_id,
    )
    mark_files_reviewed(validated_entries, review_id, project_root, client_id=client_id, timestamp=timestamp)


def apply_completed_review(
    project_root: Path,
    client_id: str,
    review_id: str,
    covered_entries: list[EditRecord],
) -> list[EditRecord]:
    """Record the completed review and return remaining unreviewed file entries."""
    record_completed_review(project_root, client_id, review_id, covered_entries)
    remaining = get_unreviewed_files(load_state_snapshot(project_root, client_id))
    if remaining:
        append_state_event(
            StopBlockedRecord(
                timestamp=local_now_iso(),
                reason=REASON_PARTIAL_REVIEW,
                reviewId=review_id,
                files=[e.file for e in remaining],
            ),
            project_root,
            client_id=client_id,
        )
    return remaining

