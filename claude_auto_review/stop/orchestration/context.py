from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from claude_auto_review.config.models import PluginSettings


@dataclass(frozen=True)
class RuntimeContext:
    project_root: Path
    client_id: str
    settings: PluginSettings = field(default_factory=PluginSettings)
    payload: dict[str, Any] = field(default_factory=dict)
