from claude_auto_review.stop.orchestration.context import StopDecision
from claude_auto_review.stop.orchestration.decision_engine import StopDecisionEngine
from claude_auto_review.stop.orchestration.resolution import StopDecisionKind
from claude_auto_review.stop.response import approve_response


def _handle_allow(decision: StopDecision):
    approve_response(f"Claude Auto Review: stop approved ({decision.reason})")
    return 0


def _handle_terminal(decision: StopDecision):
    return decision.details["exit_code"]


def _handle_finalize(engine: StopDecisionEngine, decision: StopDecision):
    return engine.finalize(decision.details["resolution"])


def run_stop_flow(project_root, payload, *, client_id=None, settings=None):
    engine = StopDecisionEngine(project_root, payload, client_id=client_id, settings=settings)
    decision = engine.evaluate()
    handlers = {
        StopDecisionKind.ALLOW: lambda: _handle_allow(decision),
        StopDecisionKind.TERMINAL: lambda: _handle_terminal(decision),
        StopDecisionKind.FINALIZE: lambda: _handle_finalize(engine, decision),
    }
    return handlers.get(decision.kind, handlers[StopDecisionKind.FINALIZE])()
