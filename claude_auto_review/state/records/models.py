from __future__ import annotations

from dataclasses import dataclass


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
