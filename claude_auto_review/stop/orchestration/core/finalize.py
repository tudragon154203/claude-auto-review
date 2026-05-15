from pathlib import Path

from claude_auto_review.state.reviews import (
    extract_review_verdict_text,
    is_completed_review_content,
    is_review_clean,
    is_review_complete_verdict,
    normalize_review_verdict_content,
)
from claude_auto_review.review.completion import apply_completed_review
from claude_auto_review.config.constants import EXIT_REVIEW_FAILED
from claude_auto_review.config.settings import DEFAULT_SETTINGS, SETTING_REVIEWER_TIMEOUT
from claude_auto_review.stop.orchestration.core.context import RuntimeContext
from claude_auto_review.stop.feedback import (
    block_completed_review_findings,
    build_review_completion_prompt,
    block_response,
)
from claude_auto_review.stop.reviews.core.selection import get_entries_covered_by_review
from claude_auto_review.stop.reviews.core.prompt_runner import _review_prompt_path, attempt_stop_autocomplete
from claude_auto_review.stop.orchestration.core.response_actions import block_pending_review


def _read_review_verdict(review_path):
    if not review_path.is_file():
        return None
    content = review_path.read_text(encoding="utf-8", errors="replace")
    normalized = normalize_review_verdict_content(content)
    if normalized != content:
        review_path.write_text(normalized, encoding="utf-8", newline="\n")
        content = normalized
    return extract_review_verdict_text(content)


def _review_has_completed_artifact(review_path):
    if not review_path.is_file():
        return False
    return is_completed_review_content(review_path.read_text(encoding="utf-8", errors="replace"))


def _block_partial_review_remaining(review_id, remaining):
    block_response(
        f"Claude Auto Review: Review {review_id} completed, but {len(remaining)} file(s) still need review.",
        "New edits were made after the review was created. Another review will be generated on the next stop attempt.",
    )


def _apply_completed_clean_review(ctx, review_id, covered_entries):
    remaining = apply_completed_review(
        ctx.project_root,
        ctx.client_id,
        review_id,
        covered_entries,
    )
    if not remaining:
        return 0
    _block_partial_review_remaining(review_id, remaining)
    return 2


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

    if is_review_complete_verdict(verdict) and is_review_clean(review_path):
        return _apply_completed_clean_review(ctx, review_id, covered_entries)

    if is_review_complete_verdict(verdict):
        block_completed_review_findings(ctx, review_id, review_path, unreviewed)
        return 2

    if _review_has_completed_artifact(review_path):
        block_completed_review_findings(ctx, review_id, review_path, unreviewed)
        return 2

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
        return 0

    verdict = _read_review_verdict(review_path)
    if is_review_complete_verdict(verdict) and not is_review_clean(review_path):
        block_completed_review_findings(ctx, review_id, review_path, unreviewed)
        return 2

    if is_review_complete_verdict(verdict) and is_review_clean(review_path):
        return _apply_completed_clean_review(ctx, review_id, covered_entries)

    if _review_has_completed_artifact(review_path):
        block_completed_review_findings(ctx, review_id, review_path, unreviewed)
        return 2

    return block_pending_review(ctx, review_id, review_path, prompt_file, unreviewed)
