from dataclasses import dataclass
from typing import Any, Literal, Optional


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
            timestamp=data["timestamp"],
            file=data["file"],
            hash=data["hash"],
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
            timestamp=data["timestamp"],
            reason=data.get("reason"),
            reviewId=data.get("reviewId"),
            files=data.get("files"),
        )
