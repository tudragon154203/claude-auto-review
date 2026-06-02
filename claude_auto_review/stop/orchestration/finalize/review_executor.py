"""Execute a review prompt and resolve the resulting review state.

Response I/O (block/approve responses) is delegated to :mod:`response_actions`.
"""

from __future__ import annotations

import subprocess
from typing import Any, Callable

from claude_auto_review.config.constants.exit_codes import EXIT_REVIEW_FAILED
from claude_auto_review.stop.reviews.prompt.runner import (
    build_review_prompt_env,
    _block_review_prompt_failure,
    _reload_client_state,
    run_review_prompt,
)
from claude_auto_review.stop.orchestration.types.context import RuntimeContext
from claude_auto_review.stop.orchestration.types.resolution import StopFlowResolution, TerminalResolution, ReviewResolution
from claude_auto_review.stop.orchestration.response_actions import (
    approve_no_unreviewed_after_review,
    fail_review,
)
from claude_auto_review.state.reviews.matching import best_pending_review_exactly_matching_entries
from claude_auto_review.stop.response import ResponseEmitter


def resolve_prompted_review(
    ctx: RuntimeContext, timeout_hours: float, files_str: str, result: Any, *, emitter: ResponseEmitter, log_event_fn: Callable[..., Any] | None = None
) -> StopFlowResolution:
    """Reload state after prompt execution and determine the resolution."""
    state, unreviewed = _reload_client_state(ctx)
    if not unreviewed:
        approve_no_unreviewed_after_review(ctx, emitter=emitter, log_event_fn=log_event_fn)
        return TerminalResolution(exit_code=0)

    review = best_pending_review_exactly_matching_entries(state, unreviewed, ctx.project_root, timeout_hours)
    if not review:
        _block_review_prompt_failure(files_str, result, emitter=emitter)
        return TerminalResolution(exit_code=EXIT_REVIEW_FAILED)

    return ReviewResolution(review=review, state=state, unreviewed=unreviewed)


def execute_review_prompt(
    ctx: RuntimeContext, unreviewed: list[Any], timeout_hours: float, review_prompt_script: str, files_str: str, *, emitter: ResponseEmitter, log_event_fn: Callable[..., Any] | None = None
) -> StopFlowResolution:
    """Run the review prompt script and resolve the resulting review."""
    env = build_review_prompt_env(ctx.payload)
    try:
        result = run_review_prompt(ctx, review_prompt_script, env)
    except subprocess.TimeoutExpired:
        return fail_review(ctx, files_str, EXIT_REVIEW_FAILED, "stop_hook_review_timeout", script=review_prompt_script, emitter=emitter, log_event_fn=log_event_fn)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        return fail_review(ctx, files_str, EXIT_REVIEW_FAILED, "stop_hook_review_error", error=error, emitter=emitter, log_event_fn=log_event_fn)
    return resolve_prompted_review(ctx, timeout_hours, files_str, result, emitter=emitter, log_event_fn=log_event_fn)
