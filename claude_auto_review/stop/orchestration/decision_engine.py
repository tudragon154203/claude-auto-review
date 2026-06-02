"""Stop-decision engine wiring together context, dependencies, and stop-flow service."""

from __future__ import annotations

from claude_auto_review.stop.orchestration.deps import (
    ReviewEvalDeps,
    StopFlowDependencies,
    build_default_dependencies,
    build_default_eval_deps,
)
from claude_auto_review.stop.orchestration.pipeline.service import StopFlowService
from claude_auto_review.stop.orchestration.types.protocols import ResponseEmitter
from claude_auto_review.stop.response import StdoutResponseEmitter
from claude_auto_review.state.store.writer import StateEventWriter as _ConcreteStateEventWriter


class StopDecisionEngine:
    def __init__(
        self,
        ctx,
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
    ctx,
    *,
    emitter: ResponseEmitter | None = None,
    load_state_snapshot_fn=None,
    get_unreviewed_files_fn=None,
    consecutive_stop_blocks_fn=None,
    classify_last_assistant_message_fn=None,
    classifier_persist_factory=None,
    resolve_pending_review_fn=None,
    get_reviewer_prompt_script_fn=None,
    log_event_fn=None,
    finalize_review_stop_fn=None,
):
    response_emitter = emitter or StdoutResponseEmitter()
    deps = build_default_dependencies(
        emitter=response_emitter,
        load_state_snapshot_fn=load_state_snapshot_fn,
        get_unreviewed_files_fn=get_unreviewed_files_fn,
        consecutive_stop_blocks_fn=consecutive_stop_blocks_fn,
        classify_last_assistant_message_fn=classify_last_assistant_message_fn,
        classifier_persist_factory=classifier_persist_factory,
        resolve_pending_review_fn=resolve_pending_review_fn,
        get_reviewer_prompt_script_fn=get_reviewer_prompt_script_fn,
        log_event_fn=log_event_fn,
        finalize_review_stop_fn=finalize_review_stop_fn,
    )
    eval_deps = build_default_eval_deps(
        emitter=response_emitter,
        state_event_writer_factory=_ConcreteStateEventWriter,
        log_event_fn=log_event_fn,
    )
    return StopDecisionEngine(ctx, deps=deps, eval_deps=eval_deps)
