from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from claude_auto_review.runtime.context import resolve_client_id, resolve_project_root
from claude_auto_review.state.records.edit import EditRecord
from claude_auto_review.state.records.events import StateEvent
from claude_auto_review.state.store.write import append_review_started, append_state_event, mark_files_reviewed


@dataclass(frozen=True)
class StateRepository:
    """Write-only facade for a single client's JSONL state file."""

    project_root: Path
    client_id: str

    @classmethod
    def for_client(cls, project_root=None, client_id=None) -> StateRepository:
        return cls(
            project_root=resolve_project_root(project_root),
            client_id=resolve_client_id(client_id),
        )

    def append_event(self, event: StateEvent) -> None:
        append_state_event(event, self.project_root, client_id=self.client_id)

    def append_review_started(self, entries: list[EditRecord], review_id: str, review_path: str) -> None:
        append_review_started(entries, review_id, review_path, self.project_root, client_id=self.client_id)

    def mark_files_reviewed(self, entries: list[EditRecord], review_id: str, *, timestamp=None) -> None:
        mark_files_reviewed(entries, review_id, self.project_root, client_id=self.client_id, timestamp=timestamp)


__all__ = ["StateRepository"]

