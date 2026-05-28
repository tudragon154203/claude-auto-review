from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from claude_auto_review.state.record_utils import dict_with_optional


@dataclass(frozen=True)
class EditRecord:
    """Tracks a single file edit event with its content hash."""

    timestamp: str
    file: str
    hash: str
    reviewed: bool = False
    deleted: bool = False
    reviewId: str | None = None
    type: Literal["edit"] = "edit"

    def to_dict(self) -> dict[str, Any]:
        return dict_with_optional(
            {
                "timestamp": self.timestamp,
                "type": self.type,
                "file": self.file,
                "hash": self.hash,
                "reviewed": self.reviewed,
            },
            reviewId=self.reviewId,
            deleted=self.deleted if self.deleted else None,
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EditRecord:
        return cls(
            timestamp=data["timestamp"],
            file=data["file"],
            hash=data["hash"],
            reviewed=data.get("reviewed", False),
            deleted=data.get("deleted", False),
            reviewId=data.get("reviewId"),
        )


@dataclass(frozen=True)
class StopBlockedRecord:
    """Recorded when a stop attempt is blocked due to unreviewed files."""

    timestamp: str
    reason: str | None = None
    reviewId: str | None = None
    files: list[str] | None = None
    type: Literal["stop_blocked"] = "stop_blocked"

    def to_dict(self) -> dict[str, Any]:
        return dict_with_optional(
            {"timestamp": self.timestamp, "type": self.type},
            reason=self.reason,
            reviewId=self.reviewId,
            files=self.files,
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StopBlockedRecord:
        return cls(
            timestamp=data["timestamp"],
            reason=data.get("reason"),
            reviewId=data.get("reviewId"),
            files=data.get("files"),
        )
