from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from claude_auto_review.config.constants.defaults import (
    DEFAULT_CLASSIFIER_MODEL,
    DEFAULT_CLASSIFIER_TIMEOUT_SECONDS,
    DEFAULT_RULES_FILE,
)
from claude_auto_review.config.constants.severity import coerce_minimum_blocking_severity
from claude_auto_review.config.reviewer.backends import DEFAULT_REVIEWER_BACKEND
from claude_auto_review.config.utils.coercion import coerce_bool, coerce_extensions, coerce_float, coerce_int, coerce_rules_file


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


@dataclass(frozen=True)
class SettingSpec:
    json_key: str
    field_name: str
    group: str = "core"
    coerce_fn: Callable[[Any], Any] | None = None
    default: Any = None
    to_mapping_transform: Callable[[Any], Any] | None = None


def _coerce_reviewer_model(raw):
    return None if raw in (None, "") else str(raw)


SETTING_SPECS: tuple[SettingSpec, ...] = (
    # Core
    SettingSpec(SETTING_ENABLED, "enabled", group="core", coerce_fn=lambda v: coerce_bool(v, True)),
    SettingSpec(SETTING_DEBUG, "debug", group="core", coerce_fn=lambda v: coerce_bool(v, True)),
    # Reviewer
    SettingSpec(SETTING_REVIEWER_BACKEND, "reviewer_backend", group="reviewer", coerce_fn=lambda v: str(v or DEFAULT_REVIEWER_BACKEND).lower()),
    SettingSpec(SETTING_REVIEWER_MODEL, "reviewer_model", group="reviewer", coerce_fn=_coerce_reviewer_model),
    SettingSpec(SETTING_REVIEWER_TIMEOUT, "reviewer_timeout_seconds", group="reviewer", coerce_fn=lambda v: coerce_int(v, 600)),
    SettingSpec(SETTING_FEEDBACK_MAX_CHARS, "review_feedback_max_chars", group="reviewer", coerce_fn=lambda v: max(0, coerce_int(v, 9000))),
    # Classifier
    SettingSpec(SETTING_CLASSIFIER_ENABLED, "last_assistant_message_classifier_enabled", group="classifier", coerce_fn=lambda v: coerce_bool(v, True)),
    SettingSpec(SETTING_CLASSIFIER_TIMEOUT, "last_assistant_message_classifier_timeout_seconds", group="classifier", coerce_fn=lambda v: coerce_float(v, DEFAULT_CLASSIFIER_TIMEOUT_SECONDS)),
    SettingSpec(SETTING_CLASSIFIER_MODEL, "classifier_model", group="classifier", coerce_fn=lambda v: str(v or DEFAULT_CLASSIFIER_MODEL)),
    # Filters
    SettingSpec(SETTING_RULES_FILE, "rules_file", group="filters", default=DEFAULT_RULES_FILE, coerce_fn=coerce_rules_file),
    SettingSpec(SETTING_INCLUDE_EXTS, "include_extensions", group="filters", coerce_fn=coerce_extensions, to_mapping_transform=list),
    SettingSpec(SETTING_SKIP_EXTS, "skip_extensions", group="filters", coerce_fn=coerce_extensions, to_mapping_transform=list),
    # Flow
    SettingSpec(SETTING_MAX_STOP_PASSES, "max_stop_passes", group="flow", coerce_fn=lambda v: coerce_int(v, 5)),
    SettingSpec(SETTING_MINIMUM_BLOCKING_SEVERITY, "minimum_blocking_severity", group="flow", coerce_fn=coerce_minimum_blocking_severity),
    SettingSpec(SETTING_PENDING_TIMEOUT, "pending_review_timeout_hours", group="flow", coerce_fn=lambda v: coerce_float(v, 1)),
    SettingSpec(SETTING_STALE_CLIENT_TIMEOUT, "stale_client_timeout_hours", group="flow", coerce_fn=lambda v: coerce_float(v, 48)),
)

KNOWN_SETTING_KEYS = frozenset(spec.json_key for spec in SETTING_SPECS)
