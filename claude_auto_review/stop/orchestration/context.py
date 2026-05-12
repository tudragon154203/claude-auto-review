from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

@dataclass(frozen=True)
class StopContext:
    project_root: Path
    client_id: str
    settings: Dict[str, Any]
    payload: Dict[str, Any]
    state: List[Dict[str, Any]]
    log_file: Optional[Path] = None
