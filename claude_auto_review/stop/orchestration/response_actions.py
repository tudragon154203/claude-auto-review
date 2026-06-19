from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from claude_auto_review.config.constants.exit_codes import EXIT_REVIEW_FAILED
from claude_auto_review.timestamps import local_now_iso
from claude_auto_review.state.records.edit import StopBlockedRecord
from claude_auto_review.stop.feedback_format import build_unreviewed_files_string
from claude_auto_review.stop.orchestration.types.context import RuntimeContext
from claude_auto_review.stop.orchestration.types.protocols import StateEventWriterProtocol
from claude_auto_review.stop.orchestration.types.resolution import StopFlowResolution, TerminalResolution
from claude_auto_review.stop.response import ResponseEmitter
from claude_auto_review.stop.reviews.types.enums import AutocompleteStatus


_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_STDERR_PREVIEW_LIMIT = 400


def _strip_ansi(text: str) -> str:
    return _ANSI_ESCAPE_RE.sub("", text)


def _truncate(text: str, limit: int = _STDERR_PREVIEW_LIMIT) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."


def _format_failure_hint(failure_info) -> str:
    """Return a one-paragraph hint describing why the auto-reviewer backend failed.

    Returns an empty string when there is no failure to report (no info, or the
    autocomplete produced output successfully).
    """
    if failure_info is None:
        return ""
    status = failure_info.status
    if status == AutocompleteStatus.OUTPUT_WRITTEN:
        return ""
    if status == AutocompleteStatus.CLI_NOT_FOUND:
        return "reviewer backend CLI was not found on PATH"
    if status == AutocompleteStatus.TIMEOUT:
        return "reviewer subprocess timed out (check `reviewerTimeoutSeconds`)"
    stderr = _truncate(_strip_ansi(failure_info.stderr or ""))
    if status == AutocompleteStatus.EMPTY_STDOUT:
        base = "reviewer backend produced no output"
        return f"{base}: {stderr}" if stderr else base
    if status == AutocompleteStatus.NONZERO:
        base = f"reviewer backend exited with code {failure_info.returncode}"
        return f"{base}: {stderr}" if stderr else base
    if status == AutocompleteStatus.ERROR:
        base = "reviewer backend raised an error"
        return f"{base}: {stderr}" if stderr else base
    if status == AutocompleteStatus.PROMPT_NOT_FOUND:
        return "review prompt file was missing"
    return ""


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


@dataclass(frozen=True)
class PendingReviewBlockResult:
    system_message: str
    feedback: str
    state_record: StopBlockedRecord


def prepare_pending_review_block(
    ctx: RuntimeContext,
    review_id: str,
    review_path: Path,
    prompt_path: Path,
    unreviewed: list[Any],
    *,
    failure_info=None,
) -> PendingReviewBlockResult:
    """Prepare messages and state record for a pending review block without I/O."""
    files_str = build_unreviewed_files_string(unreviewed)
    review_path_rel = _display_path(review_path, ctx.project_root)
    prompt_path_rel = _display_path(prompt_path, ctx.project_root)
    system_message = f"Claude Auto Review: Review {review_id} created for {files_str}."
    hint = _format_failure_hint(failure_info)
    hint_paragraph = f"\nThe auto-reviewer backend could not complete the review: {hint}\n" if hint else ""
    feedback = (
        f"Review file created at:\n  {review_path_rel}\n\n"
        "This file is only a placeholder until the review is completed.\n"
        f"{hint_paragraph}\n"
        f"Complete the review from:\n  {prompt_path_rel}\n\n"
        "Then write the findings into the review file and set each finding verdict "
        "(Confirmed, Skipped). Once the review verdict is no longer Pending, "
        "stopping will be allowed."
    )
    record = StopBlockedRecord(
        timestamp=local_now_iso(),
        reason="review_pending",
        files=[entry.file for entry in unreviewed],
    )
    return PendingReviewBlockResult(system_message=system_message, feedback=feedback, state_record=record)


def block_pending_review(ctx: RuntimeContext, review_id, review_path, prompt_path, unreviewed, *, emitter: ResponseEmitter, state_event_writer: StateEventWriterProtocol, failure_info=None):
    result = prepare_pending_review_block(ctx, review_id, review_path, prompt_path, unreviewed, failure_info=failure_info)
    emitter.block(result.system_message, result.feedback)
    state_event_writer.append(result.state_record)
    return 2

