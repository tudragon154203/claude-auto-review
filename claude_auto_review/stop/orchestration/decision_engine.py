"""Stop-decision engine wiring together context, dependencies, and stop-flow service."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional

from claude_auto_review.stop.orchestration.deps import (
    ReviewEvalDeps,
    StopFlowDependencies,
    build_default_dependencies,
    build_default_eval_deps,
)
from claude_auto_review.stop.orchestration.pipeline.service import StopFlowService
from claude_auto_review.stop.orchestration.types.context import RuntimeContext
from claude_auto_review.stop.orchestration.types.protocols import ResponseEmitter
from claude_auto_review.stop.response import StdoutResponseEmitter


@dataclass(frozen=True)
class DependencyOverrides:
    emitter: Optional[ResponseEmitter] = None
    load_state_snapshot_fn: Optional[Callable] = None
    get_unreviewed_files_fn: Optional[Callable] = None
    consecutive_stop_blocks_fn: Optional[Callable] = None
    classify_last_assistant_message_fn: Optional[Callable] = None
    classifier_persist_factory: Optional[Callable] = None
    resolve_pending_review_fn: Optional[Callable] = None
    get_reviewer_prompt_script_fn: Optional[Callable] = None
    log_event_fn: Optional[Callable] = None
    finalize_review_stop_fn: Optional[Callable] = None
    state_event_writer_factory: Optional[Callable] = None


class StopDecisionEngine:
    def __init__(
        self,
        ctx: RuntimeContext,
        *,
        deps: StopFlowDependencies,
        eval_deps: ReviewEvalDeps,
    ):
        self.ctx = ctx
        self.deps = deps
        self.eval_deps = eval_deps
        self.emitter = deps.emitter
        self._service = StopFlowService(ctx, deps=deps)

    def evaluate(self):
        return self._service.evaluate()

    def run(self):
        return self._service.run()

    def finalize(self, resolution):
        return self.deps.finalize_review_stop(self.ctx, resolution, deps=self.eval_deps)


def build_decision_engine(
    ctx: RuntimeContext,
    *,
    overrides: DependencyOverrides | None = None,
):
    overrides = DependencyOverrides() if overrides is None else overrides
    response_emitter = overrides.emitter or StdoutResponseEmitter()

    deps = build_default_dependencies(
        emitter=response_emitter,
        load_state_snapshot_fn=overrides.load_state_snapshot_fn,
        get_unreviewed_files_fn=overrides.get_unreviewed_files_fn,
        consecutive_stop_blocks_fn=overrides.consecutive_stop_blocks_fn,
        classify_last_assistant_message_fn=overrides.classify_last_assistant_message_fn,
        classifier_persist_factory=overrides.classifier_persist_factory,
        resolve_pending_review_fn=overrides.resolve_pending_review_fn,
        get_reviewer_prompt_script_fn=overrides.get_reviewer_prompt_script_fn,
        log_event_fn=overrides.log_event_fn,
        finalize_review_stop_fn=overrides.finalize_review_stop_fn,
    )

    writer_factory = overrides.state_event_writer_factory
    if writer_factory is None:
        from claude_auto_review.state.store.writer import StateEventWriter as _ConcreteStateEventWriter

        writer_factory = _ConcreteStateEventWriter

    eval_deps = build_default_eval_deps(
        emitter=response_emitter,
        state_event_writer_factory=writer_factory,
        log_event_fn=overrides.log_event_fn,
    )
    return StopDecisionEngine(ctx, deps=deps, eval_deps=eval_deps)
