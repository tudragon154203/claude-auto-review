from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from claude_auto_review.paths.path_utils import get_state_path, local_now_iso
from claude_auto_review.runtime.client_dirs import get_existing_client_runtime_dir
from claude_auto_review.runtime.context import resolve_project_root
from claude_auto_review.runtime.serialization import json_safe
from claude_auto_review.state.store.write import write_jsonl_line


@dataclass(frozen=True)
class EntryBuilder:
    project_root: Path

    @classmethod
    def for_project(cls, project_root: str | Path) -> EntryBuilder:
        return cls(project_root=resolve_project_root(project_root))

    def build(self, event_type: str, client_id: str | None = None, **kwargs: Any) -> dict[str, Any]:
        entry: dict[str, Any] = {"timestamp": local_now_iso(), "type": event_type}
        if client_id:
            entry["clientId"] = client_id
        entry.update(json_safe(kwargs))
        return entry


@dataclass(frozen=True)
class EntryWriter:
    project_root: Path

    @classmethod
    def for_project(cls, project_root: str | Path) -> EntryWriter:
        return cls(project_root=resolve_project_root(project_root))

    def write(self, entry: dict[str, Any], *, client_id: str | None = None) -> bool:
        global_path = get_state_path(self.project_root)
        if client_id:
            client_dir = get_existing_client_runtime_dir(self.project_root, client_id)
            if client_dir is not None:
                write_jsonl_line(client_dir / "state.jsonl", entry)
        write_jsonl_line(global_path, entry)
        return True


@dataclass(frozen=True)
class EventSink:
    project_root: Path

    @classmethod
    def for_project(cls, project_root: str | Path) -> EventSink:
        return cls(project_root=resolve_project_root(project_root))

    def build_entry(self, event_type: str, client_id: str | None = None, **kwargs: Any) -> dict[str, Any]:
        return EntryBuilder(project_root=self.project_root).build(event_type, client_id=client_id, **kwargs)

    def write_entry(self, entry: dict[str, Any], *, client_id: str | None = None) -> bool:
        return EntryWriter(project_root=self.project_root).write(entry, client_id=client_id)

    def log(self, event_type: str, *, client_id: str | None = None, **kwargs: Any) -> bool:
        try:
            entry = EntryBuilder(project_root=self.project_root).build(event_type, client_id=client_id, **kwargs)
            return EntryWriter(project_root=self.project_root).write(entry, client_id=client_id)
        except OSError:
            return False


@dataclass(frozen=True)
class EventLogger:
    """Lightweight interface for callers that only need to log events."""
    project_root: Path

    @classmethod
    def for_project(cls, project_root: str | Path) -> EventLogger:
        return cls(project_root=resolve_project_root(project_root))

    def log(self, event_type: str, *, client_id: str | None = None, **kwargs: Any) -> bool:
        try:
            entry = EntryBuilder(project_root=self.project_root).build(event_type, client_id=client_id, **kwargs)
            return EntryWriter(project_root=self.project_root).write(entry, client_id=client_id)
        except OSError:
            return False


def log_event(project_root: str | Path, event_type: str, client_id: str | None = None, **kwargs: Any) -> bool:
    return EventLogger.for_project(project_root).log(event_type, client_id=client_id, **kwargs)


def log_failure(
    project_root: str | Path, event_type: str, error: Exception | str, client_id: str | None = None, **kwargs: Any
) -> bool:
    return log_event(project_root, event_type, client_id=client_id, error=str(error), **kwargs)
