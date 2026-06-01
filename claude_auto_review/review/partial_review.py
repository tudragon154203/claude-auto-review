from __future__ import annotations

from pathlib import Path

from claude_auto_review.paths.path_utils import local_now_iso
from claude_auto_review.state.edit_record import EditRecord, StopBlockedRecord
from claude_auto_review.state.store.queries import get_unreviewed_files
from claude_auto_review.state.store.read import load_state_snapshot
from claude_auto_review.state.store.write import append_state_event

REASON_PARTIAL_REVIEW = "partial_review"


def get_remaining_unreviewed_entries(project_root: Path, client_id: str) -> list[EditRecord]:
    return get_unreviewed_files(load_state_snapshot(project_root, client_id))


def record_partial_review_block(
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

