from __future__ import annotations

from pathlib import Path

DEFAULT_RULES_FILE = str(Path(".claude") / "claude-auto-review" / "review-rules.md")
DEFAULT_CLASSIFIER_TIMEOUT_SECONDS = 20
DEFAULT_TIMEOUT_SECONDS = DEFAULT_CLASSIFIER_TIMEOUT_SECONDS
DEFAULT_CLASSIFIER_MODEL = "claude-haiku-4-5"
