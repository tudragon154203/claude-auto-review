from __future__ import annotations

from pathlib import Path
from typing import Any

from claude_auto_review.review.completion import apply_completed_review, record_completed_review
from claude_auto_review.runtime.events import log_event
from claude_auto_review.stop.feedback import block_completed_review_findings
from claude_auto_review.stop.orchestration.context import ResponsePayload, RuntimeContext
from claude_auto_review.stop.orchestration.finalize_outcomes import approved_result, plan_for_partial_review
from claude_auto_review.stop.orchestration.resolution import FinalizeAction, FinalizeResult
from claude_auto_review.stop.orchestration.finalize_payloads import _approve_payload, _partial_review_payload


def _apply_completed_clean_review_result(
    ctx: RuntimeContext, review_id: str, covered_entries: list[Any]
) -> tuple[FinalizeResult, ResponsePayload]:
    remaining = apply_completed_review(ctx.project_root, ctx.client_id, review_id, covered_entries)
    if not remaining:
        log_event(
            ctx.project_root,
            "stop_approved",
            client_id=ctx.client_id,
            reason=FinalizeAction.APPROVED,
            reviewId=review_id,
        )
        return approved_result(), _approve_payload(review_id)
    return plan_for_partial_review().result, _partial_review_payload(review_id, len(remaining))


def _apply_finalize_plan_result(
    ctx: RuntimeContext, plan: Any, review_id: str, review_path: Path, covered_entries: list[Any], unreviewed: list[Any]
) -> tuple[FinalizeResult, ResponsePayload | None]:
    if plan.effect == "apply_completed_clean_review":
        return _apply_completed_clean_review_result(ctx, review_id, covered_entries)
    if plan.effect == "record_findings_block":
        record_completed_review(ctx.project_root, ctx.client_id, review_id, covered_entries)
        block_completed_review_findings(ctx, review_id, review_path, unreviewed)
        return plan.result, None
    raise ValueError(f"Unsupported finalize plan effect: {plan.effect}")
