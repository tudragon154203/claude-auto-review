from __future__ import annotations

import re
from pathlib import Path

from claude_auto_review.state.reviews.findings import has_review_findings
from claude_auto_review.state.reviews.review_text import extract_review_verdict_text, get_review_verdict_text

# Patterns that unambiguously signal a completed review verdict.
# Negative patterns (incomplete/pending) are checked first in is_review_complete_verdict.
_COMPLETE_VERDICT = re.compile(
    r"^(?:"
    r"clean\b"
    r"|confirmed\s*(?:\(\s*clean\s*\))?"
    r"|not\s+clean\b"
    r"|\d+\s+issues?\b"
    r"|all\s+(?:(?:fixes|issues?)\s+)?(?:applied|addressed)\b"
    r"|findings?\s+present\b"
    r"|has\s+findings?\b"
    r"|issue(?:s)?\s+found\b"
    r")",
    re.IGNORECASE,
)


def is_placeholder_review_content(content: str | None) -> bool:
    if not content:
        return True
    text = content.strip()
    if not text:
        return True
    placeholder_markers = (
        "No findings yet. This file is a placeholder until Claude completes the review.",
        "Pending. Claude must complete this review",
        "## Verdict\n\nPending.",
    )
    return any(marker in text for marker in placeholder_markers)


def is_completed_review_content(content: str | None) -> bool:
    return not is_placeholder_review_content(content)


def is_review_complete_verdict(verdict: str | None) -> bool:
    if not verdict:
        return False
    verdict = verdict.strip().lower()
    if verdict in ("pending", "pending."):
        return False
    return bool(_COMPLETE_VERDICT.match(verdict))


def is_review_clean_verdict(verdict: str | None) -> bool:
    if not verdict:
        return False
    verdict = verdict.strip().lower()
    if verdict.startswith("not clean"):
        return False
    if verdict.startswith("clean"):
        return True
    return bool(re.match(r"^confirmed\s*\(\s*clean\s*\)(?:\s|$|[-:])", verdict))


def is_review_clean_content(content: str | None) -> bool:
    verdict = extract_review_verdict_text(content)
    if not is_review_clean_verdict(verdict):
        return False
    return not has_review_findings(content)


def is_review_complete(review_path: str | Path) -> bool:
    return is_review_complete_verdict(get_review_verdict_text(review_path))


def is_review_clean(review_path: str | Path) -> bool:
    path = Path(review_path)
    if not path.is_file():
        return False
    content = path.read_text(encoding="utf-8", errors="replace")
    return is_review_clean_content(content)
