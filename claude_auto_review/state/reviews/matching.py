from __future__ import annotations

from collections.abc import Sequence

from claude_auto_review.state.models import EditRecord, ReviewFileRecord, ReviewMetadata, StateEvent
from claude_auto_review.state.reviews.matching_engine import _sorted_by_timestamp_desc, _pending_reviews_matching_entries
from claude_auto_review.state.reviews.matching_hash import PendingReviewCandidate


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
    return sorted(
        candidates, key=lambda candidate: (candidate["overlap_count"], candidate["review"].timestamp), reverse=True
    )


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
