from __future__ import annotations

from claude_auto_review.stop.orchestration.types.context import ResponsePayload


def _approve_payload(review_id: str) -> ResponsePayload:
    return ResponsePayload(system_message=f"Claude Auto Review: review {review_id} clean, all files covered")


def _partial_review_payload(review_id: str, remaining_count: int) -> ResponsePayload:
    return ResponsePayload(
        system_message=(
            f"Claude Auto Review: Review {review_id} completed, but {remaining_count} file(s) still need review."
        ),
        feedback=(
            "New edits were made after the review was created. "
            "Another review will be generated on the next stop attempt."
        ),
    )


def _invalid_backend_payload(error: Exception) -> ResponsePayload:
    return ResponsePayload(
        system_message="Claude Auto Review: invalid reviewerBackend setting",
        feedback=str(error),
    )
