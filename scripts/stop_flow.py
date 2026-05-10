import json
import os
import subprocess
import sys
from pathlib import Path

from scripts.paths import client_run_dir, get_client_id, get_project_root, utc_now_iso
from scripts.reviews import is_review_complete
from scripts.state import (
    append_state,
    consecutive_stop_blocks,
    ensure_client_runtime,
    get_unreviewed_files,
    load_settings,
    load_state,
    log_event,
)
from scripts.stop_autocomplete import attempt_stop_autocomplete
from scripts.stop_selection import find_pending_review_for_files, get_entries_covered_by_review


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
        ),
    )
    print(message, file=sys.stderr)


def run_stop_flow(project_root, payload):
    client_id = get_client_id(payload.get("session_id"))
    ensure_client_runtime(project_root, client_id)
    settings = load_settings(project_root)
    timeout_hours = float(settings.get("pendingReviewTimeoutHours", 1))

    if not settings.get("enabled", True):
        log_event(project_root, "stop_disabled")
        return 0

    state = load_state(project_root, client_id)
    unreviewed = get_unreviewed_files(state)
    if not unreviewed:
        log_event(project_root, "stop_approved", reason="no_unreviewed_files")
        return 0

    max_passes = int(settings.get("maxStopPasses", 3))
    block_count = consecutive_stop_blocks(state)
    if block_count >= max_passes:
        log_event(project_root, "stop_approved", reason="circuit_breaker", block_count=block_count, max_passes=max_passes)
        return 0

    review = find_pending_review_for_files(state, unreviewed, project_root, timeout_hours)

    if not review:
        files_str = ", ".join(entry["file"] for entry in unreviewed)
        plugin_review_script = Path(__file__).resolve().parent / "review_prompt.py"
        env = os.environ.copy()
        session_id = payload.get("session_id")
        if session_id:
            env["CLAUDE_SESSION_ID"] = session_id
        try:
            result = subprocess.run(
                [sys.executable, str(plugin_review_script)],
                cwd=str(project_root),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=60,
                env=env,
            )
            log_event(
                project_root,
                "stop_hook_review_invoked",
                stdout=result.stdout,
                stderr=result.stderr,
                returncode=result.returncode,
            )
        except subprocess.TimeoutExpired:
            log_event(project_root, "stop_hook_review_timeout", script=str(plugin_review_script))
            block_response(
                f"Claude Auto Review: Timeout generating review for {files_str}.",
                "The review generation timed out. Check the logs and try again.",
            )
            return 2
        except Exception as e:
            log_event(project_root, "stop_hook_review_error", error=str(e))
            block_response(
                f"Claude Auto Review: Error generating review for {files_str}.",
                f"Failed to run review_prompt.py: {e}",
            )
            return 2

        state = load_state(project_root, client_id)
        unreviewed = get_unreviewed_files(state)
        if not unreviewed:
            log_event(project_root, "stop_approved", reason="no_unreviewed_files_after_review")
            return 0
        review = find_pending_review_for_files(state, unreviewed, project_root, timeout_hours)
        if not review:
            block_response(
                f"Claude Auto Review: Failed to create review for {files_str}.",
                f"review_prompt.py ran but no review was created.\n\nOutput:\n{result.stdout}\n\nErrors:\n{result.stderr}",
            )
            return 2

    covered_entries = get_entries_covered_by_review(review, state)
    review_id = review.get("reviewId", "")
    review_path = Path(review.get("reviewPath", ""))
    prompt_file = client_run_dir(project_root, client_id) / f"review-{review_id}-prompt.md"

    if is_review_complete(review_path):
        from scripts.state import mark_files_reviewed  # local import to avoid cycle during module import

        mark_files_reviewed(covered_entries, review_id, project_root, client_id=client_id)
        log_event(project_root, "stop_approved", reason="review_completed", reviewId=review_id)
        state = load_state(project_root, client_id)
        remaining = get_unreviewed_files(state)
        if not remaining:
            return 0
        log_event(project_root, "stop_blocked_after_partial_review", remaining=[e["file"] for e in remaining])
        block_response(
            f"Claude Auto Review: Review {review_id} completed, but {len(remaining)} file(s) still need review.",
            "New edits were made after the review was created. Another review will be generated on the next stop attempt.",
        )
        append_state({"type": "stop_blocked", "reason": "partial_review", "timestamp": utc_now_iso()}, project_root, client_id=client_id)
        return 2

    user_prompt = (
        f"Complete the review at {review_path}. "
        "Read each file, evaluate findings, set verdicts "
        "(Confirmed/Skipped/Fixed), and write the final review "
        "with a non-Pending Verdict."
    )
    if attempt_stop_autocomplete(project_root, client_id, review_id, review_path, prompt_file, covered_entries, user_prompt):
        return 0

    files_str = ", ".join(entry["file"] for entry in unreviewed)
    block_response(
        f"Claude Auto Review: Review {review_id} created for {files_str}.",
        (
            f"Review file created at:\n  {review_path}\n\n"
            "Go through each finding in the generated file and set its verdict "
            "(Confirmed, Skipped, Fixed). Once all verdicts are set, "
            "stopping will be allowed."
        ),
    )
    log_event(project_root, "stop_blocked", files=[entry["file"] for entry in unreviewed])
    append_state({"type": "stop_blocked", "reason": "review_pending", "timestamp": utc_now_iso()}, project_root, client_id=client_id)
    return 2
