"""High-level state facade for a single client session.

`StateTracker` composes an injectable `StateRepository` rather than reaching
into concrete modules directly, satisfying DIP. Callers can swap in a
fake repository for tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol, runtime_checkable

from claude_auto_review.state.records.edit import EditRecord
from claude_auto_review.state.records.events import StateEvent
from claude_auto_review.state.records.models import FileHash
from claude_auto_review.state.snapshots.snapshot import StateSnapshot
from claude_auto_review.state.store.queries import consecutive_stop_blocks, get_unreviewed_files
from claude_auto_review.state.store.read import load_state_snapshot
from claude_auto_review.state.store.write import append_review_started, append_state_event, mark_files_reviewed


@runtime_checkable
class StateRepository(Protocol):
    """Abstraction over state storage for DIP-friendly injection."""

    def load_snapshot(self, project_root: Path, client_id: str) -> StateSnapshot: ...
    def append_event(self, event: StateEvent, project_root: Path, client_id: str) -> None: ...
    def append_review_started(
        self,
        entries: list[EditRecord],
        review_id: str,
        review_path: str,
        project_root: Path,
        client_id: str,
    ) -> None: ...
    def mark_files_reviewed(
        self,
        entries: list[EditRecord],
        review_id: str,
        project_root: Path,
        client_id: str,
        *,
        timestamp: str | None = None,
    ) -> None: ...
    def unreviewed_files(self, snapshot: StateSnapshot) -> list[EditRecord]: ...
    def consecutive_stop_blocks(self, snapshot: StateSnapshot) -> int: ...


@dataclass(frozen=True)
class _DefaultStateRepository:
    """Default repository backed by the production JSONL store."""

    def load_snapshot(self, project_root: Path, client_id: str) -> StateSnapshot:
        return load_state_snapshot(project_root, client_id)

    def append_event(self, event: StateEvent, project_root: Path, client_id: str) -> None:
        append_state_event(event, project_root, client_id=client_id)

    def append_review_started(
        self,
        entries: list[EditRecord],
        review_id: str,
        review_path: str,
        project_root: Path,
        client_id: str,
    ) -> None:
        append_review_started(entries, review_id, review_path, project_root, client_id=client_id)

    def mark_files_reviewed(
        self,
        entries: list[EditRecord],
        review_id: str,
        project_root: Path,
        client_id: str,
        *,
        timestamp: str | None = None,
    ) -> None:
        mark_files_reviewed(entries, review_id, project_root, client_id=client_id, timestamp=timestamp)

    def unreviewed_files(self, snapshot: StateSnapshot) -> list[EditRecord]:
        return get_unreviewed_files(snapshot)

    def consecutive_stop_blocks(self, snapshot: StateSnapshot) -> int:
        return consecutive_stop_blocks(snapshot)


DEFAULT_REPOSITORY: StateRepository = _DefaultStateRepository()


@dataclass(frozen=True)
class StateTracker:
    """Own state loading, mutations, and derived queries for one client session."""

    project_root: Path
    client_id: str
    repository: StateRepository = DEFAULT_REPOSITORY

    def load(self) -> StateSnapshot:
        return self.repository.load_snapshot(self.project_root, self.client_id)

    def record_event(self, event: StateEvent) -> None:
        self.repository.append_event(event, self.project_root, self.client_id)

    def track_edit(self, entry: EditRecord) -> None:
        self.record_event(entry)

    def track_review_started(self, entries: list[EditRecord], review_id: str, review_path: str) -> None:
        self.repository.append_review_started(entries, review_id, review_path, self.project_root, self.client_id)

    def mark_reviewed(self, entries: list[EditRecord], review_id: str, *, timestamp: str | None = None) -> None:
        self.repository.mark_files_reviewed(
            entries, review_id, self.project_root, self.client_id, timestamp=timestamp
        )

    def get_unreviewed(self) -> list[EditRecord]:
        return self.repository.unreviewed_files(self.load())

    def get_consecutive_blocks(self) -> int:
        return self.repository.consecutive_stop_blocks(self.load())

    @staticmethod
    def file_hash(value: str) -> FileHash:
        return FileHash(value)
