from __future__ import annotations

from claude_auto_review.config.models import (
    DEFAULT_MINIMUM_BLOCKING_SEVERITY,
)
from claude_auto_review.state.reviews.detection import has_review_findings
from claude_auto_review.state.reviews.parsing import _UNRECOGNIZED_SEVERITY, parse_review_findings

_SEVERITY_RANKS = {
    "info": 0,
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
}


def _severity_rank(value: str) -> int | None:
    if value == _UNRECOGNIZED_SEVERITY:
        return _SEVERITY_RANKS.get(DEFAULT_MINIMUM_BLOCKING_SEVERITY, 2)
    return _SEVERITY_RANKS.get(value.strip().lower())


def has_blocking_review_findings(
    content: str | None, minimum_blocking_severity: str = DEFAULT_MINIMUM_BLOCKING_SEVERITY
) -> bool:
    threshold = _severity_rank(minimum_blocking_severity) if minimum_blocking_severity else None
    if threshold is None:
        threshold = _severity_rank(DEFAULT_MINIMUM_BLOCKING_SEVERITY)

    findings = parse_review_findings(content)
    if not findings:
        return has_review_findings(content)

    for finding in findings:
        verdict = (finding.verdict or "").strip().lower()
        if verdict.startswith("skipped"):
            continue
        if not verdict.startswith("confirmed"):
            return True
        if finding.severity is None:
            return True
        else:
            severity_rank = _severity_rank(finding.severity)
        if threshold is None or severity_rank is None or severity_rank >= threshold:
            return True
    return False
