from __future__ import annotations

from claude_auto_review.state.records.edit import EditRecord
from claude_auto_review.state.records.review import ReviewMetadata
from claude_auto_review.state.reviews.matching import best_pending_review_exactly_matching_entries
from claude_auto_review.state.reviews.matching_hash import review_file_hash_pairs
from claude_auto_review.state.snapshots.snapshot import StateSnapshot


def find_pending_review_for_files(state, unreviewed_entries, project_root, timeout_hours=0):
    """Find the newest pending review whose file/hash set exactly matches the current unreviewed set."""
    return best_pending_review_exactly_matching_entries(
        state,
        unreviewed_entries,
        project_root=project_root,
        timeout_hours=timeout_hours,
    )


def get_entries_covered_by_review(review_entry: ReviewMetadata, state_entries=None, latest_by_file=None):
    review_files = review_file_hash_pairs(review_entry)
    result = []
    if latest_by_file is None:
        latest_by_file = StateSnapshot.from_events(state_entries or []).latest_entries_by_file
    for file_path, entry in latest_by_file.items():
        if isinstance(entry, EditRecord) and (file_path, entry.hash) in review_files:
            result.append(entry)
    return result

