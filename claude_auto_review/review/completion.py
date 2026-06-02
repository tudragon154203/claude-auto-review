"""Record completed review state transitions."""

from __future__ import annotations

from pathlib import Path

from claude_auto_review.timestamps import local_now_iso
from claude_auto_review.state.records.edit import EditRecord
from claude_auto_review.state.records.edit import StopBlockedRecord
from claude_auto_review.state.records.file import ReviewFileRecord
from claude_auto_review.state.records.review import ReviewCompletedRecord, ReviewMetadata
from claude_auto_review.state.records.events import StateEvent
from claude_auto_review.state.store.read import load_state_snapshot
from claude_auto_review.state.store.queries import get_unreviewed_files
from claude_auto_review.state.store.write import append_state_event, mark_files_reviewed
from claude_auto_review.timestamps import duration_seconds, format_duration

REASON_PARTIAL_REVIEW = "partial_review"


def _append_partial_review_block(
    project_root: Path,
    client_id: str,
    review_id: str,
    remaining: list[EditRecord],
) -> None:
    if not remaining:
        return
    append_state_event(
        StopBlockedRecord(
            timestamp=local_now_iso(),
            reason=REASON_PARTIAL_REVIEW,
            reviewId=review_id,
            files=[entry.file for entry in remaining],
        ),
        project_root,
        client_id=client_id,
    )


def _review_entry_for_id(state: list[StateEvent], review_id: str) -> ReviewMetadata | None:
    for entry in reversed(state):
        if isinstance(entry, ReviewMetadata) and entry.reviewId == review_id:
            return entry
    return None


def _validate_entries(covered_entries: list) -> list[EditRecord]:
    validated: list[EditRecord] = []
    for item in covered_entries:
        if isinstance(item, EditRecord):
            validated.append(item)
            continue
        raise ValueError("covered_entries must contain EditRecord instances")
    return validated


def _build_review_completed_record(
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


def _append_review_started(project_root: Path, client_id: str, review_id: str) -> None:
    append_state_event(
        ReviewMetadata(
            timestamp=local_now_iso(),
            reviewId=review_id,
            reviewPath="",
            files=[],
            clientId=client_id,
            status="completed",
        ),
        project_root,
        client_id=client_id,
    )


def _append_completed_record(
    completed_record: ReviewCompletedRecord,
    project_root: Path,
    client_id: str,
) -> None:
    append_state_event(completed_record, project_root, client_id=client_id)


def _build_and_append_records(
    project_root: Path,
    client_id: str,
    review_id: str,
    covered_entries: list[EditRecord],
) -> None:
    validated_entries = _validate_entries(covered_entries)
    state_before = list(load_state_snapshot(project_root, client_id).events)
    timestamp = local_now_iso()

    _append_review_started(project_root, client_id, review_id)
    completed_record = _build_review_completed_record(
        review_id, validated_entries, state_before, timestamp, client_id
    )
    _append_completed_record(completed_record, project_root, client_id)
    mark_files_reviewed(validated_entries, review_id, project_root, client_id=client_id, timestamp=timestamp)


def record_completed_review(
    project_root: Path,
    client_id: str,
    review_id: str,
    covered_entries: list[EditRecord],
) -> None:
    _build_and_append_records(project_root, client_id, review_id, covered_entries)


def _query_remaining_unreviewed_files(project_root: Path, client_id: str) -> list[EditRecord]:
    return get_unreviewed_files(load_state_snapshot(project_root, client_id))


def apply_completed_review(
    project_root: Path,
    client_id: str,
    review_id: str,
    covered_entries: list[EditRecord],
) -> list[EditRecord]:
    record_completed_review(project_root, client_id, review_id, covered_entries)
    remaining = _query_remaining_unreviewed_files(project_root, client_id)
    _append_partial_review_block(project_root, client_id, review_id, remaining)
    return remaining
