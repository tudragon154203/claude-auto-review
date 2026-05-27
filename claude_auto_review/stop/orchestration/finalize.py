from __future__ import annotations

from pathlib import Path

from claude_auto_review.review.completion import apply_completed_review, record_completed_review
from claude_auto_review.review.lifecycle import ReviewLifecycleService
from claude_auto_review.runtime.events import log_event
from claude_auto_review.state.snapshot import StateSnapshot
from claude_auto_review.stop.feedback import block_completed_review_findings, build_review_completion_prompt
from claude_auto_review.stop.orchestration.context import ResponsePayload, RuntimeContext
from claude_auto_review.stop.orchestration.finalize_outcomes import (
    approved_result,
    plan_for_artifact_state,
    plan_for_invalid_settings,
    plan_for_partial_review,
    plan_for_pending_review,
)
from claude_auto_review.stop.orchestration.resolution import FinalizeResult, StopFlowResolution
from claude_auto_review.stop.orchestration.review_artifact_evaluator import classify_review_artifact_state
from claude_auto_review.stop.orchestration.response_actions import block_pending_review
from claude_auto_review.stop.response import approve_response, block_response
from claude_auto_review.stop.reviews.prompt_runner import attempt_stop_autocomplete
from claude_auto_review.stop.reviews.review_prompt_runner import _review_prompt_path
from claude_auto_review.stop.reviews.selection import get_entries_covered_by_review


def _approve_payload(review_id: str) -> ResponsePayload:
    return ResponsePayload(
        system_message=f"Claude Auto Review: review {review_id} clean, all files covered"
    )


def _partial_review_payload(review_id: str, remaining_count: int) -> ResponsePayload:
    return ResponsePayload(
        system_message=(
            f"Claude Auto Review: Review {review_id} completed, but {remaining_count} file(s) still need review."
        ),
        feedback=(
            "New edits were made after the review was created. "
            "Another review will be generated on the next stop attempt."
        ),
    )


def _invalid_backend_payload(error: Exception) -> ResponsePayload:
    return ResponsePayload(
        system_message="Claude Auto Review: invalid reviewerBackend setting",
        feedback=str(error),
    )


def _apply_completed_clean_review_result(ctx: RuntimeContext, review_id: str, covered_entries: list[Any]) -> tuple[FinalizeResult, ResponsePayload]:
    remaining = apply_completed_review(ctx.project_root, ctx.client_id, review_id, covered_entries)
    if not remaining:
        log_event(
            ctx.project_root,
            "stop_approved",
            client_id=ctx.client_id,
            reason="review_clean",
            reviewId=review_id,
        )
        return approved_result(), _approve_payload(review_id)
    return plan_for_partial_review().result, _partial_review_payload(review_id, len(remaining))


def _apply_finalize_plan_result(ctx: RuntimeContext, plan: Any, review_id: str, review_path: Path, covered_entries: list[Any], unreviewed: list[Any]) -> tuple[FinalizeResult, ResponsePayload | None]:
    if plan.effect == "apply_completed_clean_review":
        return _apply_completed_clean_review_result(ctx, review_id, covered_entries)
    if plan.effect == "record_findings_block":
        record_completed_review(ctx.project_root, ctx.client_id, review_id, covered_entries)
        block_completed_review_findings(ctx, review_id, review_path, unreviewed)
        return plan.result, None
    raise ValueError(f"Unsupported finalize plan effect: {plan.effect}")


def _attempt_review_autocomplete(ctx: RuntimeContext, review_id: str, review_path: Path, prompt_file: Path) -> Any:
    lifecycle = ReviewLifecycleService(ctx)
    user_prompt = build_review_completion_prompt(review_path)
    result = None
    for attempt in range(2):
        result = attempt_stop_autocomplete(
            ctx,
            review_id,
            review_path,
            prompt_file,
            user_prompt,
            reviewer_timeout_seconds=ctx.settings.reviewer_timeout_seconds,
            model=ctx.settings.resolved_reviewer_model(backend=ctx.settings.resolved_reviewer_backend()),
            backend=ctx.settings.resolved_reviewer_backend(),
        )
        if result.status != "empty_stdout":
            break
        if attempt == 0:
            log_event(ctx.project_root, "stop_hook_reviewer_retry", client_id=ctx.client_id, reviewId=review_id)
    return result


def finalize_review_stop_result(ctx: RuntimeContext, resolution: StopFlowResolution) -> tuple[FinalizeResult, ResponsePayload | None]:
    state = resolution.state
    unreviewed = resolution.unreviewed
    review = resolution.review
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

    if result is not None and result.status == "empty_stdout":
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
