from claude_auto_review.state.reviews import best_pending_review_covering_entries, review_file_hash_pairs
from claude_auto_review.state.store_read import latest_entries_by_file


def find_pending_review_for_files(state, unreviewed_entries, project_root, timeout_hours=0):
    """Find the newest pending review that covers all unreviewed file hashes."""
    return best_pending_review_covering_entries(state, unreviewed_entries, project_root=project_root, timeout_hours=timeout_hours)


def get_entries_covered_by_review(review_entry, state_entries):
    review_files = review_file_hash_pairs(review_entry)
    result = []
    latest_by_file = latest_entries_by_file(state_entries)
    for file_path, entry in latest_by_file.items():
        if (file_path, entry.get("hash")) in review_files:
            result.append(entry)
    return result
