from __future__ import annotations

from typing import Any, Mapping

from claude_auto_review.config.reviewer import DEFAULT_REVIEWER_BACKEND, resolve_reviewer_backend, resolve_reviewer_model
from claude_auto_review.config.severity import DEFAULT_MINIMUM_BLOCKING_SEVERITY, coerce_minimum_blocking_severity
from claude_auto_review.config.utils.coercion import coerce_bool, coerce_extensions, coerce_float, coerce_int
from claude_auto_review.config.utils.schema import (
    DEFAULT_RULES_FILE,
    KNOWN_SETTING_KEYS,
    SETTING_CLASSIFIER_ENABLED,
    SETTING_CLASSIFIER_MODEL,
    SETTING_CLASSIFIER_TIMEOUT,
    SETTING_DEBUG,
    SETTING_ENABLED,
    SETTING_FEEDBACK_MAX_CHARS,
    SETTING_INCLUDE_EXTS,
    SETTING_MAX_STOP_PASSES,
    SETTING_MINIMUM_BLOCKING_SEVERITY,
    SETTING_PENDING_TIMEOUT,
    SETTING_REVIEWER_BACKEND,
    SETTING_REVIEWER_MODEL,
    SETTING_REVIEWER_TIMEOUT,
    SETTING_RULES_FILE,
    SETTING_SKIP_EXTS,
    SETTING_STALE_CLIENT_TIMEOUT,
)

DEFAULT_CLASSIFIER_MODEL = "claude-haiku-4-5"
DEFAULT_TIMEOUT_SECONDS = 20


def plugin_settings_kwargs(mapping: Mapping[str, Any] | None) -> dict[str, Any]:
    data = dict(mapping) if isinstance(mapping, Mapping) else {}
    extras = {key: value for key, value in data.items() if key not in KNOWN_SETTING_KEYS}
    reviewer_model = data.get(SETTING_REVIEWER_MODEL)
    return {
        "enabled": coerce_bool(data.get(SETTING_ENABLED), True),
        "rules_file": str(data.get(SETTING_RULES_FILE, DEFAULT_RULES_FILE)),
        "include_extensions": coerce_extensions(data.get(SETTING_INCLUDE_EXTS)),
        "skip_extensions": coerce_extensions(data.get(SETTING_SKIP_EXTS)),
        "max_stop_passes": coerce_int(data.get(SETTING_MAX_STOP_PASSES), 5),
        "minimum_blocking_severity": coerce_minimum_blocking_severity(data.get(SETTING_MINIMUM_BLOCKING_SEVERITY)),
        "pending_review_timeout_hours": coerce_float(data.get(SETTING_PENDING_TIMEOUT), 1),
        "reviewer_backend": str(data.get(SETTING_REVIEWER_BACKEND, DEFAULT_REVIEWER_BACKEND)).lower(),
        "reviewer_model": None if reviewer_model in (None, "") else str(reviewer_model),
        "reviewer_timeout_seconds": coerce_int(data.get(SETTING_REVIEWER_TIMEOUT), 600),
        "review_feedback_max_chars": max(0, coerce_int(data.get(SETTING_FEEDBACK_MAX_CHARS), 9000)),
        "last_assistant_message_classifier_enabled": coerce_bool(data.get(SETTING_CLASSIFIER_ENABLED), True),
        "last_assistant_message_classifier_timeout_seconds": coerce_float(data.get(SETTING_CLASSIFIER_TIMEOUT), DEFAULT_TIMEOUT_SECONDS),
        "classifier_model": str(data.get(SETTING_CLASSIFIER_MODEL, DEFAULT_CLASSIFIER_MODEL)),
        "stale_client_timeout_hours": coerce_float(data.get(SETTING_STALE_CLIENT_TIMEOUT), 48),
        "debug": coerce_bool(data.get(SETTING_DEBUG), True),
        "extras": extras,
    }


def plugin_settings_mapping(settings) -> dict[str, Any]:
    backend = resolve_reviewer_backend(settings.reviewer_backend)
    return {
        SETTING_ENABLED: settings.enabled,
        SETTING_RULES_FILE: settings.rules_file,
        SETTING_INCLUDE_EXTS: list(settings.include_extensions),
        SETTING_SKIP_EXTS: list(settings.skip_extensions),
        SETTING_REVIEWER_BACKEND: settings.reviewer_backend,
        SETTING_REVIEWER_MODEL: settings.reviewer_model or resolve_reviewer_model(settings.reviewer_model, backend=backend),
        SETTING_REVIEWER_TIMEOUT: settings.reviewer_timeout_seconds,
        SETTING_FEEDBACK_MAX_CHARS: settings.review_feedback_max_chars,
        SETTING_MAX_STOP_PASSES: settings.max_stop_passes,
        SETTING_MINIMUM_BLOCKING_SEVERITY: settings.minimum_blocking_severity,
        SETTING_PENDING_TIMEOUT: settings.pending_review_timeout_hours,
        SETTING_CLASSIFIER_ENABLED: settings.last_assistant_message_classifier_enabled,
        SETTING_CLASSIFIER_MODEL: settings.classifier_model,
        SETTING_CLASSIFIER_TIMEOUT: settings.last_assistant_message_classifier_timeout_seconds,
        SETTING_STALE_CLIENT_TIMEOUT: settings.stale_client_timeout_hours,
        SETTING_DEBUG: settings.debug,
        **settings.extras,
    }
