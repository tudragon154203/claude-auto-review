from __future__ import annotations

from claude_auto_review.stop.orchestration.context import ResponsePayload, StopDecision
from claude_auto_review.stop.orchestration.decision_engine import StopDecisionEngine
from claude_auto_review.stop.orchestration.resolution import StopDecisionKind
from claude_auto_review.stop.response import approve_response, block_response


def _emit_response(payload: ResponsePayload):
    if payload.feedback is None:
        approve_response(payload.system_message)
        return 0
    block_response(payload.system_message, payload.feedback)
    return 2


def _handle_allow(decision: StopDecision):
    assert decision.reason is not None
    return _emit_response(ResponsePayload(system_message=f"Claude Auto Review: stop approved ({decision.reason.value})"))


def _handle_terminal(decision: StopDecision):
    details = decision.details or {}
    return details["exit_code"]


def _handle_finalize(engine: StopDecisionEngine, decision: StopDecision):
    details = decision.details or {}
    return engine.finalize(details["resolution"])


def run_stop_flow(project_root, payload, *, client_id=None, settings=None):
    """Main entry point for the stop hook — evaluates, finalizes, and emits the response."""
    engine = StopDecisionEngine(project_root, payload, client_id=client_id, settings=settings)
    decision = engine.evaluate()
    handlers = {
        StopDecisionKind.ALLOW: lambda: _handle_allow(decision),
        StopDecisionKind.TERMINAL: lambda: _handle_terminal(decision),
        StopDecisionKind.FINALIZE: lambda: _handle_finalize(engine, decision),
    }
    return handlers.get(decision.kind, handlers[StopDecisionKind.FINALIZE])()
