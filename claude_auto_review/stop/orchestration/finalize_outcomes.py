from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from claude_auto_review.stop.orchestration.resolution import FinalizeAction, FinalizeResult


class FinalizeEffect(Enum):
    APPLY_COMPLETED_CLEAN_REVIEW = "apply_completed_clean_review"
    RECORD_FINDINGS_BLOCK = "record_findings_block"
    INVALID_SETTINGS_BLOCK = "invalid_settings_block"
    PARTIAL_REVIEW_BLOCK = "partial_review_block"
    PENDING_REVIEW_BLOCK = "pending_review_block"


@dataclass(frozen=True)
class FinalizePlan:
    result: FinalizeResult
    effect: FinalizeEffect


def approved_result() -> FinalizeResult:
    return FinalizeResult(action=FinalizeAction.APPROVED, exit_code=0)


def blocked_result(action: FinalizeAction) -> FinalizeResult:
    return FinalizeResult(action=action, exit_code=2)


def artifact_status_name(artifact_state) -> str | None:
    status = getattr(artifact_state, "status", None)
    if status is None:
        return None
    return str(status.value) if hasattr(status, "value") else str(status)


def plan_for_artifact_state(artifact_state):
    status_name = artifact_status_name(artifact_state)
    if status_name == "complete_clean":
        return FinalizePlan(result=approved_result(), effect=FinalizeEffect.APPLY_COMPLETED_CLEAN_REVIEW)
    if status_name == "complete_findings":
        return FinalizePlan(result=blocked_result(FinalizeAction.BLOCKED_FINDINGS), effect=FinalizeEffect.RECORD_FINDINGS_BLOCK)
    return None


def plan_for_invalid_settings():
    return FinalizePlan(
        result=blocked_result(FinalizeAction.BLOCKED_INVALID_SETTINGS),
        effect=FinalizeEffect.INVALID_SETTINGS_BLOCK,
    )


def plan_for_partial_review():
    return FinalizePlan(
        result=blocked_result(FinalizeAction.BLOCKED_PARTIAL_REVIEW),
        effect=FinalizeEffect.PARTIAL_REVIEW_BLOCK,
    )


def plan_for_pending_review():
    return FinalizePlan(
        result=blocked_result(FinalizeAction.BLOCKED_PENDING),
        effect=FinalizeEffect.PENDING_REVIEW_BLOCK,
    )
