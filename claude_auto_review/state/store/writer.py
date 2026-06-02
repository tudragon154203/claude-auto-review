"""Thin typed wrappers satisfying StateEventWriterProtocol.

Provides focused interfaces for state event writing and review marking,
plus a composite StateEventWriter for backward compatibility.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from claude_auto_review.runtime.context import resolve_client_id, resolve_project_root
from claude_auto_review.state.records.edit import EditRecord
from claude_auto_review.state.records.events import StateEvent
from claude_auto_review.state.store.write import (
    append_review_started,
    append_state_event,
    mark_files_reviewed,
)


@dataclass(frozen=True)
class StateAppender:
    """Write-only facade for appending arbitrary state events."""

    project_root: Path
    client_id: str

    @classmethod
    def for_client(cls, project_root=None, client_id=None) -> StateAppender:
        return cls(
            project_root=resolve_project_root(project_root),
            client_id=resolve_client_id(client_id),
        )

    def append(self, event: StateEvent) -> None:
        append_state_event(event, self.project_root, client_id=self.client_id)


@dataclass(frozen=True)
class ReviewMarker:
    """Write-only facade for review-lifecycle state transitions."""

    project_root: Path
    client_id: str

    @classmethod
    def for_client(cls, project_root=None, client_id=None) -> ReviewMarker:
        return cls(
            project_root=resolve_project_root(project_root),
            client_id=resolve_client_id(client_id),
        )

    def append_review_started(self, entries: list[EditRecord], review_id: str, review_path: str) -> None:
        append_review_started(entries, review_id, review_path, self.project_root, client_id=self.client_id)

    def append_marked_reviewed(self, entries: list[EditRecord], review_id: str, timestamp: str) -> None:
        mark_files_reviewed(entries, review_id, self.project_root, client_id=self.client_id, timestamp=timestamp)


@dataclass(frozen=True)
class StateEventWriter:
    """Composite facade combining StateAppender and ReviewMarker for backward compatibility."""

    project_root: Path
    client_id: str

    @classmethod
    def for_client(cls, project_root=None, client_id=None) -> StateEventWriter:
        return cls(
            project_root=resolve_project_root(project_root),
            client_id=resolve_client_id(client_id),
        )

    def append(self, event: StateEvent) -> None:
        append_state_event(event, self.project_root, client_id=self.client_id)

    def append_review_started(self, entries: list[EditRecord], review_id: str, review_path: str) -> None:
        append_review_started(entries, review_id, review_path, self.project_root, client_id=self.client_id)

    def append_marked_reviewed(self, entries: list[EditRecord], review_id: str, timestamp: str) -> None:
        mark_files_reviewed(entries, review_id, self.project_root, client_id=self.client_id, timestamp=timestamp)
