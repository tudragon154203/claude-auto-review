#!/usr/bin/env python3
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from state import (  # noqa: E402
    append_state,
    client_run_dir,
    cleanup_expired_pending_reviews,
    consecutive_stop_blocks,
    ensure_client_runtime,
    get_client_id,
    get_project_root,
    get_unreviewed_files,
    is_review_complete,
    is_review_expired,
    load_settings,
    load_state,
    log_event,
    mark_files_reviewed,
    utc_now_iso,
    latest_entries_by_file,
)


def find_pending_review_for_files(state, unreviewed_entries, timeout_hours=0):
    """Find the latest pending review that covers at least some of the unreviewed entries.

    Unlike pending_reviews_for_entries which requires full coverage, this accepts
    partial coverage so that new edits after review creation don't block review completion.
    Expired reviews (if timeout_hours > 0) are skipped and logged.
    """
    needed = {(entry["file"], entry["hash"]) for entry in unreviewed_entries}
    matches = []
    for entry in state:
        if not isinstance(entry, dict) or entry.get("type") != "review" or entry.get("status") != "pending":
            continue
        if timeout_hours > 0 and is_review_expired(entry, timeout_hours):
            log_event(
                get_project_root(),
                "stop_review_expired",
                review_id=entry.get("reviewId", ""),
                files=[f.get("file", "") for f in entry.get("files", []) if isinstance(f, dict)],
            )
            continue
        covered = {
            (item.get("file"), item.get("hash"))
            for item in entry.get("files", [])
            if isinstance(item, dict)
        }
        # Accept review if it covers at least some of the needed files
        overlap = needed & covered
        if overlap:
            matches.append((entry, len(overlap)))
    if not matches:
        return None
    # Return the one with most overlap (usually the most recent)
    return max(matches, key=lambda x: x[1])[0]


def get_entries_covered_by_review(review_entry, state_entries):
    """Get the edit entries in state that are covered by a given review."""
    review_files = {
        (item["file"], item["hash"])
        for item in review_entry.get("files", [])
        if isinstance(item, dict)
    }
    result = []
    latest_by_file = latest_entries_by_file(state_entries)
    for file_path, entry in latest_by_file.items():
        if (file_path, entry.get("hash")) in review_files:
            result.append(entry)
    return result


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
        timeout_hours = float(settings.get("pendingReviewTimeoutHours", 1))

        # Clean up any expired pending reviews before proceeding
        removed = cleanup_expired_pending_reviews(project_root)
        if removed > 0:
            print(f"[claude-auto-review] Removed {removed} expired pending review(s)", file=sys.stderr)

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

        # Find a pending review that covers at least some of the unreviewed files.
        # This handles the common case where edits arrive after review creation:
        # we can still complete the review for covered files and handle the rest.
        review = find_pending_review_for_files(state, unreviewed, timeout_hours)

        if not review:
            # No matching review — create one via review_prompt.py
            files_str = ", ".join(entry["file"] for entry in unreviewed)
            plugin_review_script = Path(__file__).resolve().parent.parent / "scripts" / "review_prompt.py"
            try:
                result = subprocess.run(
                    [sys.executable, str(plugin_review_script)],
                    cwd=str(project_root),
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=60,
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

            # Reload state and find the newly created review
            state = load_state(project_root, client_id)
            unreviewed = get_unreviewed_files(state)
            if not unreviewed:
                log_event(project_root, "stop_approved", reason="no_unreviewed_files_after_review")
                return 0
            review = find_pending_review_for_files(state, unreviewed, timeout_hours)
            if not review:
                block_response(
                    f"Claude Auto Review: Failed to create review for {files_str}.",
                    f"review_prompt.py ran but no review was created.\n\nOutput:\n{result.stdout}\n\nErrors:\n{result.stderr}",
                )
                return 2

        # Determine which entries this review actually covers
        covered_entries = get_entries_covered_by_review(review, state)
        review_id = review.get("reviewId", "")
        review_path = Path(review.get("reviewPath", ""))
        prompt_file = client_run_dir(project_root, client_id) / f"review-{review_id}-prompt.md"

        # Check if review is already complete (e.g. from a previous attempt)
        if is_review_complete(review_path):
            mark_files_reviewed(covered_entries, review_id, project_root, client_id=client_id)
            log_event(project_root, "stop_approved", reason="review_completed", reviewId=review_id)
            # Check if there are still unreviewed files not covered by this review
            state = load_state(project_root, client_id)
            remaining = get_unreviewed_files(state)
            if not remaining:
                return 0
            # Block: remaining files need a new review
            log_event(project_root, "stop_blocked_after_partial_review", remaining=[e["file"] for e in remaining])
            block_response(
                f"Claude Auto Review: Review {review_id} completed, but {len(remaining)} file(s) still need review.",
                "New edits were made after the review was created. Another review will be generated on the next stop attempt.",
            )
            append_state({"type": "stop_blocked", "reason": "partial_review", "timestamp": utc_now_iso()}, project_root, client_id=client_id)
            return 2

        # Try the claude CLI subagent to auto-complete the review
        claude_cli = shutil.which("claude")
        if claude_cli and prompt_file.is_file():
            try:
                cli_result = subprocess.run(
                    [
                        claude_cli,
                        "--print",
                        "--bare",
                        "--model",
                        "opus",
                        "--system-prompt-file",
                        str(prompt_file),
                    ],
                    cwd=str(project_root),
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=600,
                )
                log_event(
                    project_root,
                    "stop_hook_claude_cli_done",
                    returncode=cli_result.returncode,
                    stdout=cli_result.stdout[:500],
                    stderr=cli_result.stderr[:500] if cli_result.stderr else "",
                )
                if cli_result.returncode == 0 and cli_result.stdout.strip():
                    review_path.write_text(cli_result.stdout, encoding="utf-8", newline="\n")
                if is_review_complete(review_path):
                    mark_files_reviewed(covered_entries, review_id, project_root, client_id=client_id)
                    # Check for remaining unreviewed files
                    state = load_state(project_root, client_id)
                    remaining = get_unreviewed_files(state)
                    if not remaining:
                        log_event(project_root, "stop_approved", reason="review_completed", reviewId=review_id)
                        return 0
                    log_event(project_root, "stop_blocked_after_partial_review", remaining=[e["file"] for e in remaining])
                    block_response(
                        f"Claude Auto Review: Review {review_id} completed, but {len(remaining)} file(s) still need review.",
                        "New edits were made after the review was created. Another review will be generated on the next stop attempt.",
                    )
                    append_state({"type": "stop_blocked", "reason": "partial_review", "timestamp": utc_now_iso()}, project_root, client_id=client_id)
                    return 2
            except subprocess.TimeoutExpired:
                log_event(project_root, "stop_hook_claude_cli_timeout", reviewId=review_id)
            except Exception as e:
                log_event(project_root, "stop_hook_claude_cli_error", error=str(e))
        elif not claude_cli:
            log_event(project_root, "stop_hook_claude_cli_not_found")
        elif not prompt_file.is_file():
            log_event(project_root, "stop_hook_prompt_not_found", path=str(prompt_file))

        # Fallback: block with feedback so Claude can review in-session
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
    except Exception as error:
        try:
            log_event(get_project_root(), "stop_error", error=str(error))
        except Exception:
            pass
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
