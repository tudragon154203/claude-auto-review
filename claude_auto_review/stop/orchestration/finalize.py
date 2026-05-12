from pathlib import Path

from claude_auto_review.paths import local_now_iso
from claude_auto_review.state.reviews import is_review_clean, is_review_complete
from claude_auto_review.review.completion import apply_completed_review
from claude_auto_review.settings import SETTING_CLASSIFIER_ENABLED, SETTING_REVIEWER_TIMEOUT
from claude_auto_review.state.models import StopBlockedRecord
from claude_auto_review.state.store_write import append_state
from claude_auto_review.stop.reviews.autocomplete import attempt_stop_autocomplete
from claude_auto_review.stop.feedback import (
    block_completed_review_findings,
    block_response,
    build_review_completion_prompt,
    build_unreviewed_files_string,
)
from claude_auto_review.stop.classifier.last_assistant_message import classify_last_assistant_message
from claude_auto_review.stop.reviews.selection import get_entries_covered_by_review
from claude_auto_review.stop.reviews.prompt_runner import _review_prompt_path


def _classify_last_assistant_message_if_enabled(project_root, client_id, payload, settings):
    if settings.get(SETTING_CLASSIFIER_ENABLED, False):
        classify_last_assistant_message(project_root, client_id, payload, settings)


def _complete_clean_review(project_root, client_id, review_id, covered_entries):
    remaining = apply_completed_review(project_root, client_id, review_id, covered_entries)
    if not remaining:
        return 0
    block_response(
        f"Claude Auto Review: Review {review_id} completed, but {len(remaining)} file(s) still need review.",
        "New edits were made after the review was created. Another review will be generated on the next stop attempt.",
    )
    return 2


def _block_pending_review(project_root, client_id, review_id, review_path, unreviewed):
    files_str = build_unreviewed_files_string(unreviewed)
    review_path_rel = review_path.relative_to(project_root).as_posix()
    block_response(
        f"Claude Auto Review: Review {review_id} created for {files_str}.",
        (
            f"Review file created at:\n  {review_path_rel}\n\n"
            "Go through each finding in the generated file and set its verdict "
            "(Confirmed, Skipped). Once all findings are resolved, "
            "stopping will be allowed."
        ),
    )
    append_state(
        StopBlockedRecord(
            timestamp=local_now_iso(),
            reason="review_pending",
            files=[entry["file"] for entry in unreviewed],
        ),
        project_root,
        client_id=client_id,
    )
    return 2


def finalize_review_stop(project_root, client_id, resolution, payload, settings):
    state = resolution.state
    unreviewed = resolution.unreviewed
    review = resolution.review
    covered_entries = get_entries_covered_by_review(review, state)
    review_id = review.get("reviewId", "")
    review_path = Path(review.get("reviewPath", ""))
    prompt_file = _review_prompt_path(project_root, client_id, review_id)
    reviewer_timeout_seconds = settings.get(SETTING_REVIEWER_TIMEOUT, 600)

    exit_code = 2
    try:
        if is_review_complete(review_path) and is_review_clean(review_path):
            exit_code = _complete_clean_review(project_root, client_id, review_id, covered_entries)
            return exit_code

        if is_review_complete(review_path):
            block_completed_review_findings(project_root, client_id, review_id, review_path, unreviewed, settings)
            return exit_code

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
            exit_code = 0
            return exit_code

        if is_review_complete(review_path) and not is_review_clean(review_path):
            block_completed_review_findings(project_root, client_id, review_id, review_path, unreviewed, settings)
            return exit_code

        return _block_pending_review(project_root, client_id, review_id, review_path, unreviewed)
    finally:
        if exit_code != 0:
            _classify_last_assistant_message_if_enabled(project_root, client_id, payload, settings)
