from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class _HasToDict(Protocol):
    def to_dict(self) -> dict[str, Any]: ...


@dataclass(frozen=True)
class ReviewFileRecord:
    """A file and its content hash tracked by a review run."""

    file: str
    hash: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "file": self.file,
            "hash": self.hash,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReviewFileRecord:
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


def serialize_review_file_entries(files: list[_HasToDict]) -> list[dict[str, Any]]:
    return [entry.to_dict() for entry in files]
