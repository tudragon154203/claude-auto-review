"""Orchestrates the multi-stage stop decision pipeline."""

from __future__ import annotations

from claude_auto_review.stop.orchestration.context import RuntimeContext, StopDecision
from claude_auto_review.stop.orchestration.deps import StopFlowDependencies as StopFlowDependencies
from claude_auto_review.stop.orchestration.stages import (
    run_allow_no_unreviewed_stage,
    run_circuit_breaker_stage,
    run_classifier_stage,
    run_enabled_stage,
    run_pending_stage,
    run_state_stage,
)


class StopFlowService:
    """Orchestrates the multi-stage stop decision pipeline."""

    def __init__(self, ctx: RuntimeContext, deps: StopFlowDependencies):
        self.ctx = ctx
        self.deps = deps

    def evaluate(self) -> StopDecision:
        decision = run_enabled_stage(self.ctx, log_event_fn=self.deps.log_event)
        if decision is not None:
            return decision

        state_snapshot, state, unreviewed = run_state_stage(
            self.ctx,
            load_state_snapshot_fn=self.deps.load_state_snapshot,
            get_unreviewed_files_fn=self.deps.get_unreviewed_files,
        )

        decision = run_allow_no_unreviewed_stage(unreviewed)
        if decision is not None:
            return decision

        decision = run_circuit_breaker_stage(
            self.ctx,
            state_snapshot,
            consecutive_stop_blocks_fn=self.deps.consecutive_stop_blocks,
        )
        if decision is not None:
            return decision

        decision = run_classifier_stage(
            self.ctx,
            classify_last_assistant_message_fn=self.deps.classify_last_assistant_message,
        )
        if decision is not None:
            return decision

        return run_pending_stage(
            self.ctx,
            state,
            unreviewed,
            resolve_pending_review_fn=self.deps.resolve_pending_review,
            get_reviewer_prompt_script_fn=self.deps.get_reviewer_prompt_script,
            emitter=self.deps.emitter,
        )

    def run(self) -> StopDecision:
        return self.evaluate()
