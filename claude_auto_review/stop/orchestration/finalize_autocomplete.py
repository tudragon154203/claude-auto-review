from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from claude_auto_review.stop.feedback_format import build_review_completion_prompt
from claude_auto_review.stop.orchestration.context import RuntimeContext
from claude_auto_review.stop.reviews.enums import AutocompleteStatus
from claude_auto_review.stop.reviews.prompt_runner import attempt_stop_autocomplete


def _attempt_review_autocomplete(
    ctx: RuntimeContext,
    review_id: str,
    review_path: Path,
    prompt_file: Path,
    *,
    log_event_fn: Callable[..., Any] | None = None,
) -> Any:
    user_prompt = build_review_completion_prompt(review_path)
    result = None
    for attempt in range(2):
        result = attempt_stop_autocomplete(
            ctx,
            review_id,
            review_path,
            prompt_file,
            user_prompt,
            reviewer_timeout_seconds=ctx.settings.reviewer_timeout_seconds,
            model=ctx.settings.resolved_reviewer_model(backend=ctx.settings.resolved_reviewer_backend()),
            backend=ctx.settings.resolved_reviewer_backend(),
        )
        if result.status != AutocompleteStatus.EMPTY_STDOUT:
            break
        if attempt == 0 and log_event_fn:
            log_event_fn(ctx.project_root, "stop_hook_reviewer_retry", client_id=ctx.client_id, reviewId=review_id)
    return result
