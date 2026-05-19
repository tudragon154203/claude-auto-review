from pathlib import Path
from dataclasses import dataclass

from claude_auto_review.runtime.events import log_event
from claude_auto_review.state.reviews.verdicts import (
    extract_review_verdict_text,
    is_completed_review_content,
    is_review_clean,
    is_review_clean_content,
    is_review_complete_verdict,
    normalize_review_verdict_content,
)
from claude_auto_review.review.completion import apply_completed_review, record_completed_review
from claude_auto_review.config.settings import DEFAULT_SETTINGS, SETTING_REVIEWER_TIMEOUT, SETTING_REVIEWER_MODEL, DEFAULT_REVIEWER_MODEL
from claude_auto_review.stop.orchestration.core.context import RuntimeContext
from claude_auto_review.stop.feedback import (
    block_completed_review_findings,
    build_review_completion_prompt,
)
from claude_auto_review.stop.reviews.core.prompt_runner import attempt_stop_autocomplete
from claude_auto_review.stop.reviews.core.selection import get_entries_covered_by_review
from claude_auto_review.stop.reviews.core.review_prompt_runner import _review_prompt_path
from claude_auto_review.stop.orchestration.core.response_actions import block_pending_review
from claude_auto_review.stop.response import approve_response, block_response
from claude_auto_review.state.snapshot import StateSnapshot


@dataclass(frozen=True)
class ReviewArtifactState:
    status: str
    verdict: str | None = None


def _read_review_content(review_path):
    if not review_path.is_file():
        return None
    content = review_path.read_text(encoding="utf-8", errors="replace")
    normalized = normalize_review_verdict_content(content)
    if normalized != content:
        review_path.write_text(normalized, encoding="utf-8", newline="\n")
        return normalized
    return content


def _read_review_verdict(review_path, content=None):
    if content is None:
        content = _read_review_content(review_path)
    if content is None:
        return None
    return extract_review_verdict_text(content)


def _review_has_completed_artifact(review_path, content=None):
    if content is None:
        content = _read_review_content(review_path)
    if content is None:
        return False
    return is_completed_review_content(content)


def _review_artifact_state(review_path):
    content = _read_review_content(review_path)
    verdict = _read_review_verdict(review_path, content=content)
    if is_review_complete_verdict(verdict) and content is not None and is_review_clean_content(content):
        return ReviewArtifactState(status="complete_clean", verdict=verdict)
    if is_review_complete_verdict(verdict) and content is None and is_review_clean(review_path):
        return ReviewArtifactState(status="complete_clean", verdict=verdict)
    if is_review_complete_verdict(verdict):
        return ReviewArtifactState(status="complete_findings", verdict=verdict)
    if _review_has_completed_artifact(review_path, content=content):
        return ReviewArtifactState(status="complete_findings", verdict=verdict)
    return ReviewArtifactState(status="pending", verdict=verdict)


def _block_partial_review_remaining(review_id, remaining):
    block_response(
        f"Claude Auto Review: Review {review_id} completed, but {len(remaining)} file(s) still need review.",
        "New edits were made after the review was created. Another review will be generated on the next stop attempt.",
    )


def _apply_completed_clean_review(ctx, review_id, covered_entries):
    remaining = apply_completed_review(
        ctx.project_root,
        ctx.client_id,
        review_id,
        covered_entries,
    )
    if not remaining:
        approve_response(f"Claude Auto Review: review {review_id} clean, all files covered")
        return 0
    _block_partial_review_remaining(review_id, remaining)
    return 2


def _apply_artifact_state(ctx, artifact_state, review_id, review_path, covered_entries, unreviewed):
    if artifact_state.status == "complete_clean":
        return _apply_completed_clean_review(ctx, review_id, covered_entries)
    if artifact_state.status == "complete_findings":
        record_completed_review(ctx.project_root, ctx.client_id, review_id, covered_entries)
        block_completed_review_findings(ctx, review_id, review_path, unreviewed)
        return 2
    return None


def finalize_review_stop(ctx: RuntimeContext, resolution):
    state = resolution.state
    unreviewed = resolution.unreviewed
    review = resolution.review
    state_snapshot = StateSnapshot.from_events(state)
    covered_entries = get_entries_covered_by_review(review, state, latest_by_file=state_snapshot.latest_entries_by_file)
    review_id = review.reviewId
    review_path = Path(ctx.project_root) / review.reviewPath
    prompt_file = _review_prompt_path(ctx, review_id)
    reviewer_timeout_seconds = ctx.settings.get(SETTING_REVIEWER_TIMEOUT, DEFAULT_SETTINGS[SETTING_REVIEWER_TIMEOUT])
    reviewer_model = ctx.settings.get(SETTING_REVIEWER_MODEL, DEFAULT_REVIEWER_MODEL)
    artifact_state = _review_artifact_state(review_path)
    action_result = _apply_artifact_state(ctx, artifact_state, review_id, review_path, covered_entries, unreviewed)
    if action_result is not None:
        return action_result

    user_prompt = build_review_completion_prompt(review_path)
    for _attempt in range(2):
        result = attempt_stop_autocomplete(
            ctx,
            review_id,
            review_path,
            prompt_file,
            user_prompt,
            reviewer_timeout_seconds=reviewer_timeout_seconds,
            model=reviewer_model,
        )
        if result.status != "empty_stdout":
            break
        if _attempt == 0:
            log_event(ctx.project_root, "stop_hook_claude_cli_retry", client_id=ctx.client_id, reviewId=review_id)

    artifact_state = _review_artifact_state(review_path)
    action_result = _apply_artifact_state(ctx, artifact_state, review_id, review_path, covered_entries, unreviewed)
    if action_result is not None:
        return action_result

    if result.status == "empty_stdout":
        log_event(ctx.project_root, "stop_hook_claude_cli_empty_approved", client_id=ctx.client_id, reviewId=review_id)
        approve_response(f"Claude Auto Review: review {review_id} auto-approved (empty stdout)")
        return 0

    return block_pending_review(ctx, review_id, review_path, prompt_file, unreviewed)
