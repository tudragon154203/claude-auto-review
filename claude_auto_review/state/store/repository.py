from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from claude_auto_review.runtime.context import resolve_client_id, resolve_project_root
from claude_auto_review.state.models import EditRecord, StateEvent
from claude_auto_review.state.snapshot import StateSnapshot
from claude_auto_review.state.store.read import (
    get_file_hash,
    read_jsonl_records,
    read_jsonl_state_records,
    read_last_jsonl_record,
)
from claude_auto_review.state.store.write import append_review_started, append_state_event, mark_files_reviewed


@dataclass(frozen=True)
class StateRepository:
    """Read/write facade for a single client's JSONL state file."""

    project_root: Path
    client_id: str

    @classmethod
    def for_client(cls, project_root=None, client_id=None) -> StateRepository:
        return cls(
            project_root=resolve_project_root(project_root),
            client_id=resolve_client_id(client_id),
        )

    def load_snapshot(self) -> StateSnapshot:
        from claude_auto_review.runtime.client_dirs import client_state_path

        state_file = client_state_path(self.project_root, self.client_id)
        events = [record.event for record in read_jsonl_state_records(state_file) if record.event is not None]
        return StateSnapshot.from_events(events)

    def load_events(self) -> list[StateEvent]:
        return list(self.load_snapshot().events)

    def append_event(self, event: StateEvent) -> None:
        append_state_event(event, self.project_root, client_id=self.client_id)

    def append_review_started(self, entries: list[EditRecord], review_id: str, review_path: str) -> None:
        append_review_started(entries, review_id, review_path, self.project_root, client_id=self.client_id)

    def mark_files_reviewed(self, entries: list[EditRecord], review_id: str, *, timestamp=None) -> None:
        mark_files_reviewed(entries, review_id, self.project_root, client_id=self.client_id, timestamp=timestamp)

    def get_file_hash(self, file_path: str) -> str | None:
        return get_file_hash(file_path, self.project_root)


__all__ = [
    "StateRepository",
    "read_jsonl_records",
    "read_last_jsonl_record",
    "read_jsonl_state_records",
]
