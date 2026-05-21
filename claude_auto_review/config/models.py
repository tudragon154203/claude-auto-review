from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from claude_auto_review.config.utils.coercion import (
    coerce_bool,
    coerce_extensions,
    coerce_float,
    coerce_int,
)
from claude_auto_review.config.utils.schema import (
    DEFAULT_RULES_FILE,
    KNOWN_SETTING_KEYS,
    SETTING_CLASSIFIER_ENABLED,
    SETTING_CLASSIFIER_MODEL,
    SETTING_CLASSIFIER_TIMEOUT,
    SETTING_DEBUG,
    SETTING_ENABLED,
    SETTING_FEEDBACK_MAX_CHARS,
    SETTING_MINIMUM_BLOCKING_SEVERITY,
    SETTING_INCLUDE_EXTS,
    SETTING_MAX_STOP_PASSES,
    SETTING_PENDING_TIMEOUT,
    SETTING_REVIEWER_BACKEND,
    SETTING_REVIEWER_MODEL,
    SETTING_REVIEWER_TIMEOUT,
    SETTING_RULES_FILE,
    SETTING_SKIP_EXTS,
    SETTING_STALE_CLIENT_TIMEOUT,
)

DEFAULT_CLASSIFIER_MODEL = "claude-haiku-4-5"

DEFAULT_REVIEWER_BACKEND = "claude"
DEFAULT_MINIMUM_BLOCKING_SEVERITY = "medium"
MINIMUM_BLOCKING_SEVERITIES = frozenset({"info", "low", "medium", "high", "critical"})

# API names for reviewer models, keyed by backend
DEFAULT_CLAUDE_REVIEWER_MODEL = "claude-sonnet-4-6"
DEFAULT_CODEX_REVIEWER_MODEL = "gpt-5.3-codex"
DEFAULT_REVIEWER_MODELS = {
    "claude": DEFAULT_CLAUDE_REVIEWER_MODEL,
    "codex": DEFAULT_CODEX_REVIEWER_MODEL,
}
DEFAULT_REVIEWER_MODEL = DEFAULT_REVIEWER_MODELS[DEFAULT_REVIEWER_BACKEND]

# Time in seconds to wait for hook
DEFAULT_TIMEOUT_SECONDS = 20

REVIEWER_BACKENDS = frozenset(DEFAULT_REVIEWER_MODELS)


def coerce_minimum_blocking_severity(value: Any) -> str:
    if value is None:
        return DEFAULT_MINIMUM_BLOCKING_SEVERITY
    severity = str(value).strip().lower()
    if severity in MINIMUM_BLOCKING_SEVERITIES:
        return severity
    return DEFAULT_MINIMUM_BLOCKING_SEVERITY


@dataclass(frozen=True)
class PluginSettings:
    enabled: bool = True
    rules_file: str = DEFAULT_RULES_FILE
    include_extensions: tuple[str, ...] = ()
    skip_extensions: tuple[str, ...] = ()
    max_stop_passes: int = 5
    minimum_blocking_severity: str = DEFAULT_MINIMUM_BLOCKING_SEVERITY
    pending_review_timeout_hours: float = 1
    reviewer_backend: str = DEFAULT_REVIEWER_BACKEND
    reviewer_model: str | None = None
    reviewer_timeout_seconds: int = 600
    review_feedback_max_chars: int = 9000
    last_assistant_message_classifier_enabled: bool = True
    last_assistant_message_classifier_timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    classifier_model: str = DEFAULT_CLASSIFIER_MODEL
    stale_client_timeout_hours: float = 48
    debug: bool = True
    extras: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any] | None) -> "PluginSettings":
        data = dict(mapping) if isinstance(mapping, Mapping) else {}
        extras = {key: value for key, value in data.items() if key not in KNOWN_SETTING_KEYS}
        reviewer_model = data.get(SETTING_REVIEWER_MODEL)
        return cls(
            enabled=coerce_bool(data.get(SETTING_ENABLED), True),
            rules_file=str(data.get(SETTING_RULES_FILE, DEFAULT_RULES_FILE)),
            include_extensions=coerce_extensions(data.get(SETTING_INCLUDE_EXTS)),
            skip_extensions=coerce_extensions(data.get(SETTING_SKIP_EXTS)),
            max_stop_passes=coerce_int(data.get(SETTING_MAX_STOP_PASSES), 5),
            minimum_blocking_severity=coerce_minimum_blocking_severity(
                data.get(SETTING_MINIMUM_BLOCKING_SEVERITY)
            ),
            pending_review_timeout_hours=coerce_float(data.get(SETTING_PENDING_TIMEOUT), 1),
            reviewer_backend=str(data.get(SETTING_REVIEWER_BACKEND, DEFAULT_REVIEWER_BACKEND)).lower(),
            reviewer_model=None if reviewer_model in (None, "") else str(reviewer_model),
            reviewer_timeout_seconds=coerce_int(data.get(SETTING_REVIEWER_TIMEOUT), 600),
            review_feedback_max_chars=max(0, coerce_int(data.get(SETTING_FEEDBACK_MAX_CHARS), 9000)),
            last_assistant_message_classifier_enabled=coerce_bool(
                data.get(SETTING_CLASSIFIER_ENABLED),
                True,
            ),
            last_assistant_message_classifier_timeout_seconds=coerce_float(
                data.get(SETTING_CLASSIFIER_TIMEOUT),
                DEFAULT_TIMEOUT_SECONDS,
            ),
            classifier_model=str(data.get(SETTING_CLASSIFIER_MODEL, DEFAULT_CLASSIFIER_MODEL)),
            stale_client_timeout_hours=coerce_float(data.get(SETTING_STALE_CLIENT_TIMEOUT), 48),
            debug=coerce_bool(data.get(SETTING_DEBUG), True),
            extras=extras,
        )

    def to_mapping(self) -> dict[str, Any]:
        mapping = {
            SETTING_ENABLED: self.enabled,
            SETTING_RULES_FILE: self.rules_file,
            SETTING_INCLUDE_EXTS: list(self.include_extensions),
            SETTING_SKIP_EXTS: list(self.skip_extensions),
            SETTING_MAX_STOP_PASSES: self.max_stop_passes,
            SETTING_MINIMUM_BLOCKING_SEVERITY: self.minimum_blocking_severity,
            SETTING_PENDING_TIMEOUT: self.pending_review_timeout_hours,
            SETTING_REVIEWER_BACKEND: self.reviewer_backend,
            SETTING_REVIEWER_TIMEOUT: self.reviewer_timeout_seconds,
            SETTING_FEEDBACK_MAX_CHARS: self.review_feedback_max_chars,
            SETTING_CLASSIFIER_ENABLED: self.last_assistant_message_classifier_enabled,
            SETTING_CLASSIFIER_TIMEOUT: self.last_assistant_message_classifier_timeout_seconds,
            SETTING_CLASSIFIER_MODEL: self.classifier_model,
            SETTING_STALE_CLIENT_TIMEOUT: self.stale_client_timeout_hours,
            SETTING_DEBUG: self.debug,
        }
        if self.reviewer_model is not None:
            mapping[SETTING_REVIEWER_MODEL] = self.reviewer_model
        mapping.update(self.extras)
        return mapping

    def resolved_reviewer_backend(self) -> str:
        if self.reviewer_backend not in REVIEWER_BACKENDS:
            raise ValueError(f"Unsupported reviewer backend: {self.reviewer_backend}")
        return self.reviewer_backend

    def resolved_reviewer_model(self, *, backend: str | None = None) -> str:
        if self.reviewer_model is not None:
            return self.reviewer_model
        resolved_backend = backend or self.resolved_reviewer_backend()
        return DEFAULT_REVIEWER_MODELS.get(resolved_backend, DEFAULT_REVIEWER_MODEL)
