from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from claude_auto_review.paths.path_utils import get_state_path
from claude_auto_review.timestamps import local_now_iso
from claude_auto_review.runtime.client_dirs import get_existing_client_runtime_dir
from claude_auto_review.runtime.context import resolve_project_root
from claude_auto_review.runtime.serialization import json_safe
from claude_auto_review.state.store.write import write_jsonl_line


class _EntrySink(Protocol):
    """Protocol for composable entry-writing destinations."""

    def write(self, entry: dict[str, Any], *, client_id: str | None = None) -> None: ...


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
class _StateFileSink:
    """Writes entries to the global state.jsonl."""

    project_root: Path

    def write(self, entry: dict[str, Any], *, client_id: str | None = None) -> None:
        write_jsonl_line(get_state_path(self.project_root), entry)


@dataclass(frozen=True)
class _ClientStateSink:
    """Writes entries to a per-client state.jsonl when that client is present."""

    project_root: Path

    def write(self, entry: dict[str, Any], *, client_id: str | None = None) -> None:
        if not client_id:
            return
        client_dir = get_existing_client_runtime_dir(self.project_root, client_id)
        if client_dir is None:
            return
        write_jsonl_line(client_dir / "state.jsonl", entry)


@dataclass(frozen=True)
class EntryWriter:
    """Composite writer: global state.jsonl + per-client state.jsonl (when present)."""

    project_root: Path

    @classmethod
    def for_project(cls, project_root: str | Path) -> EntryWriter:
        return cls(project_root=resolve_project_root(project_root))

    def write(self, entry: dict[str, Any], *, client_id: str | None = None) -> bool:
        for sink in (self._state_sink(), self._client_sink()):
            sink.write(entry, client_id=client_id)
        return True

    def _state_sink(self) -> _EntrySink:
        return _StateFileSink(project_root=self.project_root)

    def _client_sink(self) -> _EntrySink:
        return _ClientStateSink(project_root=self.project_root)


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
            entry = self.build_entry(event_type, client_id=client_id, **kwargs)
            return self.write_entry(entry, client_id=client_id)
        except OSError:
            return False


@dataclass(frozen=True)
class EventLogger:
    """Lightweight interface for callers that only need to log events.

    Delegates to EventSink to avoid duplicating the build/write pipeline.
    """

    project_root: Path

    @classmethod
    def for_project(cls, project_root: str | Path) -> EventLogger:
        return cls(project_root=resolve_project_root(project_root))

    def log(self, event_type: str, *, client_id: str | None = None, **kwargs: Any) -> bool:
        return EventSink(project_root=self.project_root).log(event_type, client_id=client_id, **kwargs)


def log_event(project_root: str | Path, event_type: str, client_id: str | None = None, **kwargs: Any) -> bool:
    return EventLogger.for_project(project_root).log(event_type, client_id=client_id, **kwargs)


def log_failure(
    project_root: str | Path, event_type: str, error: Exception | str, client_id: str | None = None, **kwargs: Any
) -> bool:
    return log_event(project_root, event_type, client_id=client_id, error=str(error), **kwargs)
