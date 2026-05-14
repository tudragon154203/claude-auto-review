from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RuntimeContext:
    project_root: Path
    client_id: str
    settings: dict[str, Any] = field(default_factory=dict)
    payload: dict[str, Any] = field(default_factory=dict)