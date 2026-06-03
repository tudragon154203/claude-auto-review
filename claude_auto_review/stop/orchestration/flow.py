from __future__ import annotations

from collections.abc import Callable

from claude_auto_review.stop.orchestration.deps import DependencyOverrides
from claude_auto_review.stop.orchestration.decision_engine import StopDecisionEngine, build_decision_engine
from claude_auto_review.stop.orchestration.types.context import (
    FinalizeDetails,
    ResponsePayload,
    RuntimeContext,
    StopDecision,
    TerminalDetails,
)
from claude_auto_review.stop.orchestration.types.resolution import StopDecisionKind
from claude_auto_review.stop.response import ResponseEmitter, StdoutResponseEmitter

StopHandler = Callable[[StopDecisionEngine, StopDecision, ResponseEmitter], int]


def _build_response_payload(message: str, feedback: str | None = None) -> ResponsePayload:
    return ResponsePayload(system_message=message, feedback=feedback)


def _emit_response(payload: ResponsePayload, emitter: ResponseEmitter) -> int:
    if payload.feedback is None:
        emitter.approve(payload.system_message)
        return 0
    emitter.block(payload.system_message, payload.feedback)
    return 2


def _handle_allow(engine: StopDecisionEngine, decision: StopDecision, emitter: ResponseEmitter) -> int:
    if decision.reason is None:
        raise ValueError("ALLOW decision missing reason")
    payload = _build_response_payload(f"Claude Auto Review: stop approved ({decision.reason.value})")
    return _emit_response(payload, emitter=emitter)


def _handle_terminal(engine: StopDecisionEngine, decision: StopDecision, emitter: ResponseEmitter) -> int:
    details = decision.details
    assert isinstance(details, TerminalDetails)
    return details.exit_code


def _handle_finalize(engine: StopDecisionEngine, decision: StopDecision, emitter: ResponseEmitter) -> int:
    details = decision.details
    assert isinstance(details, FinalizeDetails)
    return int(engine.finalize(details.resolution))


_STOP_HANDLERS: dict[StopDecisionKind, StopHandler] = {
    StopDecisionKind.ALLOW: _handle_allow,
    StopDecisionKind.TERMINAL: _handle_terminal,
    StopDecisionKind.FINALIZE: _handle_finalize,
}


def dispatch_stop_decision(
    engine: StopDecisionEngine,
    decision: StopDecision,
    *,
    emitter: ResponseEmitter,
) -> int:
    handler = _STOP_HANDLERS.get(decision.kind)
    if handler is None:
        raise ValueError(f"Unhandled stop decision kind: {decision.kind}")
    return handler(engine, decision, emitter)


def run_stop_flow(ctx: RuntimeContext, *, emitter: ResponseEmitter | None = None) -> int:
    response_emitter = emitter or StdoutResponseEmitter()
    engine = build_decision_engine(ctx, overrides=DependencyOverrides(emitter=response_emitter))
    decision = engine.run()
    return dispatch_stop_decision(engine, decision, emitter=response_emitter)
