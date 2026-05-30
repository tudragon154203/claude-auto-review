from __future__ import annotations

import logging
import re

from claude_auto_review.config.models import (
    DEFAULT_MINIMUM_BLOCKING_SEVERITY,
)
from claude_auto_review.state.reviews.detection import _CONTRADICTION_RE, _is_no_findings_line, has_review_findings
from claude_auto_review.state.reviews.parsing import _UNRECOGNIZED_SEVERITY, parse_review_findings

logger = logging.getLogger(__name__)

# Plain canonical field: must start with whitespace, must NOT contain **.
_PLAIN_CANONICAL_FIELD_RE = re.compile(
    r"^\s+(?:Severity|Verdict|Reason|Rule|Location|Rationale|Suggestion):\s*\S",
    re.IGNORECASE | re.MULTILINE,
)

# Bold canonical field: requires paired ** on the label (**Field:**).
# The value may or may not be bold — the constraint is the label's bold is closed.
_BOLD_CANONICAL_FIELD_RE = re.compile(
    r"^\s*\*\*(?:Severity|Verdict|Reason|Rule|Location|Rationale|Suggestion):\*\*",
    re.IGNORECASE | re.MULTILINE,
)


def _has_canonical_field_line(text: str) -> bool:
    for line in text.splitlines():
        if "**" in line:
            if _BOLD_CANONICAL_FIELD_RE.match(line):
                return True
        elif _PLAIN_CANONICAL_FIELD_RE.match(line):
            return True
    return False

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
            # Apply the same prose-noise and contradiction rules here that
            # has_review_findings applies at the document level, so we never
            # fall back to the full-doc re-evaluation (which would otherwise
            # re-introduce the "confirmed always blocks" behaviour for any
            # unparsed prose block that merely contains the word "confirmed").
            if _is_no_findings_line(finding.raw_text):
                continue
            # Canonical fields but no severity = ambiguous state: treat as not
            # blocking unless the prose itself is explicitly a finding (contradiction,
            # issue indicator...).  This matches the reviewer's request.
            if _has_canonical_field_line(
                finding.raw_text
            ) and not _CONTRADICTION_RE.search(finding.raw_text):
                logger.info(
                    "has_blocking_review_findings: bypassing ambiguous "
                    "severity=None block (has canonical fields, no contradiction) "
                    "(raw_text=%r)",
                    finding.raw_text[:120],
                )
                continue
            # Any other severity=None case (badge/field headline, prose block) is
            # treated as a real blocking finding.
            return True
        severity_rank = _severity_rank(finding.severity)
        if threshold is None or severity_rank is None or severity_rank >= threshold:
            return True
    return False
