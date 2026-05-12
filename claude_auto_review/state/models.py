from dataclasses import dataclass, asdict
from typing import Literal, Optional, Any


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
        d = asdict(self)
        if self.reviewId is None:
            d.pop("reviewId")
        if not self.deleted:
            d.pop("deleted")
        return d


@dataclass(frozen=True)
class StopBlockedRecord:
    timestamp: str
    reason: Optional[str] = None
    reviewId: Optional[str] = None
    files: Optional[list[str]] = None
    type: Literal["stop_blocked"] = "stop_blocked"

    def to_dict(self) -> dict[str, Any]:
        d = {"type": "stop_blocked", "timestamp": self.timestamp}
        if self.reason is not None:
            d["reason"] = self.reason
        if self.reviewId is not None:
            d["reviewId"] = self.reviewId
        if self.files is not None:
            d["files"] = self.files
        return d


@dataclass(frozen=True)
class ReviewMetadata:
    timestamp: str
    reviewId: str
    reviewPath: str
    files: list[dict[str, str]]
    clientId: str
    status: Literal["pending", "completed"] = "pending"
    type: Literal["review"] = "review"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ReviewCompletedRecord:
    timestamp: str
    reviewId: str
    files: list[dict[str, str]]
    clientId: str = ""
    duration: Optional[str] = None
    durationSeconds: Optional[float] = None
    type: Literal["review_completed"] = "review_completed"

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "type": "review_completed",
            "reviewId": self.reviewId,
            "files": self.files,
            "timestamp": self.timestamp,
            "clientId": self.clientId,
        }
        if self.duration is not None:
            d["duration"] = self.duration
        if self.durationSeconds is not None:
            d["durationSeconds"] = self.durationSeconds
        return d


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
            "type": self.type,
            "timestamp": self.timestamp,
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


# Union of all state event types for type annotations
StateEvent = EditRecord | StopBlockedRecord | ReviewMetadata | ReviewCompletedRecord | ClassificationRecord
