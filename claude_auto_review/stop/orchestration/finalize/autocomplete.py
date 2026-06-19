from __future__ import annotations

from pathlib import Path
from typing import Callable

from claude_auto_review.config.resolvers.reviewer import resolved_reviewer_backend, resolved_reviewer_model
from claude_auto_review.stop.feedback_format import build_review_completion_prompt
from claude_auto_review.stop.orchestration.finalize.retry import RetryPolicy
from claude_auto_review.stop.orchestration.types.context import RuntimeContext
from claude_auto_review.stop.reviews.runners.dispatcher import attempt_stop_autocomplete
from claude_auto_review.stop.reviews.types.enums import AutocompleteStatus
from claude_auto_review.stop.reviews.types.result import AutocompleteResult


DEFAULT_RETRY_POLICY = RetryPolicy()


def attempt_review_autocomplete(
    ctx: RuntimeContext,
    review_id: str,
    review_path: Path,
    prompt_file: Path,
    *,
    log_event_fn: Callable[..., object] | None = None,
    retry_policy: RetryPolicy | None = None,
) -> AutocompleteResult | None:
    policy = retry_policy or DEFAULT_RETRY_POLICY
    user_prompt = build_review_completion_prompt(review_path)
    result: AutocompleteResult | None = None
    for attempt in range(policy.max_attempts):
        result = attempt_stop_autocomplete(
            ctx,
            review_id,
            review_path,
            prompt_file,
            user_prompt,
            reviewer_timeout_seconds=ctx.settings.reviewer.reviewer_timeout_seconds,
            model=resolved_reviewer_model(ctx.settings, backend=resolved_reviewer_backend(ctx.settings)),
            backend=resolved_reviewer_backend(ctx.settings),
            log_event_fn=log_event_fn,
        )
        if not policy.should_retry(AutocompleteStatus(result.status), attempt):
            break
        if log_event_fn:
            log_event_fn(ctx.project_root, "stop_hook_reviewer_retry", client_id=ctx.client_id, reviewId=review_id)
    return result
