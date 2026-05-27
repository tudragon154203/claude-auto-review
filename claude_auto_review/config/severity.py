from __future__ import annotations

from typing import Any

DEFAULT_MINIMUM_BLOCKING_SEVERITY = "medium"
MINIMUM_BLOCKING_SEVERITIES = frozenset({"info", "low", "medium", "high", "critical"})


def coerce_minimum_blocking_severity(value: Any) -> str:
    if value is None:
        return DEFAULT_MINIMUM_BLOCKING_SEVERITY
    severity = str(value).strip().lower()
    if severity in MINIMUM_BLOCKING_SEVERITIES:
        return severity
    return DEFAULT_MINIMUM_BLOCKING_SEVERITY
