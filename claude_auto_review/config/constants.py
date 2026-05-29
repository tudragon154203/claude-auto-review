from __future__ import annotations

from pathlib import Path

# Exit codes returned by the stop hook.
EXIT_STOP_APPROVED = 0
EXIT_REVIEW_FAILED = 2

# Time conversion constants.
SECONDS_PER_MINUTE = 60
SECONDS_PER_HOUR = 3600
MS_PER_SECOND = 1000

# Default classifier timeout in seconds.
DEFAULT_CLASSIFIER_TIMEOUT_SECONDS = 20

# Duration display rounding precision (decimal places).
DURATION_ROUND_PRECISION = 3

# Default rules file path relative to project root.
DEFAULT_RULES_FILE = str(Path(".claude") / "claude-auto-review" / "review-rules.md")
