from pathlib import Path
from dataclasses import dataclass
from typing import Literal

from claude_auto_review.review.completion import apply_completed_review, record_completed_review
from claude_auto_review.runtime.events import log_event
from claude_auto_review.state.reviews.verdicts import (
    extract_review_verdict_text,
    is_completed_review_content,
    is_review_complete_verdict,
    has_blocking_review_findings,
    normalize_review_verdict_content,
)
from claude_auto_review.stop.feedback import block_completed_review_findings, build_review_completion_prompt
from claude_auto_review.stop.reviews.core.prompt_runner import AutocompleteResult, attempt_stop_autocomplete
from claude_auto_review.stop.reviews.core.review_prompt_runner import _review_prompt_path
from claude_auto_review.stop.reviews.core.selection import get_entries_covered_by_review
from claude_auto_review.stop.orchestration.core.context import RuntimeContext
from claude_auto_review.stop.orchestration.core.resolution import StopFlowResolution
from claude_auto_review.stop.orchestration.core.response_actions import block_pending_review
from claude_auto_review.stop.response import approve_response, block_response
from claude_auto_review.state.snapshot import StateSnapshot


@dataclass(frozen=True)
class ReviewArtifactState:
    status: Literal["complete_clean", "complete_findings", "pending"]
    verdict: str | None = None


_AUTOCOMPLETE_RETRY_ATTEMPTS = 2


def _load_and_ensure_normalized_review(review_path):
    """Load review content and normalize verdict section if needed."""
    if not review_path.is_file():
        return None
    content = review_path.read_text(encoding="utf-8", errors="replace")
    normalized = normalize_review_verdict_content(content)
    if normalized != content:
        review_path.write_text(normalized, encoding="utf-8", newline="\n")
        return normalized
    return content


def _read_review_verdict(content):
    if content is None:
        return None
    return extract_review_verdict_text(content)


def _review_has_completed_artifact(content):
    if content is None:
        return False
    return is_completed_review_content(content)


def _classify_artifact_state(verdict, content, minimum_blocking_severity):
    if content is None:
        return ReviewArtifactState(status="pending", verdict=verdict)
    if is_review_complete_verdict(verdict):
        if has_blocking_review_findings(content, minimum_blocking_severity):
            return ReviewArtifactState(status="complete_findings", verdict=verdict)
        return ReviewArtifactState(status="complete_clean", verdict=verdict)
    if _review_has_completed_artifact(content):
        return ReviewArtifactState(status="complete_findings", verdict=verdict)
    return ReviewArtifactState(status="pending", verdict=verdict)


def _review_artifact_state(review_path, minimum_blocking_severity="medium"):
    content = _load_and_ensure_normalized_review(review_path)
    verdict = _read_review_verdict(content)
    return _classify_artifact_state(verdict, content, minimum_blocking_severity)


def _apply_completed_clean_review(ctx, review_id, covered_entries):
    remaining = apply_completed_review(
        ctx.project_root,
        ctx.client_id,
        review_id,
        covered_entries,
    )
    if not remaining:
        log_event(
            ctx.project_root,
            "stop_approved",
            client_id=ctx.client_id,
            reason="review_clean",
            reviewId=review_id,
        )
        approve_response(f"Claude Auto Review: review {review_id} clean, all files covered")
        return 0
    block_response(
        f"Claude Auto Review: Review {review_id} completed, but {len(remaining)} file(s) still need review.",
        "New edits were made after the review was created. Another review will be generated on the next stop attempt.",
    )
    return 2


def _apply_artifact_state(ctx, artifact_state, review_id, review_path, covered_entries, unreviewed):
    if artifact_state.status == "complete_clean":
        return _apply_completed_clean_review(ctx, review_id, covered_entries)
    if artifact_state.status == "complete_findings":
        record_completed_review(ctx.project_root, ctx.client_id, review_id, covered_entries)
        block_completed_review_findings(ctx, review_id, review_path, unreviewed)
        return 2
    return None


def finalize_review_stop(ctx: RuntimeContext, resolution: StopFlowResolution):
    state = resolution.state
    unreviewed = resolution.unreviewed
    review = resolution.review
    state_snapshot = StateSnapshot.from_events(state)
    covered_entries = get_entries_covered_by_review(review, state, latest_by_file=state_snapshot.latest_entries_by_file)
    review_id = review.reviewId
    review_path = Path(ctx.project_root) / review.reviewPath
    prompt_file = _review_prompt_path(ctx, review_id)
    reviewer_timeout_seconds = ctx.settings.reviewer_timeout_seconds
    try:
        reviewer_backend = ctx.settings.resolved_reviewer_backend()
    except ValueError as error:
        log_event(
            ctx.project_root,
            "stop_hook_invalid_reviewer_backend",
            client_id=ctx.client_id,
            error=str(error),
        )
        block_response(
            "Claude Auto Review: invalid reviewerBackend setting",
            str(error),
        )
        return 2
    reviewer_model = ctx.settings.resolved_reviewer_model(backend=reviewer_backend)
    # Phase 1: classify existing artifact
    artifact_state = _review_artifact_state(review_path, ctx.settings.minimum_blocking_severity)
    action_result = _apply_artifact_state(ctx, artifact_state, review_id, review_path, covered_entries, unreviewed)
    if action_result is not None:
        return action_result

    # Phase 2: run autocomplete retry loop
    user_prompt = build_review_completion_prompt(review_path)
    result: AutocompleteResult | None = None
    for attempt in range(_AUTOCOMPLETE_RETRY_ATTEMPTS):
        result = attempt_stop_autocomplete(
            ctx,
            review_id,
            review_path,
            prompt_file,
            user_prompt,
            reviewer_timeout_seconds=reviewer_timeout_seconds,
            model=reviewer_model,
            backend=reviewer_backend,
        )
        if result.status != "empty_stdout":
            break
        if attempt == 0:
            log_event(ctx.project_root, "stop_hook_reviewer_retry", client_id=ctx.client_id, reviewId=review_id)

    # Phase 3: re-evaluate after retry
    artifact_state = _review_artifact_state(review_path, ctx.settings.minimum_blocking_severity)
    action_result = _apply_artifact_state(ctx, artifact_state, review_id, review_path, covered_entries, unreviewed)
    if action_result is not None:
        return action_result

    if result is not None and result.status == "empty_stdout":
        log_event(ctx.project_root, "stop_hook_reviewer_empty_approved", client_id=ctx.client_id, reviewId=review_id)
        log_event(
            ctx.project_root,
            "stop_approved",
            client_id=ctx.client_id,
            reason="review_auto_approved_empty_stdout",
            reviewId=review_id,
        )
        approve_response(f"Claude Auto Review: review {review_id} auto-approved (empty stdout)")
        return 0

    return block_pending_review(ctx, review_id, review_path, prompt_file, unreviewed)
