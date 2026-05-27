from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from claude_auto_review.config.models import PluginSettings
from claude_auto_review.stop.orchestration.resolution import StopDecisionKind


@dataclass(frozen=True)
class RuntimeContext:
    project_root: Path
    client_id: str
    settings: PluginSettings = field(default_factory=PluginSettings)
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class StopDecision:
    kind: StopDecisionKind
    reason: str | None = None
    details: dict[str, Any] | None = None


@dataclass(frozen=True)
class ResponsePayload:
    system_message: str
    feedback: str | None = None
