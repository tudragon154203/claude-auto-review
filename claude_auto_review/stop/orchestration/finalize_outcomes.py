from __future__ import annotations

from dataclasses import dataclass

from claude_auto_review.stop.orchestration.resolution import FinalizeAction, FinalizeResult


@dataclass(frozen=True)
class FinalizePlan:
    result: FinalizeResult
    effect: str


def approved_result() -> FinalizeResult:
    return FinalizeResult(action=FinalizeAction.APPROVED, exit_code=0)


def blocked_result(action: FinalizeAction) -> FinalizeResult:
    return FinalizeResult(action=action, exit_code=2)


def artifact_status_name(artifact_state) -> str | None:
    status = getattr(artifact_state, "status", None)
    return status.value if hasattr(status, "value") else status


def plan_for_artifact_state(artifact_state):
    status_name = artifact_status_name(artifact_state)
    if status_name == "complete_clean":
        return FinalizePlan(result=approved_result(), effect="apply_completed_clean_review")
    if status_name == "complete_findings":
        return FinalizePlan(result=blocked_result(FinalizeAction.BLOCKED_FINDINGS), effect="record_findings_block")
    return None


def plan_for_invalid_settings():
    return FinalizePlan(
        result=blocked_result(FinalizeAction.BLOCKED_INVALID_SETTINGS),
        effect="invalid_settings_block",
    )


def plan_for_partial_review():
    return FinalizePlan(
        result=blocked_result(FinalizeAction.BLOCKED_PARTIAL_REVIEW),
        effect="partial_review_block",
    )


def plan_for_pending_review():
    return FinalizePlan(
        result=blocked_result(FinalizeAction.BLOCKED_PENDING),
        effect="pending_review_block",
    )
