from __future__ import annotations

from collections.abc import Iterable, Iterator, Sequence

from claude_auto_review.runtime.events import log_event
from claude_auto_review.state.edit_record import EditRecord
from claude_auto_review.state.event_types import StateEvent
from claude_auto_review.state.file_record import ReviewFileRecord
from claude_auto_review.state.review_records import ReviewMetadata
from claude_auto_review.state.reviews.expiry import is_review_expired
from claude_auto_review.state.reviews.matching_hash import entry_file_hash_pairs, review_file_hash_pairs
from claude_auto_review.state.store.queries import ensure_state_snapshot


def _is_pending_review_entry(entry: StateEvent) -> bool:
    return isinstance(entry, ReviewMetadata) and entry.status == "pending"


def _sorted_by_timestamp_desc(entries: Sequence[ReviewMetadata]) -> list[ReviewMetadata]:
    return sorted(entries, key=lambda entry: entry.timestamp, reverse=True)


def _log_expired_review(project_root, review_entry: ReviewMetadata, client_id=None) -> None:
    log_event(
        project_root,
        "stop_review_expired",
        client_id=client_id,
        review_id=review_entry.reviewId,
        files=[f.file for f in review_entry.files],
    )


def _pending_review_match_info(
    state: list[StateEvent],
    entries: Sequence[EditRecord | ReviewFileRecord],
    project_root=None,
    timeout_hours=0,
) -> Iterator[tuple[ReviewMetadata, set[tuple[str, str]], set[tuple[str, str]]]]:
    needed = entry_file_hash_pairs(entries)
    if not needed:
        return

    snapshot = ensure_state_snapshot(state)
    for entry in snapshot.latest_review_entries_by_id.values():
        if not _is_pending_review_entry(entry):
            continue
        if not isinstance(entry, ReviewMetadata):
            continue
        if timeout_hours and is_review_expired(entry, timeout_hours):
            _log_expired_review(project_root, entry)
            continue
        covered = review_file_hash_pairs(entry)
        overlap = needed & covered
        yield entry, covered, overlap


def _pending_reviews_matching_entries(
    state: list[StateEvent],
    entries: Sequence[EditRecord | ReviewFileRecord],
    project_root=None,
    timeout_hours=0,
) -> tuple[
    set[tuple[str, str]],
    Iterable[tuple[ReviewMetadata, set[tuple[str, str]], set[tuple[str, str]]]],
]:
    needed = entry_file_hash_pairs(entries)
    if not needed:
        return needed, ()
    return needed, _pending_review_match_info(
        state,
        entries,
        project_root=project_root,
        timeout_hours=timeout_hours,
    )

