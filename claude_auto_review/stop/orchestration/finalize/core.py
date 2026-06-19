"""Finalize a pending review: evaluate, autocomplete, and return stop decision."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from claude_auto_review.config.resolvers.reviewer import resolved_reviewer_backend
from claude_auto_review.state.snapshots.snapshot import StateSnapshot
from claude_auto_review.stop.orchestration.types.context import ResponsePayload, RuntimeContext
from claude_auto_review.stop.orchestration.finalize.eval import orchestrate_review_eval
from claude_auto_review.stop.orchestration.finalize.outcomes import (
    plan_for_invalid_settings,
    plan_for_pending_review,
)
from claude_auto_review.stop.orchestration.types.resolution import FinalizeResult, ReviewResolution
from claude_auto_review.stop.orchestration.response_actions import block_pending_review
from claude_auto_review.stop.reviews.prompt.runner import _review_prompt_path
from claude_auto_review.stop.reviews.selection.matching import get_entries_covered_by_review
from claude_auto_review.stop.orchestration.finalize.payloads import _invalid_backend_payload

if TYPE_CHECKING:
    from claude_auto_review.stop.orchestration.deps import ReviewEvalDeps


def _validate_reviewer_backend(ctx: RuntimeContext, *, log_event_fn) -> tuple[FinalizeResult, ResponsePayload] | None:
    try:
        resolved_reviewer_backend(ctx.settings)
        return None
    except ValueError as error:
        log_event_fn(
            ctx.project_root,
            "stop_hook_invalid_reviewer_backend",
            client_id=ctx.client_id,
            error=str(error),
        )
        return plan_for_invalid_settings().result, _invalid_backend_payload(error)


def _run_eval_orchestration(
    ctx: RuntimeContext,
    review_id: str,
    review_path: Path,
    prompt_file: Path,
    covered_entries: list[Any],
    unreviewed: list[Any],
    *,
    deps: ReviewEvalDeps,
) -> tuple[tuple[FinalizeResult, ResponsePayload | None] | None, Any]:
    return orchestrate_review_eval(
        ctx, review_id, review_path, prompt_file, covered_entries, unreviewed, deps=deps
    )


def _prepare_review_data(ctx: RuntimeContext, resolution: ReviewResolution):
    state = resolution.state
    unreviewed = resolution.unreviewed
    review = resolution.review
    state_snapshot = StateSnapshot.from_events(state)
    covered_entries = get_entries_covered_by_review(review, state, latest_by_file=state_snapshot.latest_entries_by_file)
    review_id = review.reviewId
    review_path = Path(ctx.project_root) / review.reviewPath
    prompt_file = _review_prompt_path(ctx, review_id)
    return review_id, review_path, prompt_file, covered_entries, unreviewed


def _block_and_return_pending(ctx, review_id, review_path, prompt_file, unreviewed, *, deps: ReviewEvalDeps, failure_info=None) -> tuple[FinalizeResult, None]:
    writer = deps.executor.state_event_writer_factory(ctx.project_root, ctx.client_id)
    block_pending_review(
        ctx, review_id, review_path, prompt_file, unreviewed,
        emitter=deps.executor.emitter, state_event_writer=writer,
        failure_info=failure_info,
    )
    return plan_for_pending_review().result, None


def finalize_review_stop_result(
    ctx: RuntimeContext, resolution: ReviewResolution, *, deps: ReviewEvalDeps
) -> tuple[FinalizeResult, ResponsePayload | None]:
    review_id, review_path, prompt_file, covered_entries, unreviewed = _prepare_review_data(ctx, resolution)

    invalid = _validate_reviewer_backend(ctx, log_event_fn=deps.autocomplete.log_event_fn)
    if invalid is not None:
        return invalid

    eval_result, autocomplete_result = _run_eval_orchestration(
        ctx, review_id, review_path, prompt_file, covered_entries, unreviewed, deps=deps
    )
    if eval_result is not None:
        return eval_result

    return _block_and_return_pending(
        ctx, review_id, review_path, prompt_file, unreviewed,
        deps=deps, failure_info=autocomplete_result,
    )


def finalize_review_stop(ctx: RuntimeContext, resolution: ReviewResolution, *, deps: ReviewEvalDeps) -> int:
    result, payload = finalize_review_stop_result(ctx, resolution, deps=deps)
    if payload is not None:
        if payload.feedback is None:
            deps.executor.emitter.approve(payload.system_message)
        else:
            deps.executor.emitter.block(payload.system_message, payload.feedback)
    return result.exit_code
