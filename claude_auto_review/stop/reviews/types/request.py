from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from claude_auto_review.config.settings.models import DEFAULT_REVIEWER_MODEL
from claude_auto_review.stop.orchestration.types.context import RuntimeContext


@dataclass(frozen=True)
class ReviewRequest:
    ctx: RuntimeContext
    review_id: str
    review_path: Path
    prompt_file: Path
    user_prompt: str
    reviewer_timeout_seconds: int = 600
    model: str = DEFAULT_REVIEWER_MODEL
