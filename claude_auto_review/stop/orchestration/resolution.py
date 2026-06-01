from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from claude_auto_review.state.event_types import StateEvent
from claude_auto_review.state.review_records import ReviewMetadata


class StopDecisionKind(str, Enum):
    ALLOW = "allow"
    TERMINAL = "terminal"
    FINALIZE = "finalize"


class FinalizeAction(str, Enum):
    APPROVED = "approved"
    BLOCKED_FINDINGS = "blocked_findings"
    BLOCKED_PENDING = "blocked_pending"
    BLOCKED_INVALID_SETTINGS = "blocked_invalid_settings"
    BLOCKED_PARTIAL_REVIEW = "blocked_partial_review"


@dataclass(frozen=True)
class TerminalResolution:
    exit_code: int


@dataclass(frozen=True)
class ReviewResolution:
    review: ReviewMetadata
    state: list[StateEvent]
    unreviewed: list


StopFlowResolution = TerminalResolution | ReviewResolution


@dataclass(frozen=True)
class FinalizeResult:
    action: FinalizeAction
    exit_code: int

