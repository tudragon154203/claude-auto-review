"""Registry-based pipeline for the stop-flow stages.

Each stage implements the :class:`Stage` protocol.  The pipeline runner
executes stages in order; the first stage that returns a
:class:`StopDecision` terminates the pipeline.  Stages may also return
``None`` to indicate they produced no decision but enriched the shared
context for downstream stages (e.g. loading state).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from claude_auto_review.stop.orchestration.types.context import RuntimeContext, StopDecision


@runtime_checkable
class Stage(Protocol):
    """A single step in the stop-flow pipeline."""

    def evaluate(self, ctx: RuntimeContext) -> StopDecision | None: ...


def run_pipeline(stages: list[Stage], ctx: RuntimeContext) -> StopDecision:
    """Execute *stages* in order, returning the first non-``None`` decision.

    Raises ``RuntimeError`` if every stage returns ``None`` (the pipeline
    must always produce a terminal decision).
    """
    for stage in stages:
        decision = stage.evaluate(ctx)
        if decision is not None:
            return decision
    raise RuntimeError("Pipeline exhausted without a terminal decision")
