from dataclasses import dataclass, field
from typing import Literal, List, Optional, Dict, Set

@dataclass(frozen=True)
class StateEntry:
    type: Literal["edit", "stop_blocked", "review"]
    timestamp: str

@dataclass(frozen=True)
class EditRecord(StateEntry):
    file: str
    hash: str
    type: Literal["edit"] = "edit"
    reviewed: bool = False
    deleted: bool = False
    reviewId: Optional[str] = None

@dataclass(frozen=True)
class StopBlockedRecord(StateEntry):
    type: Literal["stop_blocked"] = "stop_blocked"
    reason: Optional[str] = None

@dataclass(frozen=True)
class ReviewMetadata(StateEntry):
    reviewId: str
    reviewPath: str
    status: Literal["pending", "completed"] = "pending"
    type: Literal["review"] = "review"
