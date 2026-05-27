from __future__ import annotations

from pathlib import Path


SETTING_ENABLED = "enabled"
SETTING_RULES_FILE = "rulesFile"
SETTING_INCLUDE_EXTS = "includeExtensions"
SETTING_SKIP_EXTS = "skipExtensions"
SETTING_MAX_STOP_PASSES = "maxStopPasses"
SETTING_MINIMUM_BLOCKING_SEVERITY = "minimumBlockingSeverity"
SETTING_PENDING_TIMEOUT = "pendingReviewTimeoutHours"
SETTING_REVIEWER_BACKEND = "reviewerBackend"
SETTING_REVIEWER_MODEL = "reviewerModel"
SETTING_REVIEWER_TIMEOUT = "reviewerTimeoutSeconds"
SETTING_FEEDBACK_MAX_CHARS = "reviewFeedbackMaxChars"
SETTING_CLASSIFIER_ENABLED = "lastAssistantMessageClassifierEnabled"
SETTING_CLASSIFIER_TIMEOUT = "lastAssistantMessageClassifierTimeoutSeconds"
SETTING_CLASSIFIER_MODEL = "classifierModel"
SETTING_STALE_CLIENT_TIMEOUT = "staleClientTimeoutHours"
SETTING_DEBUG = "debug"

DEFAULT_RULES_FILE = str(Path(".claude") / "claude-auto-review" / "review-rules.md")

KNOWN_SETTING_KEYS = frozenset(
    {
        SETTING_ENABLED,
        SETTING_RULES_FILE,
        SETTING_INCLUDE_EXTS,
        SETTING_SKIP_EXTS,
        SETTING_MAX_STOP_PASSES,
        SETTING_MINIMUM_BLOCKING_SEVERITY,
        SETTING_PENDING_TIMEOUT,
        SETTING_REVIEWER_BACKEND,
        SETTING_REVIEWER_MODEL,
        SETTING_REVIEWER_TIMEOUT,
        SETTING_FEEDBACK_MAX_CHARS,
        SETTING_CLASSIFIER_ENABLED,
        SETTING_CLASSIFIER_TIMEOUT,
        SETTING_CLASSIFIER_MODEL,
        SETTING_STALE_CLIENT_TIMEOUT,
        SETTING_DEBUG,
    }
)
