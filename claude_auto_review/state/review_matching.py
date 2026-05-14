from __future__ import annotations

from typing import Sequence

from claude_auto_review.runtime.helpers import log_event
from claude_auto_review.state.models import EditRecord, ReviewMetadata, StateEvent
from claude_auto_review.state.review_expiry import is_review_expired
from claude_auto_review.state.store_read import latest_review_entries_by_id


def _is_pending_review_entry(entry: StateEvent) -> bool:
    return isinstance(entry, ReviewMetadata) and entry.status == "pending"


def _sorted_by_timestamp_desc(entries: Sequence[ReviewMetadata]) -> list[ReviewMetadata]:
    return sorted(entries, key=lambda entry: entry.timestamp, reverse=True)


def _log_expired_review(project_root, review_entry: ReviewMetadata):
    log_event(
        project_root,
        "stop_review_expired",
        review_id=review_entry.reviewId,
        files=[f.get("file", "") for f in review_entry.files if isinstance(f, dict)],
    )


def entry_file_hash_pairs(entries: Sequence[EditRecord | dict]) -> set[tuple[str, str]]:
    return {
        (entry.file, entry.hash)
        if isinstance(entry, EditRecord)
        else (entry.get("file"), entry.get("hash"))
        for entry in entries
        if (isinstance(entry, EditRecord) and entry.file and entry.hash)
        or (isinstance(entry, dict) and entry.get("file") and entry.get("hash"))
    }


def review_file_hash_pairs(review_entry: ReviewMetadata) -> set[tuple[str, str]]:
    return entry_file_hash_pairs(review_entry.files)


def _pending_review_match_info(state, entries, project_root=None, timeout_hours=0):
    needed = entry_file_hash_pairs(entries)
    if not needed:
        return

    for entry in latest_review_entries_by_id(state).values():
        if not _is_pending_review_entry(entry):
            continue
        if timeout_hours > 0 and is_review_expired(entry, timeout_hours):
            _log_expired_review(project_root, entry)
            continue
        covered = review_file_hash_pairs(entry)
        yield entry, covered, needed & covered


def pending_reviews_for_entries(state, entries):
    matches = []
    needed = entry_file_hash_pairs(entries)
    for entry, covered, _ in _pending_review_match_info(state, entries):
        if needed and needed.issubset(covered):
            matches.append(entry)
    return _sorted_by_timestamp_desc(matches)


def pending_reviews_exactly_matching_entries(state, entries, project_root=None, timeout_hours=0):
    matches = []
    needed = entry_file_hash_pairs(entries)
    if not needed:
        return matches
    for entry, covered, _ in _pending_review_match_info(state, entries, project_root=project_root, timeout_hours=timeout_hours):
        if review_file_hash_pairs(entry) == needed:
            matches.append(entry)
    return _sorted_by_timestamp_desc(matches)


def best_pending_review_exactly_matching_entries(state, entries, project_root=None, timeout_hours=0):
    matches = pending_reviews_exactly_matching_entries(
        state,
        entries,
        project_root=project_root,
        timeout_hours=timeout_hours,
    )
    if not matches:
        return None
    return matches[0]


def best_pending_review_covering_entries(state, entries, project_root=None, timeout_hours=0):
    needed = entry_file_hash_pairs(entries)
    if not needed:
        return None

    matches = []
    for entry, covered, overlap in _pending_review_match_info(state, entries, project_root=project_root, timeout_hours=timeout_hours):
        if needed.issubset(covered):
            matches.append({"review": entry, "overlap_count": len(overlap)})

    if not matches:
        return None
    return sorted(matches, key=lambda item: (item["overlap_count"], item["review"].timestamp), reverse=True)[0]["review"]


def pending_review_candidates_for_entries(state, entries, project_root=None, timeout_hours=0):
    """Return pending reviews that overlap the requested file/hash pairs.

    Matching semantics:
    - a review is eligible if it covers at least one requested file/hash pair
    - expired reviews are skipped
    - higher overlap wins, then newer timestamp wins
    """
    candidates = []
    for entry, _, overlap in _pending_review_match_info(state, entries, project_root=project_root, timeout_hours=timeout_hours):
        if overlap:
            candidates.append({"review": entry, "overlap_count": len(overlap)})
    return sorted(candidates, key=lambda item: (item["overlap_count"], item["review"].timestamp), reverse=True)


def best_pending_review_for_entries(state, entries, project_root=None, timeout_hours=0):
    candidates = pending_review_candidates_for_entries(state, entries, project_root=project_root, timeout_hours=timeout_hours)
    if not candidates:
        return None
    return candidates[0]["review"]
