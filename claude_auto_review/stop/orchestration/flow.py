from __future__ import annotations

from collections.abc import Callable
from typing import Any

from claude_auto_review.stop.orchestration.types.context import ResponsePayload, RuntimeContext, StopDecision
from claude_auto_review.stop.orchestration.decision_engine import StopDecisionEngine
from claude_auto_review.stop.orchestration.types.resolution import StopDecisionKind
from claude_auto_review.stop.response import ResponseEmitter, StdoutResponseEmitter

StopHandler = Callable[[StopDecisionEngine, StopDecision, ResponseEmitter], int]


def _emit_response(payload: ResponsePayload, emitter: ResponseEmitter) -> int:
    if payload.feedback is None:
        emitter.approve(payload.system_message)
        return 0
    emitter.block(payload.system_message, payload.feedback)
    return 2


def _handle_allow(engine: StopDecisionEngine, decision: StopDecision, emitter: ResponseEmitter) -> int:
    if decision.reason is None:
        raise ValueError("ALLOW decision missing reason")
    return _emit_response(
        ResponsePayload(
            system_message=f"Claude Auto Review: stop approved ({decision.reason.value})"
        ),
        emitter=emitter,
    )


def _handle_terminal(engine: StopDecisionEngine, decision: StopDecision, emitter: ResponseEmitter) -> int:
    details: dict[str, Any] = decision.details or {}
    return int(details["exit_code"])


def _handle_finalize(engine: StopDecisionEngine, decision: StopDecision, emitter: ResponseEmitter) -> int:
    details: dict[str, Any] = decision.details or {}
    return int(engine.finalize(details["resolution"]))


_HANDLER_REGISTRY: dict[StopDecisionKind, StopHandler] = {
    StopDecisionKind.ALLOW: _handle_allow,
    StopDecisionKind.TERMINAL: _handle_terminal,
    StopDecisionKind.FINALIZE: _handle_finalize,
}


def register_stop_handler(kind: StopDecisionKind, handler: StopHandler) -> None:
    _HANDLER_REGISTRY[kind] = handler


def dispatch_stop_decision(
    engine: StopDecisionEngine,
    decision: StopDecision,
    *,
    emitter: ResponseEmitter,
) -> int:
    handler = _HANDLER_REGISTRY.get(decision.kind)
    if handler is None:
        raise ValueError(f"Unhandled stop decision kind: {decision.kind}")
    return handler(engine, decision, emitter)


def run_stop_flow(ctx: RuntimeContext, *, emitter: ResponseEmitter | None = None) -> int:
    response_emitter = emitter or StdoutResponseEmitter()
    engine = StopDecisionEngine(ctx, emitter=response_emitter)
    decision = engine.run()
    return dispatch_stop_decision(engine, decision, emitter=response_emitter)
