"""Re-export facade for findings sub-modules.

All public names are imported from their canonical locations so that
``from claude_auto_review.state.reviews.findings import ...`` continues
to work unchanged.
"""

from __future__ import annotations

from claude_auto_review.state.reviews.blocking import (
    _severity_rank as _severity_rank,
)
from claude_auto_review.state.reviews.blocking import (
    has_blocking_review_findings as has_blocking_review_findings,
)
from claude_auto_review.state.reviews.detection import (
    _CONTRADICTION_RE as _CONTRADICTION_RE,
)
from claude_auto_review.state.reviews.detection import (
    _FINDING_HEADING as _FINDING_HEADING,
)
from claude_auto_review.state.reviews.detection import (
    _NO_FINDINGS_PREFIXES as _NO_FINDINGS_PREFIXES,
)
from claude_auto_review.state.reviews.detection import (
    _NO_FINDINGS_VERB_RE as _NO_FINDINGS_VERB_RE,
)
from claude_auto_review.state.reviews.detection import (
    _PUNCTUATION_CHARS as _PUNCTUATION_CHARS,
)
from claude_auto_review.state.reviews.detection import (
    _STRICT_NO_FINDINGS_PREFIXES as _STRICT_NO_FINDINGS_PREFIXES,
)
from claude_auto_review.state.reviews.detection import (
    _UNQUALIFIED_NO_FINDINGS_PREFIXES as _UNQUALIFIED_NO_FINDINGS_PREFIXES,
)
from claude_auto_review.state.reviews.detection import (
    _is_no_findings_line as _is_no_findings_line,
)
from claude_auto_review.state.reviews.detection import (
    has_review_findings as has_review_findings,
)
from claude_auto_review.state.reviews.parsing import (
    _FINDING_FIELD_RE as _FINDING_FIELD_RE,
)
from claude_auto_review.state.reviews.parsing import (
    ReviewFinding as ReviewFinding,
)
from claude_auto_review.state.reviews.parsing import (
    _extract_heading_severity as _extract_heading_severity,
)
from claude_auto_review.state.reviews.parsing import (
    _normalize_severity as _normalize_severity,
)
from claude_auto_review.state.reviews.parsing import (
    _parse_finding_block as _parse_finding_block,
)
from claude_auto_review.state.reviews.parsing import (
    parse_review_findings as parse_review_findings,
)

__all__ = [
    "ReviewFinding",
    "_FINDING_FIELD_RE",
    "_FINDING_HEADING",
    "_NO_FINDINGS_PREFIXES",
    "_STRICT_NO_FINDINGS_PREFIXES",
    "_UNQUALIFIED_NO_FINDINGS_PREFIXES",
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
