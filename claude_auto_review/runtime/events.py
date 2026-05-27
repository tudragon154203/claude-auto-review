from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from claude_auto_review.paths.path_utils import get_state_path, local_now_iso
from claude_auto_review.runtime.client_dirs import get_existing_client_runtime_dir
from claude_auto_review.runtime.context import resolve_project_root
from claude_auto_review.state.store.write import write_jsonl_line


def _json_safe(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Exception):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, set):
        return sorted((_json_safe(item) for item in value), key=repr)
    return value


@dataclass(frozen=True)
class EventSink:
    project_root: Path

    @classmethod
    def for_project(cls, project_root: str | Path) -> EventSink:
        return cls(project_root=resolve_project_root(project_root))

    def build_entry(self, event_type: str, client_id: str | None = None, **kwargs: Any) -> dict[str, Any]:
        entry: dict[str, Any] = {"timestamp": local_now_iso(), "type": event_type}
        if client_id:
            entry["clientId"] = client_id
        entry.update(_json_safe(kwargs))
        return entry

    def write_entry(self, entry: dict[str, Any], *, client_id: str | None = None) -> bool:
        global_path = get_state_path(self.project_root)
        if client_id:
            client_dir = get_existing_client_runtime_dir(self.project_root, client_id)
            if client_dir is not None:
                write_jsonl_line(client_dir / "state.jsonl", entry)
        write_jsonl_line(global_path, entry)
        return True

    def log(self, event_type: str, *, client_id: str | None = None, **kwargs: Any) -> bool:
        try:
            return self.write_entry(self.build_entry(event_type, client_id=client_id, **kwargs), client_id=client_id)
        except OSError:
            return False


def log_event(project_root: str | Path, event_type: str, client_id: str | None = None, **kwargs: Any) -> bool:
    return EventSink.for_project(project_root).log(event_type, client_id=client_id, **kwargs)


def log_failure(project_root: str | Path, event_type: str, error: Exception | str, client_id: str | None = None, **kwargs: Any) -> bool:
    return log_event(project_root, event_type, client_id=client_id, error=str(error), **kwargs)
