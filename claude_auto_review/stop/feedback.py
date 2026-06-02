from __future__ import annotations

from dataclasses import dataclass

from claude_auto_review.timestamps import local_now_iso
from claude_auto_review.state.records.edit import StopBlockedRecord
from claude_auto_review.stop.feedback_format import build_review_findings_feedback, review_feedback_max_chars
from claude_auto_review.stop.orchestration.types.resolution import FinalizeAction
from claude_auto_review.stop.response import ResponseEmitter


@dataclass(frozen=True)
class FindingsBlockResult:
    system_message: str
    feedback: str
    state_record: StopBlockedRecord


def prepare_findings_block(ctx, review_id, review_path, unreviewed):
    """Build the block response data and state record without performing I/O.

    Returns a FindingsBlockResult containing the response messages and a
    StopBlockedRecord for the caller to persist.
    """
    system_message = f"Claude Auto Review: Review {review_id} found issues to address."
    feedback = build_review_findings_feedback(
        review_id,
        review_path,
        review_feedback_max_chars(ctx.settings),
        project_root=ctx.project_root,
        minimum_blocking_severity=ctx.settings.minimum_blocking_severity,
    )
    record = StopBlockedRecord(
        timestamp=local_now_iso(),
        reason=FinalizeAction.BLOCKED_FINDINGS,
        reviewId=review_id,
        files=[entry.file for entry in unreviewed],
    )
    return FindingsBlockResult(system_message=system_message, feedback=feedback, state_record=record)


def block_completed_review_findings(ctx, review_id, review_path, unreviewed, *, emitter: ResponseEmitter):
    result = prepare_findings_block(ctx, review_id, review_path, unreviewed)
    emitter.block(result.system_message, result.feedback)
    return result

