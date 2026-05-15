from dataclasses import dataclass
from typing import Any, Literal, Optional


def _serialize_review_file_entries(files: list["ReviewFileRecord"]) -> list[dict[str, Any]]:
    return [entry.to_dict() for entry in files]


@dataclass(frozen=True)
class ReviewFileRecord:
    file: str
    hash: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "file": self.file,
            "hash": self.hash,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ReviewFileRecord":
        return cls(file=data["file"], hash=data["hash"])


def _coerce_review_file_entries(files: list[ReviewFileRecord]) -> list[ReviewFileRecord]:
    coerced: list[ReviewFileRecord] = []
    for item in files:
        if not isinstance(item, ReviewFileRecord):
            raise ValueError("files must contain ReviewFileRecord entries")
        coerced.append(item)
    return coerced


def _parse_review_file_entries(files: list[dict[str, str]] | list[ReviewFileRecord]) -> list[ReviewFileRecord]:
    parsed: list[ReviewFileRecord] = []
    for item in files:
        if isinstance(item, ReviewFileRecord):
            parsed.append(item)
            continue
        if not isinstance(item, dict) or "file" not in item or "hash" not in item:
            raise ValueError("files must contain file/hash entries")
        parsed.append(ReviewFileRecord.from_dict(item))
    return parsed


@dataclass(frozen=True)
class EditRecord:
    timestamp: str
    file: str
    hash: str
    reviewed: bool = False
    deleted: bool = False
    reviewId: Optional[str] = None
    type: Literal["edit"] = "edit"

    def to_dict(self) -> dict[str, Any]:
        d = {
            "timestamp": self.timestamp,
            "type": self.type,
            "file": self.file,
            "hash": self.hash,
            "reviewed": self.reviewed,
        }
        if self.reviewId is not None:
            d["reviewId"] = self.reviewId
        if self.deleted:
            d["deleted"] = self.deleted
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EditRecord":
        return cls(
            timestamp=data.get("timestamp", ""),
            file=data.get("file", ""),
            hash=data.get("hash", ""),
            reviewed=data.get("reviewed", False),
            deleted=data.get("deleted", False),
            reviewId=data.get("reviewId"),
        )


@dataclass(frozen=True)
class StopBlockedRecord:
    timestamp: str
    reason: Optional[str] = None
    reviewId: Optional[str] = None
    files: Optional[list[str]] = None
    type: Literal["stop_blocked"] = "stop_blocked"

    def to_dict(self) -> dict[str, Any]:
        d = {
            "timestamp": self.timestamp,
            "type": self.type,
        }
        if self.reason is not None:
            d["reason"] = self.reason
        if self.reviewId is not None:
            d["reviewId"] = self.reviewId
        if self.files is not None:
            d["files"] = self.files
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StopBlockedRecord":
        return cls(
            timestamp=data.get("timestamp", ""),
            reason=data.get("reason"),
            reviewId=data.get("reviewId"),
            files=data.get("files"),
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
            "files": _serialize_review_file_entries(self.files),
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
            "files": _serialize_review_file_entries(self.files),
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
class ClassificationRecord:
    timestamp: str
    status: str
    reason: str
    latencyMs: int
    messageChars: int
    model: str
    baseUrl: str
    httpStatus: Optional[int] = None
    debugResponse: Optional[str] = None
    type: Literal["last_assistant_message_classified"] = "last_assistant_message_classified"

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "timestamp": self.timestamp,
            "type": self.type,
            "status": self.status,
            "reason": self.reason,
            "latencyMs": self.latencyMs,
            "messageChars": self.messageChars,
            "model": self.model,
            "baseUrl": self.baseUrl,
        }
        if self.httpStatus is not None:
            d["httpStatus"] = self.httpStatus
        if self.debugResponse is not None:
            d["debugResponse"] = self.debugResponse
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ClassificationRecord":
        return cls(
            timestamp=data.get("timestamp", ""),
            status=data.get("status", ""),
            reason=data.get("reason", ""),
            latencyMs=data.get("latencyMs", 0),
            messageChars=data.get("messageChars", 0),
            model=data.get("model", ""),
            baseUrl=data.get("baseUrl", ""),
            httpStatus=data.get("httpStatus"),
            debugResponse=data.get("debugResponse"),
        )


# Union of all state event types for type annotations
StateEvent = EditRecord | StopBlockedRecord | ReviewMetadata | ReviewCompletedRecord | ClassificationRecord
