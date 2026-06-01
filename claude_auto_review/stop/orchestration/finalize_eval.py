"""Evaluate review artifact state and determine the finalize plan."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from claude_auto_review.stop.orchestration.context import RuntimeContext
from claude_auto_review.stop.reviews.enums import AutocompleteStatus

if TYPE_CHECKING:
    from claude_auto_review.stop.orchestration.deps import EvalDeps


def evaluate_artifact_and_plan(
    ctx: RuntimeContext,
    review_id: str,
    review_path: Path,
    prompt_file: Path,
    covered_entries: list,
    unreviewed: list,
    *,
    deps: EvalDeps,
):
    """Classify artifact state, attempt autocomplete if needed, and apply a finalize plan.

    Returns (result, payload) if a plan was determined, or None if the review
    is still pending after autocomplete.
    """
    writer = deps.state_event_writer_factory(ctx.project_root, ctx.client_id)

    artifact_state = deps.classify_fn(
        review_path,
        minimum_blocking_severity=ctx.settings.minimum_blocking_severity,
        client_id=ctx.client_id,
    )
    plan = deps.plan_for_artifact_state_fn(artifact_state)
    if plan is not None:
        return deps.apply_plan_fn(ctx, plan, review_id, review_path, covered_entries, unreviewed, state_event_writer=writer, emitter=deps.emitter)

    autocomplete_result = deps.attempt_autocomplete_fn(ctx, review_id, review_path, prompt_file, log_event_fn=deps.log_event_fn)

    artifact_state = deps.classify_fn(
        review_path,
        minimum_blocking_severity=ctx.settings.minimum_blocking_severity,
        client_id=ctx.client_id,
    )
    plan = deps.plan_for_artifact_state_fn(artifact_state)
    if plan is not None:
        return deps.apply_plan_fn(ctx, plan, review_id, review_path, covered_entries, unreviewed, state_event_writer=writer, emitter=deps.emitter)

    if autocomplete_result is not None and autocomplete_result.status == AutocompleteStatus.EMPTY_STDOUT:
        deps.log_event_fn(
            ctx.project_root,
            "stop_hook_reviewer_empty_blocked",
            client_id=ctx.client_id,
            reviewId=review_id,
        )

    return None
