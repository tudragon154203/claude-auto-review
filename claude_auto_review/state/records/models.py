from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from claude_auto_review.state.records.file import (
    ReviewFileRecord as ReviewFileRecord,
    _coerce_review_file_entries as _coerce_review_file_entries,
    _parse_review_file_entries as _parse_review_file_entries,
    serialize_review_file_entries as serialize_review_file_entries,
)


@dataclass(frozen=True)
class FileHash:
    """Eight-character SHA-256 prefix used to track reviewed file content."""

    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str) or len(self.value) != 8:
            raise ValueError("FileHash must be an 8-character SHA-256 prefix")
        if any(character not in "0123456789abcdef" for character in self.value.lower()):
            raise ValueError("FileHash must contain only hexadecimal characters")
        object.__setattr__(self, "value", self.value.lower())

    def __str__(self) -> str:
        return self.value


class StateEntry(Protocol):
    """Protocol shared by append-only state entries."""

    timestamp: str
    type: str


class EditEntry(Protocol):
    """State entry carrying a file/hash pair."""

    timestamp: str
    file: str
    hash: str


class ReviewEntry(Protocol):
    """State entry carrying review metadata."""

    timestamp: str
    reviewId: str
    files: list[ReviewFileRecord]
