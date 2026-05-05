#!/usr/bin/env python3
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from state import (  # noqa: E402
    ensure_runtime,
    get_project_root,
    get_unreviewed_files,
    is_review_complete,
    load_settings,
    load_state,
    log_event,
    mark_files_reviewed,
    pending_reviews_for_entries,
)


def block_response(message, feedback):
    print(
        json.dumps(
            {
                "block": True,
                "message": message,
                "feedback": feedback,
                "continue": False,
            },
            separators=(",", ":"),
        )
    )


def main():
    try:
        project_root = get_project_root()
        ensure_runtime(project_root)
        settings = load_settings(project_root)
        if not settings.get("enabled", True):
            log_event(project_root, "stop_disabled")
            return 0

        state = load_state(project_root)
        unreviewed = get_unreviewed_files(state)
        if not unreviewed:
            log_event(project_root, "stop_approved", reason="no_unreviewed_files")
            return 0

        pending_reviews = pending_reviews_for_entries(state, unreviewed)
        if pending_reviews:
            review = pending_reviews[0]
            review_path = review.get("reviewPath", "")
            if is_review_complete(review_path):
                mark_files_reviewed(unreviewed, review["reviewId"], project_root)
                log_event(project_root, "stop_approved", reason="review_completed", reviewId=review["reviewId"])
                return 0

            block_response(
                f"Claude Auto Review: Review {review.get('reviewId')} is still pending.",
                (
                    f"Complete the review file at {review_path}. Replace the Pending verdict with a real verdict, "
                    "then fix or explicitly skip findings according to the review prompt before stopping."
                ),
            )
            log_event(project_root, "stop_blocked", reason="review_pending", reviewId=review.get("reviewId"), review=review_path)
            return 2

        files = ", ".join(entry["file"] for entry in unreviewed)
        plugin_review_script = Path(__file__).resolve().parent.parent / "scripts" / "review_prompt.py"
        project_review_script = project_root / ".claude" / "claude-auto-review" / "scripts" / "review_prompt.py"
        command = f'python "{plugin_review_script}"'
        block_response(
            f"Claude Auto Review: Unreviewed changes detected in {files}.",
            (
                f"Review required before stopping. Run {command}, follow the generated review prompt, "
                "write the review, and fix any CRITICAL or HIGH findings you agree with. "
                f"Project-local script path after setup: {project_review_script}"
            ),
        )
        log_event(project_root, "stop_blocked", files=[entry["file"] for entry in unreviewed])
        return 2
    except Exception as error:
        try:
            log_event(get_project_root(), "stop_error", error=str(error))
        except Exception:
            pass
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
