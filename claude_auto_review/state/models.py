from dataclasses import dataclass
from typing import Any, Literal, Optional


@dataclass(frozen=True)
class DictLikeModel:
    pass


@dataclass(frozen=True)
class ReviewFileRecord(DictLikeModel):
    file: str
    hash: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "file": self.file,
            "hash": self.hash,
        }


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
        parsed.append(ReviewFileRecord(file=item["file"], hash=item["hash"]))
    return parsed


@dataclass(frozen=True)
class EditRecord(DictLikeModel):
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


@dataclass(frozen=True)
class StopBlockedRecord(DictLikeModel):
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


@dataclass(frozen=True)
class ReviewMetadata(DictLikeModel):
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
            "files": [entry.to_dict() for entry in self.files],
            "clientId": self.clientId,
            "status": self.status,
        }


@dataclass(frozen=True)
class ReviewCompletedRecord(DictLikeModel):
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
            "files": [entry.to_dict() for entry in self.files],
            "clientId": self.clientId,
        }
        if self.duration is not None:
            d["duration"] = self.duration
        if self.durationSeconds is not None:
            d["durationSeconds"] = self.durationSeconds
        return d


@dataclass(frozen=True)
class ClassificationRecord(DictLikeModel):
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


# Union of all state event types for type annotations
StateEvent = EditRecord | StopBlockedRecord | ReviewMetadata | ReviewCompletedRecord | ClassificationRecord

_PARSERS = {
    "edit": lambda d: EditRecord(
        timestamp=d.get("timestamp", ""),
        file=d.get("file", ""),
        hash=d.get("hash", ""),
        reviewed=d.get("reviewed", False),
        deleted=d.get("deleted", False),
        reviewId=d.get("reviewId"),
    ),
    "stop_blocked": lambda d: StopBlockedRecord(
        timestamp=d.get("timestamp", ""),
        reason=d.get("reason"),
        reviewId=d.get("reviewId"),
        files=d.get("files"),
    ),
    "review": lambda d: ReviewMetadata(
        timestamp=d.get("timestamp", ""),
        reviewId=d.get("reviewId", ""),
        reviewPath=d.get("reviewPath", ""),
        files=_parse_review_file_entries(d.get("files", [])),
        clientId=d.get("clientId", ""),
        status=d.get("status", "pending"),
    ),
    "review_completed": lambda d: ReviewCompletedRecord(
        timestamp=d.get("timestamp", ""),
        reviewId=d.get("reviewId", ""),
        files=_parse_review_file_entries(d.get("files", [])),
        clientId=d.get("clientId", ""),
        duration=d.get("duration"),
        durationSeconds=d.get("durationSeconds"),
    ),
    "last_assistant_message_classified": lambda d: ClassificationRecord(
        timestamp=d.get("timestamp", ""),
        status=d.get("status", ""),
        reason=d.get("reason", ""),
        latencyMs=d.get("latencyMs", 0),
        messageChars=d.get("messageChars", 0),
        model=d.get("model", ""),
        baseUrl=d.get("baseUrl", ""),
        httpStatus=d.get("httpStatus"),
        debugResponse=d.get("debugResponse"),
    ),
}


def parse_event(raw: dict[str, Any]) -> StateEvent | None:
    if not isinstance(raw, dict):
        return None
    parser = _PARSERS.get(raw.get("type"))
    if parser is None:
        return None
    try:
        return parser(raw)
    except (TypeError, KeyError, ValueError):
        return None
