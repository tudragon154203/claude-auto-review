from __future__ import annotations

from pathlib import Path
from typing import Callable, Protocol, Any

from claude_auto_review.config.reviewer.backends import DEFAULT_REVIEWER_MODEL
from claude_auto_review.runtime.events import log_event
from claude_auto_review.stop.orchestration.types.context import RuntimeContext
from claude_auto_review.stop.reviews.types.request import ReviewRequest
from claude_auto_review.stop.reviews.types.result import AutocompleteResult


class ReviewFn(Protocol):
    def __call__(self, request: ReviewRequest, *, log_event_fn: Callable[..., Any]) -> AutocompleteResult: ...


def _get_backend_registry() -> dict[str, ReviewFn]:
    from .claude import _attempt_claude_autocomplete
    from .codex import _attempt_codex_autocomplete
    from .opencode import _attempt_opencode_autocomplete
    return {
        "claude": _attempt_claude_autocomplete,
        "codex": _attempt_codex_autocomplete,
        "opencode": _attempt_opencode_autocomplete,
    }


def attempt_stop_autocomplete(
    ctx: RuntimeContext,
    review_id,
    review_path,
    prompt_file,
    user_prompt,
    reviewer_timeout_seconds=600,
    model=DEFAULT_REVIEWER_MODEL,
    backend="claude",
    *,
    log_event_fn=None,
):
    registry = _get_backend_registry()
    fn = registry.get(backend)
    if fn is None:
        available = ", ".join(sorted(registry)) or "none"
        raise ValueError(f"Unsupported reviewer backend: {backend} (available: {available})")
    request = ReviewRequest(
        ctx=ctx,
        review_id=review_id,
        review_path=review_path,
        prompt_file=prompt_file,
        user_prompt=user_prompt,
        reviewer_timeout_seconds=reviewer_timeout_seconds,
        model=model,
    )
    resolved_log = log_event_fn or log_event
    return fn(request, log_event_fn=resolved_log)
