from __future__ import annotations

from typing import Any, Callable

from claude_auto_review.config.constants import EXIT_REVIEW_FAILED
from claude_auto_review.paths.path_utils import local_now_iso
from claude_auto_review.state.edit_record import StopBlockedRecord
from claude_auto_review.stop.feedback_format import build_unreviewed_files_string
from claude_auto_review.stop.orchestration.context import RuntimeContext
from claude_auto_review.stop.orchestration.protocols import StateEventWriterProtocol
from claude_auto_review.stop.orchestration.resolution import StopFlowResolution, TerminalResolution
from claude_auto_review.stop.response import ResponseEmitter


def _display_path(path, project_root):
    try:
        return path.relative_to(project_root).as_posix()
    except ValueError:
        return str(path)


def fail_review(
    ctx: RuntimeContext,
    files_str: str,
    exit_code: int,
    event_type: str,
    *,
    emitter: ResponseEmitter,
    log_event_fn: Callable[..., Any] | None = None,
    script: str | None = None,
    error: Exception | None = None,
) -> StopFlowResolution:
    """Emit failure response and return a terminal resolution."""
    if log_event_fn:
        log_event_fn(
            ctx.project_root,
            event_type,
            client_id=ctx.client_id,
            script=str(script) if script else None,
            error=str(error) if error else None,
        )
    if exit_code == EXIT_REVIEW_FAILED:
        if error:
            emitter.block(
                f"Claude Auto Review: Error generating review for {files_str}.",
                f"Failed to run review_prompt.py: {error}",
            )
        else:
            emitter.block(
                f"Claude Auto Review: Timeout generating review for {files_str}.",
                "The review generation timed out. Check the logs and try again.",
            )
    return TerminalResolution(exit_code=exit_code)


def approve_no_unreviewed_after_review(ctx: RuntimeContext, *, emitter: ResponseEmitter, log_event_fn: Callable[..., Any] | None = None) -> None:
    """Emit approval when no unreviewed files remain after a review completes."""
    if log_event_fn:
        log_event_fn(
            ctx.project_root,
            "stop_approved",
            client_id=ctx.client_id,
            reason="no_unreviewed_files_after_review",
        )
    emitter.approve("Claude Auto Review: stop approved (no_unreviewed_files_after_review)")


def block_pending_review(ctx: RuntimeContext, review_id, review_path, prompt_path, unreviewed, *, emitter: ResponseEmitter, state_event_writer: StateEventWriterProtocol):
    files_str = build_unreviewed_files_string(unreviewed)
    review_path_rel = _display_path(review_path, ctx.project_root)
    prompt_path_rel = _display_path(prompt_path, ctx.project_root)
    emitter.block(
        f"Claude Auto Review: Review {review_id} created for {files_str}.",
        (
            f"Review file created at:\n  {review_path_rel}\n\n"
            "This file is only a placeholder until the review is completed.\n\n"
            f"Complete the review from:\n  {prompt_path_rel}\n\n"
            "Then write the findings into the review file and set each finding verdict "
            "(Confirmed, Skipped). Once the review verdict is no longer Pending, "
            "stopping will be allowed."
        ),
    )
    state_event_writer.append(
        StopBlockedRecord(
            timestamp=local_now_iso(),
            reason="review_pending",
            files=[entry.file for entry in unreviewed],
        )
    )
    return 2

