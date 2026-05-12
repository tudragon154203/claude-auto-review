from pathlib import Path
import re

from claude_auto_review.state.review_matching import (
    best_pending_review_covering_entries,
    best_pending_review_exactly_matching_entries,
    best_pending_review_for_entries,
    entry_file_hash_pairs,
    is_review_expired,
    pending_review_candidates_for_entries,
    pending_reviews_exactly_matching_entries,
    pending_reviews_for_entries,
    review_file_hash_pairs,
)


def _review_verdict_text(review_path):
    path = Path(review_path)
    if not path.is_file():
        return None
    content = path.read_text(encoding="utf-8", errors="replace")
    if "## Verdict" not in content:
        return None
    verdict = content.split("## Verdict", 1)[1].strip()
    if not verdict:
        return None
    return verdict


def is_review_complete(review_path):
    verdict = _review_verdict_text(review_path)
    if not verdict:
        return False
    return verdict.lower() not in ("pending", "pending.")


def is_review_clean(review_path):
    """Return True only if the review verdict indicates no blocking issues.

    Note: The verdict must start with 'clean' to allow stop. This is coupled
    with the verdict template in agents/reviewer.md. Template changes may require
    updating this check.
    """
    verdict = _review_verdict_text(review_path)
    if not verdict:
        return False
    verdict = verdict.lower()
    if verdict.startswith("not clean"):
        return False
    if verdict.startswith("clean"):
        return True
    return bool(re.match(r"^confirmed\s*\(\s*clean\s*\)(?:\s|$|[-:])", verdict))
