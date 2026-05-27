from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from claude_auto_review.config.models import DEFAULT_MINIMUM_BLOCKING_SEVERITY
from claude_auto_review.state.reviews.completion import is_completed_review_content, is_review_complete_verdict
from claude_auto_review.state.reviews.findings import has_blocking_review_findings
from claude_auto_review.state.reviews.normalization import normalize_review_verdict_content
from claude_auto_review.state.reviews.review_text import extract_review_verdict_text


class ReviewArtifactStatus(str, Enum):
    COMPLETE_CLEAN = "complete_clean"
    COMPLETE_FINDINGS = "complete_findings"
    PENDING = "pending"


@dataclass(frozen=True)
class ReviewArtifactState:
    status: ReviewArtifactStatus
    verdict: str | None = None

    @property
    def is_complete(self) -> bool:
        return self.status is not ReviewArtifactStatus.PENDING

    @property
    def has_blocking_findings(self) -> bool:
        return self.status is ReviewArtifactStatus.COMPLETE_FINDINGS


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
        return ReviewArtifactState(status=ReviewArtifactStatus.PENDING, verdict=verdict)
    if is_review_complete_verdict(verdict):
        if has_blocking_review_findings(content, minimum_blocking_severity):
            return ReviewArtifactState(status=ReviewArtifactStatus.COMPLETE_FINDINGS, verdict=verdict)
        return ReviewArtifactState(status=ReviewArtifactStatus.COMPLETE_CLEAN, verdict=verdict)
    if is_completed_review_content(content):
        return ReviewArtifactState(status=ReviewArtifactStatus.COMPLETE_FINDINGS, verdict=verdict)
    return ReviewArtifactState(status=ReviewArtifactStatus.PENDING, verdict=verdict)
