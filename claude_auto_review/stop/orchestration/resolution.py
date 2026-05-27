from dataclasses import dataclass
from enum import Enum

from claude_auto_review.state.models import ReviewMetadata, StateEvent


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
class StopFlowResolution:
    state: list[StateEvent]
    unreviewed: list
    review: ReviewMetadata | None = None
    exit_code: int | None = None

    @property
    def is_terminal(self):
        return self.exit_code is not None


@dataclass(frozen=True)
class FinalizeResult:
    action: FinalizeAction
    exit_code: int
