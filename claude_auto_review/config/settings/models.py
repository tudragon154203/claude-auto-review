from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from claude_auto_review.config.constants.severity import DEFAULT_MINIMUM_BLOCKING_SEVERITY
from claude_auto_review.config.constants.defaults import DEFAULT_RULES_FILE
from claude_auto_review.config.reviewer.backends import DEFAULT_REVIEWER_BACKEND
from claude_auto_review.config.constants.defaults import (
    DEFAULT_CLASSIFIER_MODEL,
    DEFAULT_TIMEOUT_SECONDS,
)
from claude_auto_review.config.settings.serialization import (
    plugin_settings_kwargs,
    plugin_settings_mapping,
)


@dataclass(frozen=True)
class CoreSettings:
    enabled: bool = True
    debug: bool = True


@dataclass(frozen=True)
class ReviewerSettings:
    reviewer_backend: str = DEFAULT_REVIEWER_BACKEND
    reviewer_model: str | None = None
    reviewer_timeout_seconds: int = 600
    review_feedback_max_chars: int = 9000


@dataclass(frozen=True)
class ClassifierSettings:
    last_assistant_message_classifier_enabled: bool = True
    last_assistant_message_classifier_timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    classifier_model: str = DEFAULT_CLASSIFIER_MODEL


@dataclass(frozen=True)
class FilterSettings:
    rules_file: str = DEFAULT_RULES_FILE
    include_extensions: tuple[str, ...] = ()
    skip_extensions: tuple[str, ...] = ()


@dataclass(frozen=True)
class FlowSettings:
    max_stop_passes: int = 5
    minimum_blocking_severity: str = DEFAULT_MINIMUM_BLOCKING_SEVERITY
    pending_review_timeout_hours: float = 1
    stale_client_timeout_hours: float = 48


@dataclass(frozen=True)
class PluginSettings:
    core: CoreSettings = field(default_factory=CoreSettings)
    reviewer: ReviewerSettings = field(default_factory=ReviewerSettings)
    classifier: ClassifierSettings = field(default_factory=ClassifierSettings)
    filters: FilterSettings = field(default_factory=FilterSettings)
    flow: FlowSettings = field(default_factory=FlowSettings)
    extras: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any] | None) -> PluginSettings:
        return cls(**plugin_settings_kwargs(mapping))

    def to_mapping(self) -> dict[str, Any]:
        return plugin_settings_mapping(self)
