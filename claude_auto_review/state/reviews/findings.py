"""Re-export facade for findings sub-modules.

All public names are imported from their canonical locations so that
``from claude_auto_review.state.reviews.findings import ...`` continues
to work unchanged.
"""

from claude_auto_review.state.reviews.blocking import (
    _severity_rank as _severity_rank,
    has_blocking_review_findings as has_blocking_review_findings,
)
from claude_auto_review.state.reviews.detection import (
    _ALWAYS_NO_FINDINGS_PREFIXES as _ALWAYS_NO_FINDINGS_PREFIXES,
    _CONTRADICTION_RE as _CONTRADICTION_RE,
    _FINDING_HEADING as _FINDING_HEADING,
    _NO_FINDINGS_PREFIXES as _NO_FINDINGS_PREFIXES,
    _NO_FINDINGS_VERB_RE as _NO_FINDINGS_VERB_RE,
    _PUNCTUATION_CHARS as _PUNCTUATION_CHARS,
    _STRICT_NO_FINDINGS_PREFIXES as _STRICT_NO_FINDINGS_PREFIXES,
    _is_no_findings_line as _is_no_findings_line,
    has_review_findings as has_review_findings,
)
from claude_auto_review.state.reviews.parsing import (
    ReviewFinding as ReviewFinding,
    _FINDING_FIELD_RE as _FINDING_FIELD_RE,
    _extract_heading_severity as _extract_heading_severity,
    _normalize_severity as _normalize_severity,
    _parse_finding_block as _parse_finding_block,
    parse_review_findings as parse_review_findings,
)

__all__ = [
    "ReviewFinding",
    "_FINDING_FIELD_RE",
    "_FINDING_HEADING",
    "_NO_FINDINGS_PREFIXES",
    "_STRICT_NO_FINDINGS_PREFIXES",
    "_ALWAYS_NO_FINDINGS_PREFIXES",
    "_NO_FINDINGS_VERB_RE",
    "_CONTRADICTION_RE",
    "_PUNCTUATION_CHARS",
    "_extract_heading_severity",
    "_normalize_severity",
    "_parse_finding_block",
    "_is_no_findings_line",
    "parse_review_findings",
    "has_review_findings",
    "has_blocking_review_findings",
]
