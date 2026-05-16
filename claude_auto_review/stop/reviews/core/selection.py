from claude_auto_review.state.models import EditRecord, ReviewMetadata, StateEvent
from claude_auto_review.state.reviews.matching import best_pending_review_exactly_matching_entries, review_file_hash_pairs
from claude_auto_review.state.store.read import latest_entries_by_file


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
        latest_by_file = latest_entries_by_file(state_entries or [])
    for file_path, entry in latest_by_file.items():
        if isinstance(entry, EditRecord) and (file_path, entry.hash) in review_files:
            result.append(entry)
    return result
