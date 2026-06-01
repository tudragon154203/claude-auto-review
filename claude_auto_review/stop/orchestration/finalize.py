"""Finalize a pending review: evaluate, autocomplete, and return stop decision."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from claude_auto_review.state.snapshot import StateSnapshot
from claude_auto_review.stop.orchestration.context import ResponsePayload, RuntimeContext
from claude_auto_review.stop.orchestration.finalize_eval import evaluate_artifact_and_plan
from claude_auto_review.stop.orchestration.finalize_outcomes import (
    plan_for_invalid_settings,
    plan_for_pending_review,
)
from claude_auto_review.stop.orchestration.resolution import FinalizeResult, ReviewResolution
from claude_auto_review.stop.orchestration.response_actions import block_pending_review
from claude_auto_review.stop.reviews.review_prompt_runner import _review_prompt_path
from claude_auto_review.stop.reviews.selection import get_entries_covered_by_review
from claude_auto_review.stop.orchestration.finalize_payloads import _invalid_backend_payload

if TYPE_CHECKING:
    from claude_auto_review.stop.orchestration.deps import EvalDeps


def finalize_review_stop_result(
    ctx: RuntimeContext, resolution: ReviewResolution, *, deps: EvalDeps
) -> tuple[FinalizeResult, ResponsePayload | None]:
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
        deps.log_event_fn(
            ctx.project_root,
            "stop_hook_invalid_reviewer_backend",
            client_id=ctx.client_id,
            error=str(error),
        )
        return plan_for_invalid_settings().result, _invalid_backend_payload(error)

    eval_result = evaluate_artifact_and_plan(
        ctx,
        review_id,
        review_path,
        prompt_file,
        covered_entries,
        unreviewed,
        deps=deps,
    )
    if eval_result is not None:
        return eval_result  # type: ignore[no-any-return]

    block_pending_review(ctx, review_id, review_path, prompt_file, unreviewed, emitter=deps.emitter, state_event_writer=deps.state_event_writer_factory(ctx.project_root, ctx.client_id))
    return plan_for_pending_review().result, None


def finalize_review_stop(ctx: RuntimeContext, resolution: ReviewResolution, *, deps: EvalDeps) -> int:
    result, payload = finalize_review_stop_result(ctx, resolution, deps=deps)
    if payload is not None:
        if payload.feedback is None:
            deps.emitter.approve(payload.system_message)
        else:
            deps.emitter.block(payload.system_message, payload.feedback)
    return result.exit_code
