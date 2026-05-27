from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from claude_auto_review.stop.orchestration.context import RuntimeContext, StopDecision
from claude_auto_review.stop.orchestration.resolution import StopDecisionKind
from claude_auto_review.stop.orchestration.stages import (
    run_allow_no_unreviewed_stage,
    run_classifier_stage,
    run_circuit_breaker_stage,
    run_enabled_stage,
    run_pending_stage,
    run_state_stage,
)


@dataclass(frozen=True)
class StopFlowDependencies:
    load_state_snapshot: Callable
    get_unreviewed_files: Callable
    consecutive_stop_blocks: Callable
    classify_last_assistant_message: Callable
    resolve_pending_review: Callable
    get_reviewer_prompt_script: Callable
    log_event: Callable


class StopFlowService:
    def __init__(self, ctx: RuntimeContext, deps: StopFlowDependencies):
        self.ctx = ctx
        self.deps = deps

    def evaluate(self) -> StopDecision:
        stage_result = run_enabled_stage(self.ctx, log_event_fn=self.deps.log_event)
        if stage_result is not None:
            return StopDecision(kind=stage_result.kind, reason=stage_result.reason)

        state_snapshot, state, unreviewed = run_state_stage(
            self.ctx,
            load_state_snapshot_fn=self.deps.load_state_snapshot,
            get_unreviewed_files_fn=self.deps.get_unreviewed_files,
        )

        stage_result = run_allow_no_unreviewed_stage(unreviewed)
        if stage_result is not None:
            return StopDecision(kind=stage_result.kind, reason=stage_result.reason)

        stage_result = run_circuit_breaker_stage(
            self.ctx,
            state_snapshot,
            consecutive_stop_blocks_fn=self.deps.consecutive_stop_blocks,
        )
        if stage_result is not None:
            return StopDecision(
                kind=stage_result.kind,
                reason=stage_result.reason,
                details=stage_result.details,
            )

        stage_result = run_classifier_stage(
            self.ctx,
            classify_last_assistant_message_fn=self.deps.classify_last_assistant_message,
        )
        if stage_result is not None:
            return StopDecision(
                kind=stage_result.kind,
                reason=stage_result.reason,
                details=stage_result.details,
            )

        stage_result = run_pending_stage(
            self.ctx,
            state,
            unreviewed,
            resolve_pending_review_fn=self.deps.resolve_pending_review,
            get_reviewer_prompt_script_fn=self.deps.get_reviewer_prompt_script,
        )
        if stage_result.kind is StopDecisionKind.TERMINAL:
            return StopDecision(
                kind=StopDecisionKind.TERMINAL,
                details={"exit_code": stage_result.exit_code},
            )

        return StopDecision(
            kind=StopDecisionKind.FINALIZE,
            details={"resolution": stage_result.resolution},
        )

    def run(self) -> StopDecision:
        return self.evaluate()

