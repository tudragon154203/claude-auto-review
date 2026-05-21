from dataclasses import dataclass
from typing import Any, Literal, Optional

from claude_auto_review.state.file_record import (
    ReviewFileRecord,
    _coerce_review_file_entries,
    _parse_review_file_entries,
    serialize_review_file_entries,
)


@dataclass(frozen=True)
class ReviewMetadata:
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
            "files": serialize_review_file_entries(self.files),
            "clientId": self.clientId,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ReviewMetadata":
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
    timestamp: str
    reviewId: str
    files: list[ReviewFileRecord]
    clientId: str = ""
    duration: Optional[str] = None
    durationSeconds: Optional[float] = None
    type: Literal["review_completed"] = "review_completed"

    def __post_init__(self):
        object.__setattr__(self, "files", _coerce_review_file_entries(self.files))

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "timestamp": self.timestamp,
            "type": self.type,
            "reviewId": self.reviewId,
            "files": serialize_review_file_entries(self.files),
            "clientId": self.clientId,
        }
        if self.duration is not None:
            d["duration"] = self.duration
        if self.durationSeconds is not None:
            d["durationSeconds"] = self.durationSeconds
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ReviewCompletedRecord":
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
    timestamp: str
    reviewId: str
    status: str
    returncode: int | None = None
    stdout_len: int = 0
    type: Literal["review_autocomplete"] = "review_autocomplete"

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "timestamp": self.timestamp,
            "type": self.type,
            "reviewId": self.reviewId,
            "status": self.status,
            "stdout_len": self.stdout_len,
        }
        if self.returncode is not None:
            d["returncode"] = self.returncode
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ReviewAutocompleteRecord":
        # Required fields (fail fast if missing)
        timestamp = data["timestamp"]
        reviewId = data["reviewId"]
        status = data["status"]
        # Optional
        returncode = data.get("returncode")
        stdout_len = data.get("stdout_len", 0)
        return cls(
            timestamp=timestamp,
            reviewId=reviewId,
            status=status,
            returncode=returncode,
            stdout_len=stdout_len,
        )
