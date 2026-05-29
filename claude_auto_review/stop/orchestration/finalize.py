from __future__ import annotations

from pathlib import Path

from claude_auto_review.runtime.events import log_event
from claude_auto_review.state.snapshot import StateSnapshot
from claude_auto_review.stop.orchestration.context import ResponsePayload, RuntimeContext
from claude_auto_review.stop.orchestration.finalize_outcomes import (
    plan_for_artifact_state,
    plan_for_invalid_settings,
    plan_for_pending_review,
)
from claude_auto_review.stop.orchestration.resolution import FinalizeResult, StopFlowResolution
from claude_auto_review.stop.orchestration.response_actions import block_pending_review
from claude_auto_review.stop.orchestration.review_artifact_evaluator import classify_review_artifact_state
from claude_auto_review.stop.response import approve_response, block_response
from claude_auto_review.stop.reviews.enums import AutocompleteStatus
from claude_auto_review.stop.reviews.review_prompt_runner import _review_prompt_path
from claude_auto_review.stop.reviews.selection import get_entries_covered_by_review
from claude_auto_review.stop.orchestration.finalize_payloads import _invalid_backend_payload
from claude_auto_review.stop.orchestration.finalize_plan_executor import _apply_finalize_plan_result
from claude_auto_review.stop.orchestration.finalize_autocomplete import _attempt_review_autocomplete


def finalize_review_stop_result(
    ctx: RuntimeContext, resolution: StopFlowResolution
) -> tuple[FinalizeResult, ResponsePayload | None]:
    state = resolution.state
    unreviewed = resolution.unreviewed
    review = resolution.review
    if review is None:
        raise ValueError("finalize_review_stop_result called with no review in resolution")
    state_snapshot = StateSnapshot.from_events(state)
    covered_entries = get_entries_covered_by_review(review, state, latest_by_file=state_snapshot.latest_entries_by_file)
    review_id = review.reviewId
    review_path = Path(ctx.project_root) / review.reviewPath
    prompt_file = _review_prompt_path(ctx, review_id)
    try:
        ctx.settings.resolved_reviewer_backend()
    except ValueError as error:
        log_event(
            ctx.project_root,
            "stop_hook_invalid_reviewer_backend",
            client_id=ctx.client_id,
            error=str(error),
        )
        return plan_for_invalid_settings().result, _invalid_backend_payload(error)

    artifact_state = classify_review_artifact_state(
        review_path,
        minimum_blocking_severity=ctx.settings.minimum_blocking_severity,
        client_id=ctx.client_id,
    )
    plan = plan_for_artifact_state(artifact_state)
    if plan is not None:
        return _apply_finalize_plan_result(ctx, plan, review_id, review_path, covered_entries, unreviewed)

    result = _attempt_review_autocomplete(ctx, review_id, review_path, prompt_file)
    artifact_state = classify_review_artifact_state(
        review_path,
        minimum_blocking_severity=ctx.settings.minimum_blocking_severity,
        client_id=ctx.client_id,
    )
    plan = plan_for_artifact_state(artifact_state)
    if plan is not None:
        return _apply_finalize_plan_result(ctx, plan, review_id, review_path, covered_entries, unreviewed)

    if result is not None and result.status == AutocompleteStatus.EMPTY_STDOUT:
        log_event(ctx.project_root, "stop_hook_reviewer_empty_blocked", client_id=ctx.client_id, reviewId=review_id)

    block_pending_review(ctx, review_id, review_path, prompt_file, unreviewed)
    return plan_for_pending_review().result, None


def finalize_review_stop(ctx: RuntimeContext, resolution: StopFlowResolution) -> int:
    result, payload = finalize_review_stop_result(ctx, resolution)
    if payload is not None:
        if payload.feedback is None:
            approve_response(payload.system_message)
        else:
            block_response(payload.system_message, payload.feedback)
    return result.exit_code
