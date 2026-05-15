import os
import subprocess

from claude_auto_review.config.core.constants import EXIT_REVIEW_FAILED
from claude_auto_review.runtime.core.events import log_event
from claude_auto_review.stop.feedback import build_unreviewed_files_string, block_response
from claude_auto_review.stop.orchestration.core.context import RuntimeContext
from claude_auto_review.stop.orchestration.core.resolution import StopFlowResolution
from claude_auto_review.stop.reviews.core.selection import find_pending_review_for_files
from claude_auto_review.stop.reviews.core.prompt_runner import (
    _block_review_prompt_failure,
    _reload_client_state,
    _run_review_prompt,
)


def _build_review_prompt_env(payload):
    env = os.environ.copy()
    session_id = payload.get("session_id")
    if session_id:
        env["CLAUDE_SESSION_ID"] = session_id
    return env


def _resolve_prompted_review(ctx, timeout_hours, files_str, result):
    state, unreviewed = _reload_client_state(ctx)
    if not unreviewed:
        log_event(ctx.project_root, "stop_approved", reason="no_unreviewed_files_after_review")
        return StopFlowResolution(state=state, unreviewed=unreviewed, exit_code=0)

    review = find_pending_review_for_files(state, unreviewed, ctx.project_root, timeout_hours)
    if not review:
        _block_review_prompt_failure(files_str, result)
        return StopFlowResolution(state=state, unreviewed=unreviewed, exit_code=EXIT_REVIEW_FAILED)

    return StopFlowResolution(state=state, unreviewed=unreviewed, review=review)


def resolve_pending_review(ctx: RuntimeContext, state, unreviewed, timeout_hours, review_prompt_script):
    review = find_pending_review_for_files(state, unreviewed, ctx.project_root, timeout_hours)
    if review:
        return StopFlowResolution(state=state, unreviewed=unreviewed, review=review)

    files_str = build_unreviewed_files_string(unreviewed)
    env = _build_review_prompt_env(ctx.payload)

    try:
        result = _run_review_prompt(ctx, review_prompt_script, env)
    except subprocess.TimeoutExpired:
        log_event(ctx.project_root, "stop_hook_review_timeout", script=str(review_prompt_script))
        block_response(
            f"Claude Auto Review: Timeout generating review for {files_str}.",
            "The review generation timed out. Check the logs and try again.",
        )
        return StopFlowResolution(state=state, unreviewed=unreviewed, exit_code=EXIT_REVIEW_FAILED)
    except (OSError, ValueError, subprocess.SubprocessError) as e:
        log_event(ctx.project_root, "stop_hook_review_error", error=str(e))
        block_response(
            f"Claude Auto Review: Error generating review for {files_str}.",
            f"Failed to run review_prompt.py: {e}",
        )
        return StopFlowResolution(state=state, unreviewed=unreviewed, exit_code=EXIT_REVIEW_FAILED)

    return _resolve_prompted_review(ctx, timeout_hours, files_str, result)
