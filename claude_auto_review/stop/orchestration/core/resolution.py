from dataclasses import dataclass

from claude_auto_review.state.core.models import ReviewMetadata, StateEvent


@dataclass(frozen=True)
class StopFlowResolution:
    state: list[StateEvent]
    unreviewed: list
    review: ReviewMetadata | None = None
    exit_code: int | None = None

    @property
    def is_terminal(self):
        return self.exit_code is not None
