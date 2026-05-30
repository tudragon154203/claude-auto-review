from __future__ import annotations

from claude_auto_review.stop.feedback_format import build_unreviewed_files_string
from claude_auto_review.stop.orchestration.context import RuntimeContext
from claude_auto_review.stop.orchestration.review_executor import execute_review_prompt
from claude_auto_review.stop.orchestration.resolution import ReviewResolution
from claude_auto_review.stop.reviews.selection import find_pending_review_for_files


def resolve_pending_review(ctx: RuntimeContext, state, unreviewed, timeout_hours, review_prompt_script):
    review = find_pending_review_for_files(state, unreviewed, ctx.project_root, timeout_hours)
    if review:
        return ReviewResolution(review=review, state=state, unreviewed=unreviewed)

    files_str = build_unreviewed_files_string(unreviewed)
    return execute_review_prompt(ctx, unreviewed, timeout_hours, review_prompt_script, files_str)
