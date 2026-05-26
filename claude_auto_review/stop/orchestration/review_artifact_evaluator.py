from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from claude_auto_review.config.models import DEFAULT_MINIMUM_BLOCKING_SEVERITY
from claude_auto_review.state.reviews.completion import is_completed_review_content, is_review_complete_verdict
from claude_auto_review.state.reviews.findings import has_blocking_review_findings
from claude_auto_review.state.reviews.normalization import normalize_review_verdict_content
from claude_auto_review.state.reviews.review_text import extract_review_verdict_text


@dataclass(frozen=True)
class ReviewArtifactState:
    status: Literal["complete_clean", "complete_findings", "pending"]
    verdict: str | None = None


def load_and_ensure_normalized_review(review_path, client_id=None, minimum_blocking_severity=DEFAULT_MINIMUM_BLOCKING_SEVERITY):
    if not review_path.is_file():
        return None
    content = review_path.read_text(encoding="utf-8", errors="replace")
    normalized = normalize_review_verdict_content(content, client_id=client_id, minimum_blocking_severity=minimum_blocking_severity)
    if normalized != content:
        review_path.write_text(normalized, encoding="utf-8", newline="\n")
        return normalized
    return content


def classify_review_artifact_state(
    review_path: Path,
    *,
    minimum_blocking_severity=DEFAULT_MINIMUM_BLOCKING_SEVERITY,
    client_id=None,
) -> ReviewArtifactState:
    content = load_and_ensure_normalized_review(
        review_path,
        client_id=client_id,
        minimum_blocking_severity=minimum_blocking_severity,
    )
    verdict = extract_review_verdict_text(content) if content is not None else None
    if content is None:
        return ReviewArtifactState(status="pending", verdict=verdict)
    if is_review_complete_verdict(verdict):
        if has_blocking_review_findings(content, minimum_blocking_severity):
            return ReviewArtifactState(status="complete_findings", verdict=verdict)
        return ReviewArtifactState(status="complete_clean", verdict=verdict)
    if is_completed_review_content(content):
        return ReviewArtifactState(status="complete_findings", verdict=verdict)
    return ReviewArtifactState(status="pending", verdict=verdict)
