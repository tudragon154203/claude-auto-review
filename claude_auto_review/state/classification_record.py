from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Optional

from claude_auto_review.state.record_utils import dict_with_optional


@dataclass(frozen=True)
class ClassificationRecord:
    """Outcome of classifying the last assistant message before a stop."""
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
        return dict_with_optional(
            {
                "timestamp": self.timestamp,
                "type": self.type,
                "status": self.status,
                "reason": self.reason,
                "latencyMs": self.latencyMs,
                "messageChars": self.messageChars,
                "model": self.model,
                "baseUrl": self.baseUrl,
            },
            httpStatus=self.httpStatus,
            debugResponse=self.debugResponse,
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ClassificationRecord":
        return cls(
            timestamp=data["timestamp"],
            status=data["status"],
            reason=data["reason"],
            latencyMs=data["latencyMs"],
            messageChars=data["messageChars"],
            model=data["model"],
            baseUrl=data["baseUrl"],
            httpStatus=data.get("httpStatus"),
            debugResponse=data.get("debugResponse"),
        )
