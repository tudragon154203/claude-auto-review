"""Evaluate review artifact state and determine the finalize plan.

Single-Responsibility split:
  - _classify_artifact()        → classification only
  - _plan_for_classified_artifact() → planning only
  - _apply_plan()               → plan execution only
  - _attempt_autocomplete_if_needed() → autocomplete only
  - orchestrate_review_eval()   → coordinates the four above
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from claude_auto_review.stop.orchestration.context import RuntimeContext
from claude_auto_review.stop.orchestration.finalize_outcomes import FinalizeEffect
from claude_auto_review.stop.reviews.enums import AutocompleteStatus

if TYPE_CHECKING:
    from claude_auto_review.stop.orchestration.deps import ReviewEvalDeps


def _classify_artifact(ctx: RuntimeContext, review_path: Path, deps: ReviewEvalDeps):
    return deps.classifier.classify_fn(
        review_path,
        minimum_blocking_severity=ctx.settings.minimum_blocking_severity,
        client_id=ctx.client_id,
    )


def _plan_for_classified_artifact(deps: ReviewEvalDeps, artifact_state):
    return deps.planner.plan_for_artifact_state_fn(artifact_state)


def _apply_plan(
    ctx: RuntimeContext,
    plan,
    review_id: str,
    review_path: Path,
    covered_entries: list,
    unreviewed: list,
    deps: ReviewEvalDeps,
):
    writer = deps.executor.state_event_writer_factory(ctx.project_root, ctx.client_id)
    return deps.executor.apply_plan_fn(
        ctx,
        plan,
        review_id,
        review_path,
        covered_entries,
        unreviewed,
        state_event_writer=writer,
        emitter=deps.executor.emitter,
    )


def _attempt_autocomplete_if_needed(
    ctx: RuntimeContext,
    review_id: str,
    review_path: Path,
    prompt_file: Path,
    deps: ReviewEvalDeps,
):
    return deps.autocomplete.attempt_autocomplete_fn(
        ctx,
        review_id,
        review_path,
        prompt_file,
        log_event_fn=deps.autocomplete.log_event_fn,
    )


def _log_empty_autocomplete_block(ctx: RuntimeContext, review_id: str, deps: ReviewEvalDeps) -> None:
    deps.autocomplete.log_event_fn(
        ctx.project_root,
        "stop_hook_reviewer_empty_blocked",
        client_id=ctx.client_id,
        reviewId=review_id,
    )


def orchestrate_review_eval(
    ctx: RuntimeContext,
    review_id: str,
    review_path: Path,
    prompt_file: Path,
    covered_entries: list,
    unreviewed: list,
    *,
    deps: ReviewEvalDeps,
):
    """Classify the review artifact, apply any plan immediately,
    otherwise attempt autocomplete and then re-classify.

    Returns:
      - (result, payload) from plan execution if a plan was found
      - None if the review is still pending after all stages
    """
    artifact_state = _classify_artifact(ctx, review_path, deps)
    plan = _plan_for_classified_artifact(deps, artifact_state)
    if plan is not None:
        return _apply_plan(ctx, plan, review_id, review_path, covered_entries, unreviewed, deps=deps)

    result = _attempt_autocomplete_if_needed(ctx, review_id, review_path, prompt_file, deps=deps)

    artifact_state = _classify_artifact(ctx, review_path, deps)
    plan = _plan_for_classified_artifact(deps, artifact_state)
    if plan is not None:
        return _apply_plan(ctx, plan, review_id, review_path, covered_entries, unreviewed, deps=deps)

    if result is not None and result.status == AutocompleteStatus.EMPTY_STDOUT:
        _log_empty_autocomplete_block(ctx, review_id, deps)

    return None