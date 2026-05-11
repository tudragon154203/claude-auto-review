from pathlib import Path

from claude_auto_review.paths import local_now_iso
from claude_auto_review.state.reviews import is_review_clean, is_review_complete
from claude_auto_review.review.completion import apply_completed_review
from claude_auto_review.state.store_write import append_state, log_event
from claude_auto_review.stop.autocomplete import attempt_stop_autocomplete
from claude_auto_review.stop.feedback import (
    block_completed_review_findings,
    block_response,
    build_review_completion_prompt,
    build_unreviewed_files_string,
)
from claude_auto_review.stop.last_assistant_message import classify_last_assistant_message
from claude_auto_review.stop.selection import get_entries_covered_by_review
from claude_auto_review.stop.review_prompt_runner import _review_prompt_path


def _classify_last_assistant_message_if_enabled(project_root, client_id, payload, settings):
    if settings.get("lastAssistantMessageClassifierEnabled", False):
        classify_last_assistant_message(project_root, client_id, payload, settings)


def finalize_review_stop(project_root, client_id, resolution, payload, settings):
    state = resolution.state
    unreviewed = resolution.unreviewed
    review = resolution.review
    covered_entries = get_entries_covered_by_review(review, state)
    review_id = review.get("reviewId", "")
    review_path = Path(review.get("reviewPath", ""))
    prompt_file = _review_prompt_path(project_root, client_id, review_id)
    reviewer_timeout_seconds = settings.get("reviewerTimeoutSeconds", 600)

    if is_review_complete(review_path) and is_review_clean(review_path):
        remaining = apply_completed_review(project_root, client_id, review_id, covered_entries)
        if not remaining:
            return 0
        _classify_last_assistant_message_if_enabled(project_root, client_id, payload, settings)
        block_response(
            f"Claude Auto Review: Review {review_id} completed, but {len(remaining)} file(s) still need review.",
            "New edits were made after the review was created. Another review will be generated on the next stop attempt.",
        )
        return 2

    if is_review_complete(review_path):
        _classify_last_assistant_message_if_enabled(project_root, client_id, payload, settings)
        block_completed_review_findings(project_root, client_id, review_id, review_path, unreviewed, settings)
        return 2

    user_prompt = build_review_completion_prompt(review_path)
    if attempt_stop_autocomplete(
        project_root,
        client_id,
        review_id,
        review_path,
        prompt_file,
        covered_entries,
        user_prompt,
        reviewer_timeout_seconds=reviewer_timeout_seconds,
    ):
        return 0

    if is_review_complete(review_path) and not is_review_clean(review_path):
        _classify_last_assistant_message_if_enabled(project_root, client_id, payload, settings)
        block_completed_review_findings(project_root, client_id, review_id, review_path, unreviewed, settings)
        return 2

    _classify_last_assistant_message_if_enabled(project_root, client_id, payload, settings)
    files_str = build_unreviewed_files_string(unreviewed)
    block_response(
        f"Claude Auto Review: Review {review_id} created for {files_str}.",
        (
            f"Review file created at:\n  {review_path}\n\n"
            "Go through each finding in the generated file and set its verdict "
            "(Confirmed, Skipped). Once all findings are resolved, "
            "stopping will be allowed."
        ),
    )
    log_event(project_root, "stop_blocked", files=[entry["file"] for entry in unreviewed])
    append_state(
        {"type": "stop_blocked", "reason": "review_pending", "timestamp": local_now_iso()},
        project_root,
        client_id=client_id,
    )
    return 2
