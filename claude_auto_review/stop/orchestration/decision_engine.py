"""Stop-decision engine wiring together context, dependencies, and stop-flow service."""

from __future__ import annotations

from claude_auto_review.stop.orchestration.deps import (
    DependencyOverrides,
    ReviewEvalDeps,
    StopFlowDependencies,
    build_default_dependencies,
    build_default_eval_deps,
)
from claude_auto_review.stop.orchestration.pipeline.service import StopFlowService
from claude_auto_review.stop.orchestration.types.context import RuntimeContext
from claude_auto_review.stop.response import StdoutResponseEmitter


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
    deps = build_default_dependencies(overrides, emitter=response_emitter)
    eval_deps = build_default_eval_deps(overrides, emitter=response_emitter)
    return StopDecisionEngine(ctx, deps=deps, eval_deps=eval_deps)