from __future__ import annotations

from collections.abc import Sequence
from typing import TypedDict

from claude_auto_review.state.models import EditRecord, ReviewFileRecord, ReviewMetadata


class PendingReviewCandidate(TypedDict):
    review: ReviewMetadata
    overlap_count: int


def entry_file_hash_pairs(entries: Sequence[EditRecord | ReviewFileRecord]) -> set[tuple[str, str]]:
    return {(entry.file, entry.hash) for entry in entries if entry.file and entry.hash}


def review_file_hash_pairs(review_entry: ReviewMetadata) -> set[tuple[str, str]]:
    return entry_file_hash_pairs(review_entry.files)
