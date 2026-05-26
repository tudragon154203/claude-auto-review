from dataclasses import dataclass

from pathlib import Path
import json

from claude_auto_review.paths.path_utils import local_now_iso
from claude_auto_review.runtime.client_dirs import client_state_path
from claude_auto_review.runtime.setup import ensure_client_runtime
from claude_auto_review.state.models import EditRecord, ReviewMetadata, StateEvent


@dataclass(frozen=True)
class StateEventWriter:
    project_root: object
    client_id: str

    def append(self, event: StateEvent):
        ensure_client_runtime(self.project_root, self.client_id)
        state_file = client_state_path(self.project_root, self.client_id)
        state_file = Path(state_file)
        state_file.parent.mkdir(parents=True, exist_ok=True)
        with state_file.open("a", encoding="utf-8", newline="\n") as file_handle:
            file_handle.write(json.dumps(event.to_dict(), separators=(",", ":"), default=str) + "\n")

    def append_review_started(self, entries: list[EditRecord], review_id: str, review_path: str):
        self.append(
            ReviewMetadata(
                timestamp=local_now_iso(),
                reviewId=review_id,
                reviewPath=review_path,
                files=[],
                clientId=self.client_id,
            )
        )

    def append_marked_reviewed(self, entries: list[EditRecord], review_id: str, timestamp: str):
        for entry in entries:
            self.append(
                EditRecord(
                    timestamp=timestamp,
                    file=entry.file,
                    hash=entry.hash,
                    reviewed=True,
                    reviewId=review_id,
                )
            )
