from scripts.reviews import is_review_expired
from scripts.state import latest_entries_by_file, log_event


def find_pending_review_for_files(state, unreviewed_entries, project_root, timeout_hours=0):
    """Find the latest pending review that covers at least some unreviewed entries."""
    needed = {(entry["file"], entry["hash"]) for entry in unreviewed_entries}
    matches = []
    for entry in state:
        if not isinstance(entry, dict) or entry.get("type") != "review" or entry.get("status") != "pending":
            continue
        if timeout_hours > 0 and is_review_expired(entry, timeout_hours):
            log_event(
                project_root,
                "stop_review_expired",
                review_id=entry.get("reviewId", ""),
                files=[f.get("file", "") for f in entry.get("files", []) if isinstance(f, dict)],
            )
            continue
        covered = {
            (item.get("file"), item.get("hash"))
            for item in entry.get("files", [])
            if isinstance(item, dict)
        }
        overlap = needed & covered
        if overlap:
            matches.append((entry, len(overlap)))
    if not matches:
        return None
    return max(matches, key=lambda x: (x[1], x[0].get("timestamp", "")))[0]


def get_entries_covered_by_review(review_entry, state_entries):
    review_files = {
        (item["file"], item["hash"])
        for item in review_entry.get("files", [])
        if isinstance(item, dict)
    }
    result = []
    latest_by_file = latest_entries_by_file(state_entries)
    for file_path, entry in latest_by_file.items():
        if (file_path, entry.get("hash")) in review_files:
            result.append(entry)
    return result
