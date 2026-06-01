from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from claude_auto_review.config.reviewer.backends import (
    DEFAULT_CLAUDE_REVIEWER_MODEL as DEFAULT_CLAUDE_REVIEWER_MODEL,
    DEFAULT_CODEX_REVIEWER_MODEL as DEFAULT_CODEX_REVIEWER_MODEL,
    DEFAULT_OPENCODE_REVIEWER_MODEL as DEFAULT_OPENCODE_REVIEWER_MODEL,
    DEFAULT_REVIEWER_BACKEND as DEFAULT_REVIEWER_BACKEND,
    DEFAULT_REVIEWER_MODEL as DEFAULT_REVIEWER_MODEL,
    DEFAULT_REVIEWER_MODELS as DEFAULT_REVIEWER_MODELS,
    REVIEWER_BACKENDS as REVIEWER_BACKENDS,
    resolve_reviewer_backend,
    resolve_reviewer_model,
)

__all__ = [
    "PluginSettings",
    "DEFAULT_CLAUDE_REVIEWER_MODEL",
    "DEFAULT_CODEX_REVIEWER_MODEL",
    "DEFAULT_OPENCODE_REVIEWER_MODEL",
    "DEFAULT_REVIEWER_BACKEND",
    "DEFAULT_REVIEWER_MODEL",
    "DEFAULT_REVIEWER_MODELS",
    "REVIEWER_BACKENDS",
    "resolve_reviewer_backend",
    "resolve_reviewer_model",
]
from claude_auto_review.config.settings.serialization import (
    DEFAULT_CLASSIFIER_MODEL,
    DEFAULT_TIMEOUT_SECONDS,
    plugin_settings_kwargs,
    plugin_settings_mapping,
)
from claude_auto_review.config.constants.severity import (
    DEFAULT_MINIMUM_BLOCKING_SEVERITY,
)
from claude_auto_review.config.constants.defaults import DEFAULT_RULES_FILE


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
    def from_mapping(cls, mapping: Mapping[str, Any] | None) -> PluginSettings:
        return cls(**plugin_settings_kwargs(mapping))

    def to_mapping(self) -> dict[str, Any]:
        return plugin_settings_mapping(self)

    def resolved_reviewer_backend(self) -> str:
        return resolve_reviewer_backend(self.reviewer_backend)

    def resolved_reviewer_model(self, *, backend: str | None = None) -> str:
        return resolve_reviewer_model(self.reviewer_model, backend=backend or self.resolved_reviewer_backend())
