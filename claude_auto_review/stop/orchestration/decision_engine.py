"""Top-level orchestrator that wires up context, dependencies, and the stop-flow service."""

from __future__ import annotations

from claude_auto_review.stop.orchestration.context import RuntimeContext
from claude_auto_review.stop.orchestration.deps import build_default_dependencies, build_default_eval_deps
from claude_auto_review.stop.orchestration.service import StopFlowService
from claude_auto_review.stop.response import ResponseEmitter, StdoutResponseEmitter


class StopDecisionEngine:
    """Top-level orchestrator that wires up context, dependencies, and the stop-flow service."""

    def __init__(
        self,
        ctx: RuntimeContext,
        *,
        load_state_snapshot_fn=None,
        get_unreviewed_files_fn=None,
        consecutive_stop_blocks_fn=None,
        classify_last_assistant_message_fn=None,
        resolve_pending_review_fn=None,
        finalize_review_stop_fn=None,
        get_reviewer_prompt_script_fn=None,
        log_event_fn=None,
        emitter: ResponseEmitter | None = None,
        state_event_writer_factory=None,
        eval_deps=None,
    ):
        self._emitter = emitter or StdoutResponseEmitter()
        deps, finalize_fn = build_default_dependencies(
            load_state_snapshot_fn=load_state_snapshot_fn,
            get_unreviewed_files_fn=get_unreviewed_files_fn,
            consecutive_stop_blocks_fn=consecutive_stop_blocks_fn,
            classify_last_assistant_message_fn=classify_last_assistant_message_fn,
            resolve_pending_review_fn=resolve_pending_review_fn,
            get_reviewer_prompt_script_fn=get_reviewer_prompt_script_fn,
            log_event_fn=log_event_fn,
            finalize_review_stop_fn=finalize_review_stop_fn,
            emitter=self._emitter,
            state_event_writer_factory=state_event_writer_factory,
        )
        self.ctx = ctx
        self._service = StopFlowService(self.ctx, deps)
        self._finalize_review_stop = finalize_fn
        self._eval_deps = eval_deps or build_default_eval_deps(
            log_event_fn=log_event_fn,
            state_event_writer_factory=state_event_writer_factory,
            emitter=self._emitter,
        )

    @property
    def service(self):
        return self._service

    def evaluate(self):
        return self._service.evaluate()

    def finalize(self, resolution, *, emitter=None):
        return self._finalize_review_stop(self.ctx, resolution, deps=self._eval_deps)
