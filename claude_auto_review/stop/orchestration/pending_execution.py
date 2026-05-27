import subprocess

from claude_auto_review.review.lifecycle import build_review_prompt_env
from claude_auto_review.config.constants import EXIT_REVIEW_FAILED
from claude_auto_review.runtime.events import log_event
from claude_auto_review.stop.feedback import block_response
from claude_auto_review.stop.orchestration.resolution import StopFlowResolution
from claude_auto_review.stop.reviews.review_prompt_runner import (
    _block_review_prompt_failure,
    _reload_client_state,
    run_review_prompt,
)
from claude_auto_review.stop.reviews.selection import find_pending_review_for_files
from claude_auto_review.stop.response import approve_response


def fail_review(ctx, files_str, exit_code, event_type, script=None, error=None):
    log_event(ctx.project_root, event_type, client_id=ctx.client_id, script=str(script) if script else None, error=str(error) if error else None)
    if exit_code == EXIT_REVIEW_FAILED:
        if error:
            block_response(
                f"Claude Auto Review: Error generating review for {files_str}.",
                f"Failed to run review_prompt.py: {error}",
            )
        else:
            block_response(
                f"Claude Auto Review: Timeout generating review for {files_str}.",
                "The review generation timed out. Check the logs and try again.",
            )
    return StopFlowResolution(state=[], unreviewed=[], exit_code=exit_code)


def resolve_prompted_review(ctx, timeout_hours, files_str, result):
    state, unreviewed = _reload_client_state(ctx)
    if not unreviewed:
        log_event(ctx.project_root, "stop_approved", client_id=ctx.client_id, reason="no_unreviewed_files_after_review")
        approve_response("Claude Auto Review: stop approved (no_unreviewed_files_after_review)")
        return StopFlowResolution(state=state, unreviewed=unreviewed, exit_code=0)

    review = find_pending_review_for_files(state, unreviewed, ctx.project_root, timeout_hours)
    if not review:
        _block_review_prompt_failure(files_str, result)
        return StopFlowResolution(state=state, unreviewed=unreviewed, exit_code=EXIT_REVIEW_FAILED)

    return StopFlowResolution(state=state, unreviewed=unreviewed, review=review)


def execute_review_prompt(ctx, unreviewed, timeout_hours, review_prompt_script, files_str):
    env = build_review_prompt_env(ctx.payload)
    try:
        result = run_review_prompt(ctx, review_prompt_script, env)
    except subprocess.TimeoutExpired:
        return fail_review(ctx, files_str, EXIT_REVIEW_FAILED, "stop_hook_review_timeout", script=review_prompt_script)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        return fail_review(ctx, files_str, EXIT_REVIEW_FAILED, "stop_hook_review_error", error=error)
    return resolve_prompted_review(ctx, timeout_hours, files_str, result)
