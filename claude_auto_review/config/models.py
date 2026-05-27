from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from claude_auto_review.config.reviewer import (
    DEFAULT_CLAUDE_REVIEWER_MODEL,
    DEFAULT_CODEX_REVIEWER_MODEL,
    DEFAULT_REVIEWER_BACKEND,
    DEFAULT_REVIEWER_MODEL,
    DEFAULT_REVIEWER_MODELS,
    REVIEWER_BACKENDS,
    resolve_reviewer_backend,
    resolve_reviewer_model,
)
from claude_auto_review.config.serialization import (
    DEFAULT_CLASSIFIER_MODEL,
    DEFAULT_TIMEOUT_SECONDS,
    plugin_settings_kwargs,
    plugin_settings_mapping,
)
from claude_auto_review.config.severity import (
    DEFAULT_MINIMUM_BLOCKING_SEVERITY,
    MINIMUM_BLOCKING_SEVERITIES,
    coerce_minimum_blocking_severity,
)
from claude_auto_review.config.utils.schema import DEFAULT_RULES_FILE


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
        return cls(**plugin_settings_kwargs(mapping))

    def to_mapping(self) -> dict[str, Any]:
        return plugin_settings_mapping(self)

    def resolved_reviewer_backend(self) -> str:
        return resolve_reviewer_backend(self.reviewer_backend)

    def resolved_reviewer_model(self, *, backend: str | None = None) -> str:
        return resolve_reviewer_model(self.reviewer_model, backend=backend or self.resolved_reviewer_backend())
