from __future__ import annotations

from claude_auto_review.paths.path_utils import local_now_iso
from claude_auto_review.state.models import StopBlockedRecord
from claude_auto_review.state.store.writer import StateEventWriter
from claude_auto_review.stop.feedback_format import build_review_findings_feedback, review_feedback_max_chars
from claude_auto_review.stop.orchestration.resolution import FinalizeAction
from claude_auto_review.stop.response import block_response


def block_completed_review_findings(ctx, review_id, review_path, unreviewed):
    block_response(
        f"Claude Auto Review: Review {review_id} found issues to address.",
        build_review_findings_feedback(
            review_id,
            review_path,
            review_feedback_max_chars(ctx.settings),
            project_root=ctx.project_root,
            minimum_blocking_severity=ctx.settings.minimum_blocking_severity,
        ),
    )
    StateEventWriter(ctx.project_root, ctx.client_id).append(
        StopBlockedRecord(
            timestamp=local_now_iso(),
            reason=FinalizeAction.BLOCKED_FINDINGS,
            reviewId=review_id,
            files=[entry.file for entry in unreviewed],
        )
    )
