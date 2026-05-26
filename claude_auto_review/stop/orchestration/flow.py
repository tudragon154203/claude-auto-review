from claude_auto_review.stop.orchestration.decision_engine import StopDecisionEngine
from claude_auto_review.stop.response import approve_response


def _handle_allow(decision):
    approve_response(f"Claude Auto Review: stop approved ({decision.reason})")
    return 0


def _handle_terminal(decision):
    return decision.details["exit_code"]


def _handle_finalize(engine, decision):
    return engine.finalize(decision.details["resolution"])


def run_stop_flow(project_root, payload, *, client_id=None, settings=None):
    engine = StopDecisionEngine(project_root, payload, client_id=client_id, settings=settings)
    decision = engine.evaluate()
    handlers = {
        "allow": lambda: _handle_allow(decision),
        "terminal": lambda: _handle_terminal(decision),
        "finalize": lambda: _handle_finalize(engine, decision),
    }
    return handlers.get(decision.kind, handlers["finalize"])()
