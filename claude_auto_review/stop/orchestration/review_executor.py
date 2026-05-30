"""Execute a review prompt and resolve the resulting review state.

Response I/O (block/approve responses) is delegated to :mod:`response_actions`.
"""

from __future__ import annotations

import subprocess
from typing import Any

from claude_auto_review.config.constants import EXIT_REVIEW_FAILED
from claude_auto_review.stop.reviews.review_prompt_runner import (
    build_review_prompt_env,
    _block_review_prompt_failure,
    _reload_client_state,
    run_review_prompt,
)
from claude_auto_review.stop.orchestration.context import RuntimeContext
from claude_auto_review.stop.orchestration.resolution import StopFlowResolution, TerminalResolution, ReviewResolution
from claude_auto_review.stop.orchestration.response_actions import (
    approve_no_unreviewed_after_review,
    fail_review,
)
from claude_auto_review.stop.reviews.selection import find_pending_review_for_files


def resolve_prompted_review(
    ctx: RuntimeContext, timeout_hours: float, files_str: str, result: Any
) -> StopFlowResolution:
    """Reload state after prompt execution and determine the resolution."""
    state, unreviewed = _reload_client_state(ctx)
    if not unreviewed:
        approve_no_unreviewed_after_review(ctx)
        return TerminalResolution(exit_code=0)

    review = find_pending_review_for_files(state, unreviewed, ctx.project_root, timeout_hours)
    if not review:
        _block_review_prompt_failure(files_str, result)
        return TerminalResolution(exit_code=EXIT_REVIEW_FAILED)

    return ReviewResolution(review=review, state=state, unreviewed=unreviewed)


def execute_review_prompt(
    ctx: RuntimeContext, unreviewed: list[Any], timeout_hours: float, review_prompt_script: str, files_str: str
) -> StopFlowResolution:
    """Run the review prompt script and resolve the resulting review."""
    env = build_review_prompt_env(ctx.payload)
    try:
        result = run_review_prompt(ctx, review_prompt_script, env)
    except subprocess.TimeoutExpired:
        return fail_review(ctx, files_str, EXIT_REVIEW_FAILED, "stop_hook_review_timeout", script=review_prompt_script)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        return fail_review(ctx, files_str, EXIT_REVIEW_FAILED, "stop_hook_review_error", error=error)
    return resolve_prompted_review(ctx, timeout_hours, files_str, result)
