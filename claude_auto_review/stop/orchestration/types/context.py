from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from claude_auto_review.config.settings.models import PluginSettings
from claude_auto_review.stop.orchestration.types.resolution import StopDecisionKind
from claude_auto_review.stop.reviews.types.enums import StopAllowReason


@dataclass(frozen=True)
class RuntimeContext:
    project_root: Path
    client_id: str
    settings: PluginSettings = field(default_factory=PluginSettings)
    payload: Any = field(default_factory=dict)


@dataclass(frozen=True)
class TerminalDetails:
    exit_code: int = 2


@dataclass(frozen=True)
class FinalizeDetails:
    resolution: Any


@dataclass(frozen=True)
class CircuitBreakerDetails:
    block_count: int
    max_passes: int


@dataclass(frozen=True)
class ClassifierDetails:
    classifier_status: Any
    classifier_reason: Any


StopDetails = TerminalDetails | FinalizeDetails | CircuitBreakerDetails | ClassifierDetails


@dataclass(frozen=True)
class StopDecision:
    kind: StopDecisionKind
    reason: StopAllowReason | None = None
    details: StopDetails | None = None


@dataclass(frozen=True)
class ResponsePayload:
    system_message: str
    feedback: str | None = None
