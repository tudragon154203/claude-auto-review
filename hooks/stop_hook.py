#!/usr/bin/env python3
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from state import (  # noqa: E402
    append_state,
    consecutive_stop_blocks,
    ensure_client_runtime,
    get_client_id,
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
        client_id = get_client_id()
        ensure_client_runtime(project_root, client_id)
        settings = load_settings(project_root)
        if not settings.get("enabled", True):
            log_event(project_root, "stop_disabled")
            return 0

        state = load_state(project_root, client_id)
        unreviewed = get_unreviewed_files(state)
        if not unreviewed:
            log_event(project_root, "stop_approved", reason="no_unreviewed_files")
            return 0

        # Circuit breaker: if too many consecutive stop blocks, allow stop anyway
        max_passes = int(settings.get("maxStopPasses", 3))
        block_count = consecutive_stop_blocks(state)
        if block_count >= max_passes:
            log_event(project_root, "stop_approved", reason="circuit_breaker", block_count=block_count, max_passes=max_passes)
            return 0

        pending_reviews = pending_reviews_for_entries(state, unreviewed)
        if pending_reviews:
            review = pending_reviews[0]
            review_path = review.get("reviewPath", "")
            if is_review_complete(review_path):
                mark_files_reviewed(unreviewed, review["reviewId"], project_root, client_id=client_id)
                log_event(project_root, "stop_approved", reason="review_completed", reviewId=review["reviewId"])
                return 0

            block_response(
                f"Claude Auto Review: Review {review.get('reviewId')} is still pending.",
                (
                    f"Final verdict still says 'Pending' in the review file at:\n  {review_path}\n\n"
                    "Edit the file to mark each finding as Confirmed, Skipped, or Fixed. "
                    "Once all verdicts are set, stopping will be allowed."
                ),
            )
            log_event(project_root, "stop_blocked", reason="review_pending", reviewId=review.get("reviewId"), review=review_path)
            append_state({"type": "stop_blocked", "reason": "review_pending"}, project_root, client_id=client_id)
            return 2

        files = ", ".join(entry["file"] for entry in unreviewed)
        plugin_review_script = Path(__file__).resolve().parent.parent / "scripts" / "review_prompt.py"
        project_review_script = project_root / ".claude" / "claude-auto-review" / "scripts" / "review_prompt.py"
        command = f'python "{plugin_review_script}"'
        block_response(
            f"Claude Auto Review: Unreviewed changes detected in {files}.",
            (
                f"Start the review by running:\n  {command}\n\n"
                "Go through each finding in the generated file and set its verdict "
                "(Confirmed, Skipped, Fixed). Once all findings are reviewed, "
                "you'll be able to stop.\n"
                f"Script path: {project_review_script}"
            ),
        )
        log_event(project_root, "stop_blocked", files=[entry["file"] for entry in unreviewed])
        append_state({"type": "stop_blocked", "reason": "no_pending_review"}, project_root, client_id=client_id)
        return 2
    except Exception as error:
        try:
            log_event(get_project_root(), "stop_error", error=str(error))
        except Exception:
            pass
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
