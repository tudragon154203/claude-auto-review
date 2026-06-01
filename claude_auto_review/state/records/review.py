from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, cast

from claude_auto_review.state.records.file import (
    ReviewFileRecord,
    _coerce_review_file_entries,
    _parse_review_file_entries,
    serialize_review_file_entries,
)
from claude_auto_review.state.records.utils import dict_with_optional


@dataclass(frozen=True)
class ReviewMetadata:
    """Tracks a review prompt creation and its lifecycle state."""

    timestamp: str
    reviewId: str
    reviewPath: str
    files: list[ReviewFileRecord]
    clientId: str
    status: Literal["pending", "completed"] = "pending"
    type: Literal["review"] = "review"

    def __post_init__(self):
        object.__setattr__(self, "files", _coerce_review_file_entries(self.files))

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "type": self.type,
            "reviewId": self.reviewId,
            "reviewPath": self.reviewPath,
            "files": serialize_review_file_entries(cast(list, self.files)),
            "clientId": self.clientId,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReviewMetadata:
        return cls(
            timestamp=data.get("timestamp", ""),
            reviewId=data.get("reviewId", ""),
            reviewPath=data.get("reviewPath", ""),
            files=_parse_review_file_entries(data.get("files", [])),
            clientId=data.get("clientId", ""),
            status=data.get("status", "pending"),
        )


@dataclass(frozen=True)
class ReviewCompletedRecord:
    """Recorded when a review run finishes with covered file entries."""

    timestamp: str
    reviewId: str
    files: list[ReviewFileRecord]
    clientId: str = ""
    duration: str | None = None
    durationSeconds: float | None = None
    type: Literal["review_completed"] = "review_completed"

    def __post_init__(self):
        object.__setattr__(self, "files", _coerce_review_file_entries(self.files))

    def to_dict(self) -> dict[str, Any]:
        return dict_with_optional(
            {
                "timestamp": self.timestamp,
                "type": self.type,
                "reviewId": self.reviewId,
                "files": serialize_review_file_entries(cast(list, self.files)),
                "clientId": self.clientId,
            },
            duration=self.duration,
            durationSeconds=self.durationSeconds,
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReviewCompletedRecord:
        return cls(
            timestamp=data.get("timestamp", ""),
            reviewId=data.get("reviewId", ""),
            files=_parse_review_file_entries(data.get("files", [])),
            clientId=data.get("clientId", ""),
            duration=data.get("duration"),
            durationSeconds=data.get("durationSeconds"),
        )


@dataclass(frozen=True)
class ReviewAutocompleteRecord:
    """Recorded when an auto-complete review backend finishes."""

    timestamp: str
    reviewId: str
    status: str
    returncode: int | None = None
    stdout_len: int = 0
    type: Literal["review_autocomplete"] = "review_autocomplete"

    def to_dict(self) -> dict[str, Any]:
        return dict_with_optional(
            {
                "timestamp": self.timestamp,
                "type": self.type,
                "reviewId": self.reviewId,
                "status": self.status,
                "stdout_len": self.stdout_len,
            },
            returncode=self.returncode,
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReviewAutocompleteRecord:
        # Required fields (fail fast if missing)
        timestamp = data["timestamp"]
        review_id = data["reviewId"]
        status = data["status"]
        # Optional
        returncode = data.get("returncode")
        stdout_len = data.get("stdout_len", 0)
        return cls(
            timestamp=timestamp,
            reviewId=review_id,
            status=status,
            returncode=returncode,
            stdout_len=stdout_len,
        )
