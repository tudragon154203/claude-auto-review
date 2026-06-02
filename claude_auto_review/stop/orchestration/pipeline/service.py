from __future__ import annotations

from collections.abc import Callable
from typing import Any

from claude_auto_review.stop.orchestration.types.context import RuntimeContext, StopDecision
from claude_auto_review.stop.orchestration.deps import StopFlowDependencies
from claude_auto_review.stop.orchestration.pipeline.stages import (
    run_allow_no_unreviewed_stage,
    run_circuit_breaker_stage,
    run_classifier_stage,
    run_enabled_stage,
    run_pending_stage,
    run_state_stage,
)

StageFn = Callable[[RuntimeContext, StopFlowDependencies, dict[str, Any]], StopDecision | None]


def _enabled_stage(ctx: RuntimeContext, deps: StopFlowDependencies, shared: dict) -> StopDecision | None:
    return run_enabled_stage(ctx, log_event_fn=deps.log_event)


def _state_and_allow_stage(ctx: RuntimeContext, deps: StopFlowDependencies, shared: dict) -> StopDecision | None:
    state_snapshot, state, unreviewed = run_state_stage(
        ctx,
        load_state_snapshot_fn=deps.state.load_state_snapshot,
        get_unreviewed_files_fn=deps.state.get_unreviewed_files,
    )
    shared["state_snapshot"] = state_snapshot
    shared["state"] = state
    shared["unreviewed"] = unreviewed
    return run_allow_no_unreviewed_stage(unreviewed)


def _circuit_breaker_stage(ctx: RuntimeContext, deps: StopFlowDependencies, shared: dict) -> StopDecision | None:
    return run_circuit_breaker_stage(
        ctx,
        shared.get("state_snapshot"),
        consecutive_stop_blocks_fn=deps.state.consecutive_stop_blocks,
    )


def _classifier_stage(ctx: RuntimeContext, deps: StopFlowDependencies, shared: dict) -> StopDecision | None:
    return run_classifier_stage(
        ctx,
        classify_last_assistant_message_fn=deps.classifier.classify_last_assistant_message,
        classifier_persist_factory=deps.classifier.classifier_persist_factory,
    )


def _pending_stage(ctx: RuntimeContext, deps: StopFlowDependencies, shared: dict) -> StopDecision:
    return run_pending_stage(
        ctx,
        shared.get("state"),
        shared.get("unreviewed"),
        resolve_pending_review_fn=deps.review.resolve_pending_review,
        get_reviewer_prompt_script_fn=deps.review.get_reviewer_prompt_script,
        emitter=deps.emitter,
        log_event_fn=deps.log_event,
    )


def default_stages() -> list[StageFn]:
    return [_enabled_stage, _state_and_allow_stage, _circuit_breaker_stage, _classifier_stage, _pending_stage]


class StopFlowService:
    def __init__(self, ctx: RuntimeContext, *, deps: StopFlowDependencies, stages: list[StageFn] | None = None):
        self.ctx = ctx
        self.deps = deps
        self._stages = stages or default_stages()

    def evaluate(self) -> StopDecision:
        shared: dict[str, Any] = {}
        for stage in self._stages:
            decision = stage(self.ctx, self.deps, shared)
            if decision is not None:
                return decision
        raise RuntimeError("No pipeline stage produced a decision")

    def run(self) -> StopDecision:
        return self.evaluate()
