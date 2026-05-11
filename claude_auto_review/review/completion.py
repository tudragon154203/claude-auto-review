from claude_auto_review.paths import local_now_iso
from claude_auto_review.state.store_read import get_unreviewed_files, load_state
from claude_auto_review.state.store_write import append_state, log_event, mark_files_reviewed


def apply_completed_review(project_root, client_id, review_id, covered_entries):
    mark_files_reviewed(covered_entries, review_id, project_root, client_id=client_id)
    log_event(project_root, "stop_approved", reason="review_completed", reviewId=review_id)
    remaining = get_unreviewed_files(load_state(project_root, client_id))
    if remaining:
        log_event(project_root, "stop_blocked_after_partial_review", remaining=[entry["file"] for entry in remaining])
        append_state({"type": "stop_blocked", "reason": "partial_review", "timestamp": local_now_iso()}, project_root, client_id=client_id)
    return remaining
