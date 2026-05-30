"""Evaluate review artifact state and determine the finalize plan."""

from __future__ import annotations

from pathlib import Path

from claude_auto_review.runtime.events import log_event
from claude_auto_review.stop.orchestration.context import RuntimeContext
from claude_auto_review.stop.orchestration.finalize_outcomes import plan_for_artifact_state
from claude_auto_review.stop.orchestration.finalize_plan_executor import _apply_finalize_plan_result
from claude_auto_review.stop.orchestration.finalize_autocomplete import _attempt_review_autocomplete
from claude_auto_review.stop.orchestration.review_artifact_evaluator import classify_review_artifact_state
from claude_auto_review.stop.reviews.enums import AutocompleteStatus


def evaluate_artifact_and_plan(
    ctx: RuntimeContext,
    review_id: str,
    review_path: Path,
    prompt_file: Path,
    covered_entries: list,
    unreviewed: list,
    *,
    classify_fn=None,
    plan_for_artifact_state_fn=None,
    apply_plan_fn=None,
    attempt_autocomplete_fn=None,
    emitter=None,
):
    """Classify artifact state, attempt autocomplete if needed, and apply a finalize plan.

    Returns (result, payload) if a plan was determined, or None if the review
    is still pending after autocomplete.
    """
    classify_fn = classify_fn or classify_review_artifact_state
    plan_for_artifact_state_fn = plan_for_artifact_state_fn or plan_for_artifact_state
    apply_plan_fn = apply_plan_fn or _apply_finalize_plan_result
    attempt_autocomplete_fn = attempt_autocomplete_fn or _attempt_review_autocomplete

    artifact_state = classify_fn(
        review_path,
        minimum_blocking_severity=ctx.settings.minimum_blocking_severity,
        client_id=ctx.client_id,
    )
    plan = plan_for_artifact_state_fn(artifact_state)
    if plan is not None:
        return apply_plan_fn(ctx, plan, review_id, review_path, covered_entries, unreviewed, emitter=emitter)

    autocomplete_result = attempt_autocomplete_fn(ctx, review_id, review_path, prompt_file)

    artifact_state = classify_fn(
        review_path,
        minimum_blocking_severity=ctx.settings.minimum_blocking_severity,
        client_id=ctx.client_id,
    )
    plan = plan_for_artifact_state_fn(artifact_state)
    if plan is not None:
        return apply_plan_fn(ctx, plan, review_id, review_path, covered_entries, unreviewed, emitter=emitter)

    if autocomplete_result is not None and autocomplete_result.status == AutocompleteStatus.EMPTY_STDOUT:
        log_event(
            ctx.project_root,
            "stop_hook_reviewer_empty_blocked",
            client_id=ctx.client_id,
            reviewId=review_id,
        )

    return None
