from __future__ import annotations

from claude_auto_review.stop.orchestration.context import ResponsePayload, RuntimeContext, StopDecision
from claude_auto_review.stop.orchestration.decision_engine import StopDecisionEngine
from claude_auto_review.stop.orchestration.resolution import StopDecisionKind
from claude_auto_review.stop.response import StdoutResponseEmitter


def _emit_response(payload: ResponsePayload, *, emitter):
    if payload.feedback is None:
        emitter.approve(payload.system_message)
        return 0
    emitter.block(payload.system_message, payload.feedback)
    return 2


def _handle_allow(decision: StopDecision, *, emitter):
    if decision.reason is None:
        raise ValueError("ALLOW decision missing reason")
    return _emit_response(ResponsePayload(system_message=f"Claude Auto Review: stop approved ({decision.reason.value})"), emitter=emitter)


def _handle_terminal(decision: StopDecision):
    details = decision.details or {}
    return details["exit_code"]


def _handle_finalize(engine: StopDecisionEngine, decision: StopDecision, *, emitter):
    details = decision.details or {}
    return engine.finalize(details["resolution"], emitter=emitter)


def run_stop_flow(ctx: RuntimeContext, *, emitter=None):
    """Main entry point for the stop hook — evaluates, finalizes, and emits the response."""
    emitter = emitter or StdoutResponseEmitter()
    engine = StopDecisionEngine(ctx, emitter=emitter)
    decision = engine.evaluate()
    handlers = {
        StopDecisionKind.ALLOW: lambda: _handle_allow(decision, emitter=emitter),
        StopDecisionKind.TERMINAL: lambda: _handle_terminal(decision),
        StopDecisionKind.FINALIZE: lambda: _handle_finalize(engine, decision, emitter=emitter),
    }
    return handlers.get(decision.kind, handlers[StopDecisionKind.FINALIZE])()
