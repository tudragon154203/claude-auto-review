"""Backward-compatible re-export of :mod:`review_executor`.

All public names are re-exported for callers that still reference
``claude_auto_review.stop.orchestration.pending_execution``.
"""

from __future__ import annotations

from claude_auto_review.stop.orchestration.response_actions import (  # noqa: F401
    fail_review as fail_review,
)
from claude_auto_review.stop.orchestration.review_executor import (  # noqa: F401
    execute_review_prompt as execute_review_prompt,
    resolve_prompted_review as resolve_prompted_review,
)
