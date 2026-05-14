from pathlib import Path

from claude_auto_review.state.reviews import (
    extract_review_verdict_text,
    is_review_clean_verdict,
    is_review_complete_verdict,
)
from claude_auto_review.review.completion import apply_completed_review
from claude_auto_review.constants import EXIT_REVIEW_FAILED
from claude_auto_review.settings import DEFAULT_SETTINGS, SETTING_CLASSIFIER_ENABLED, SETTING_REVIEWER_TIMEOUT
from claude_auto_review.stop.orchestration.context import RuntimeContext
from claude_auto_review.stop.feedback import (
    block_completed_review_findings,
    build_review_completion_prompt,
)
from claude_auto_review.stop.classifier.last_assistant_message import classify_last_assistant_message
from claude_auto_review.stop.reviews.selection import get_entries_covered_by_review
from claude_auto_review.stop.reviews.prompt_runner import _review_prompt_path, attempt_stop_autocomplete
from claude_auto_review.stop.orchestration.response_actions import block_pending_review, complete_clean_review


def _read_review_verdict(review_path):
    if not review_path.is_file():
        return None
    return extract_review_verdict_text(review_path.read_text(encoding="utf-8", errors="replace"))


def _classify_last_assistant_message_if_enabled(ctx: RuntimeContext):
    if ctx.settings.get(SETTING_CLASSIFIER_ENABLED, DEFAULT_SETTINGS[SETTING_CLASSIFIER_ENABLED]):
        classify_last_assistant_message(ctx)


def finalize_review_stop(ctx: RuntimeContext, resolution):
    state = resolution.state
    unreviewed = resolution.unreviewed
    review = resolution.review
    covered_entries = get_entries_covered_by_review(review, state)
    review_id = review.reviewId
    review_path = Path(ctx.project_root) / review.reviewPath
    prompt_file = _review_prompt_path(ctx, review_id)
    reviewer_timeout_seconds = ctx.settings.get(SETTING_REVIEWER_TIMEOUT, DEFAULT_SETTINGS[SETTING_REVIEWER_TIMEOUT])
    verdict = _read_review_verdict(review_path)

    exit_code = 2
    try:
        if is_review_complete_verdict(verdict) and is_review_clean_verdict(verdict):
            exit_code = complete_clean_review(
                ctx,
                review_id,
                covered_entries,
                apply_completed_review,
            )
            return exit_code

        if is_review_complete_verdict(verdict):
            block_completed_review_findings(ctx, review_id, review_path, unreviewed)
            return exit_code

        user_prompt = build_review_completion_prompt(review_path)
        if attempt_stop_autocomplete(
            ctx,
            review_id,
            review_path,
            prompt_file,
            covered_entries,
            user_prompt,
            reviewer_timeout_seconds=reviewer_timeout_seconds,
        ):
            exit_code = 0
            return exit_code

        verdict = _read_review_verdict(review_path)
        if is_review_complete_verdict(verdict) and not is_review_clean_verdict(verdict):
            block_completed_review_findings(ctx, review_id, review_path, unreviewed)
            return exit_code

        return block_pending_review(ctx, review_id, review_path, unreviewed)
    finally:
        if exit_code != 0:
            _classify_last_assistant_message_if_enabled(ctx)