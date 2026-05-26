from claude_auto_review.stop.orchestration.decision_engine import StopDecisionEngine
from claude_auto_review.stop.response import approve_response

def run_stop_flow(project_root, payload, *, client_id=None, settings=None):
    engine = StopDecisionEngine(project_root, payload, client_id=client_id, settings=settings)
    decision = engine.evaluate()
    if decision.kind == "allow":
        approve_response(f"Claude Auto Review: stop approved ({decision.reason})")
        return 0
    if decision.kind == "terminal":
        return decision.details["exit_code"]
    return engine.finalize(decision.details["resolution"])
