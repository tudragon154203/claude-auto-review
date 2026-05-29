from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from claude_auto_review.state.models import EditRecord, FileHash, StateEvent
from claude_auto_review.state.snapshot import StateSnapshot
from claude_auto_review.state.store.queries import consecutive_stop_blocks, get_unreviewed_files
from claude_auto_review.state.store.read import load_state_snapshot
from claude_auto_review.state.store.write import append_review_started, append_state_event, mark_files_reviewed


@dataclass(frozen=True)
class StateTracker:
    """Own state loading, mutations, and derived queries for one client session."""

    project_root: Path
    client_id: str

    def load(self) -> StateSnapshot:
        return load_state_snapshot(self.project_root, self.client_id)

    def record_event(self, event: StateEvent) -> None:
        append_state_event(event, self.project_root, client_id=self.client_id)

    def track_edit(self, entry: EditRecord) -> None:
        self.record_event(entry)

    def track_review_started(self, entries: list[EditRecord], review_id: str, review_path: str) -> None:
        append_review_started(entries, review_id, review_path, self.project_root, client_id=self.client_id)

    def mark_reviewed(self, entries: list[EditRecord], review_id: str, *, timestamp: str | None = None) -> None:
        mark_files_reviewed(entries, review_id, self.project_root, client_id=self.client_id, timestamp=timestamp)

    def get_unreviewed(self) -> list[EditRecord]:
        return get_unreviewed_files(self.load())

    def get_consecutive_blocks(self) -> int:
        return consecutive_stop_blocks(self.load())

    @staticmethod
    def file_hash(value: str) -> FileHash:
        return FileHash(value)
