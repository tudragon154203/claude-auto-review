from __future__ import annotations

from typing import Callable

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


def _handle_allow(engine, decision: StopDecision, *, emitter):
    if decision.reason is None:
        raise ValueError("ALLOW decision missing reason")
    return _emit_response(ResponsePayload(system_message=f"Claude Auto Review: stop approved ({decision.reason.value})"), emitter=emitter)


def _handle_terminal(engine, decision: StopDecision, *, emitter):
    details = decision.details or {}
    return details["exit_code"]


def _handle_finalize(engine: StopDecisionEngine, decision: StopDecision, *, emitter):
    details = decision.details or {}
    return engine.finalize(details["resolution"])


_HANDLER_REGISTRY: dict[StopDecisionKind, Callable] = {
    StopDecisionKind.ALLOW: _handle_allow,
    StopDecisionKind.TERMINAL: _handle_terminal,
    StopDecisionKind.FINALIZE: _handle_finalize,
}


def register_stop_handler(kind: StopDecisionKind, handler: Callable) -> None:
    """Register or replace a handler for a stop decision kind.

    This is the OCP extension point — new decision kinds can be
    handled without modifying run_stop_flow.
    """
    _HANDLER_REGISTRY[kind] = handler


def run_stop_flow(ctx: RuntimeContext, *, emitter=None):
    """Main entry point for the stop hook — evaluates, finalizes, and emits the response."""
    emitter = emitter or StdoutResponseEmitter()
    engine = StopDecisionEngine(ctx, emitter=emitter)
    decision = engine.evaluate()

    handler = _HANDLER_REGISTRY.get(decision.kind)
    if handler is not None:
        return handler(engine, decision, emitter=emitter)
    return _handle_finalize(engine, decision, emitter=emitter)
