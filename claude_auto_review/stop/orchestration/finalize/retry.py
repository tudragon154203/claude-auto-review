"""RetryPolicy for review autocomplete — kept separate to avoid circular imports."""
from __future__ import annotations

from dataclasses import dataclass, field

from claude_auto_review.stop.reviews.types.enums import AutocompleteStatus


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 2
    retryable_statuses: tuple[AutocompleteStatus, ...] = field(
        default_factory=lambda: (AutocompleteStatus.EMPTY_STDOUT,)
    )

    def should_retry(self, status: AutocompleteStatus, attempt: int) -> bool:
        return attempt < self.max_attempts - 1 and status in self.retryable_statuses
