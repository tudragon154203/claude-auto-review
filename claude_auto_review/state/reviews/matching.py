from __future__ import annotations

from collections.abc import Iterable, Iterator, Sequence
from typing import TypedDict

from claude_auto_review.runtime.events import log_event
from claude_auto_review.state.models import EditRecord, ReviewFileRecord, ReviewMetadata, StateEvent
from claude_auto_review.state.reviews.expiry import is_review_expired
from claude_auto_review.state.store.read import ensure_state_snapshot


class PendingReviewCandidate(TypedDict):
    review: ReviewMetadata
    overlap_count: int


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


def entry_file_hash_pairs(entries: Sequence[EditRecord | ReviewFileRecord]) -> set[tuple[str, str]]:
    return {
        (entry.file, entry.hash)
        for entry in entries
        if entry.file and entry.hash
    }


def review_file_hash_pairs(review_entry: ReviewMetadata) -> set[tuple[str, str]]:
    return entry_file_hash_pairs(review_entry.files)


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
        if timeout_hours > 0 and is_review_expired(entry, timeout_hours):
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


def pending_review_candidates_for_entries(
    state: list[StateEvent],
    entries: Sequence[EditRecord | ReviewFileRecord],
    project_root=None,
    timeout_hours=0,
) -> list[PendingReviewCandidate]:
    _, pending_reviews = _pending_reviews_matching_entries(
        state,
        entries,
        project_root=project_root,
        timeout_hours=timeout_hours,
    )
    candidates = [
        PendingReviewCandidate(review=entry, overlap_count=len(overlap))
        for entry, _, overlap in pending_reviews
        if overlap
    ]
    return sorted(candidates, key=lambda candidate: (candidate["overlap_count"], candidate["review"].timestamp), reverse=True)


def pending_reviews_for_entries(
    state: list[StateEvent],
    entries: Sequence[EditRecord | ReviewFileRecord],
) -> list[ReviewMetadata]:
    needed, pending_reviews = _pending_reviews_matching_entries(state, entries)
    return _sorted_by_timestamp_desc([entry for entry, covered, _ in pending_reviews if needed.issubset(covered)])


def pending_reviews_exactly_matching_entries(
    state: list[StateEvent],
    entries: Sequence[EditRecord | ReviewFileRecord],
    project_root=None,
    timeout_hours=0,
) -> list[ReviewMetadata]:
    needed, pending_reviews = _pending_reviews_matching_entries(
        state,
        entries,
        project_root=project_root,
        timeout_hours=timeout_hours,
    )
    return _sorted_by_timestamp_desc([entry for entry, covered, _ in pending_reviews if covered == needed])


def best_pending_review_exactly_matching_entries(
    state: list[StateEvent],
    entries: Sequence[EditRecord | ReviewFileRecord],
    project_root=None,
    timeout_hours=0,
) -> ReviewMetadata | None:
    matches = pending_reviews_exactly_matching_entries(
        state,
        entries,
        project_root=project_root,
        timeout_hours=timeout_hours,
    )
    if not matches:
        return None
    return matches[0]


def best_pending_review_covering_entries(
    state: list[StateEvent],
    entries: Sequence[EditRecord | ReviewFileRecord],
    project_root=None,
    timeout_hours=0,
) -> ReviewMetadata | None:
    candidates = pending_review_candidates_for_entries(
        state,
        entries,
        project_root=project_root,
        timeout_hours=timeout_hours,
    )
    if not candidates:
        return None
    return candidates[0]["review"]


def best_pending_review_for_entries(
    state: list[StateEvent],
    entries: Sequence[EditRecord | ReviewFileRecord],
    project_root=None,
    timeout_hours=0,
) -> ReviewMetadata | None:
    exact = best_pending_review_exactly_matching_entries(
        state,
        entries,
        project_root=project_root,
        timeout_hours=timeout_hours,
    )
    if exact is not None:
        return exact
    return best_pending_review_covering_entries(
        state,
        entries,
        project_root=project_root,
        timeout_hours=timeout_hours,
    )
