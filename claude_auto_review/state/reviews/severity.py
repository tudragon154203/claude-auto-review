from __future__ import annotations

from claude_auto_review.config.constants.severity import MINIMUM_BLOCKING_SEVERITIES

_UNRECOGNIZED_SEVERITY = "<unrecognized>"

SEVERITY_RANKS: dict[str, int] = {
    "info": 0,
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
}


def _normalize_severity(value: str | None) -> str | None:
    if value is None:
        return None
    severity = value.strip().lower()
    if severity in MINIMUM_BLOCKING_SEVERITIES:
        return severity
    if severity == "none":
        return None
    return _UNRECOGNIZED_SEVERITY


def severity_rank(value: str, *, default_rank: int | None = None) -> int | None:
    if value == _UNRECOGNIZED_SEVERITY:
        if default_rank is not None:
            return default_rank
        from claude_auto_review.config.constants.severity import DEFAULT_MINIMUM_BLOCKING_SEVERITY

        return SEVERITY_RANKS.get(DEFAULT_MINIMUM_BLOCKING_SEVERITY, 2)
    return SEVERITY_RANKS.get(value.strip().lower())
