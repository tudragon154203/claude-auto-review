from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class _HasToDict(Protocol):
    def to_dict(self) -> dict[str, Any]: ...


def serialize_review_file_entries(files: list[_HasToDict]) -> list[dict[str, Any]]:
    return [entry.to_dict() for entry in files]
