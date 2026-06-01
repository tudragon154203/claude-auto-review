"""Shared helpers for state record serialization."""

from __future__ import annotations

from typing import Any


def dict_with_optional(base: dict[str, Any], **optional: Any) -> dict[str, Any]:
    """Return a shallow copy of *base* with non-None keyword args merged in."""
    result = dict(base)
    for key, value in optional.items():
        if value is not None:
            result[key] = value
    return result
