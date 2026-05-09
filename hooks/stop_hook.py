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
    utc_now_iso,
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

        # No pending review exists — create one via review_prompt.py
        files = ", ".join(entry["file"] for entry in unreviewed)
        if not pending_reviews:
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
                    f"Claude Auto Review: Timeout generating review for {files}.",
                    "The review generation timed out. Check the logs and try again.",
                )
                return 2
            except Exception as e:
                log_event(project_root, "stop_hook_review_error", error=str(e))
                block_response(
                    f"Claude Auto Review: Error generating review for {files}.",
                    f"Failed to run review_prompt.py: {e}",
                )
                return 2

            state = load_state(project_root, client_id)
            pending_reviews = pending_reviews_for_entries(state, unreviewed)
            if not pending_reviews:
                block_response(
                    f"Claude Auto Review: Failed to create review for {files}.",
                    f"review_prompt.py ran but no review was created.\n\nOutput:\n{result.stdout}\n\nErrors:\n{result.stderr}",
                )
                return 2

        # We now have a pending review — try the claude CLI subagent
        review = pending_reviews[0]
        review_id = review.get("reviewId", "")
        review_path = Path(review.get("reviewPath", ""))
        prompt_file = client_run_dir(project_root, client_id) / f"review-{review_id}-prompt.md"

        claude_cli = shutil.which("claude")
        if claude_cli and prompt_file.is_file():
            try:
                cli_result = subprocess.run(
                    [
                        claude_cli,
                        "--print",
                        "--model",
                        "opus",
                        "--system-prompt-file",
                        str(prompt_file),
                        "--tools",
                        "",
                        "Produce the completed review markdown. Return only markdown.",
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
                    mark_files_reviewed(unreviewed, review_id, project_root, client_id=client_id)
                    log_event(project_root, "stop_approved", reason="review_completed", reviewId=review_id)
                    return 0
            except subprocess.TimeoutExpired:
                log_event(project_root, "stop_hook_claude_cli_timeout", reviewId=review_id)
            except Exception as e:
                log_event(project_root, "stop_hook_claude_cli_error", error=str(e))
        elif not claude_cli:
            log_event(project_root, "stop_hook_claude_cli_not_found")
        elif not prompt_file.is_file():
            log_event(project_root, "stop_hook_prompt_not_found", path=str(prompt_file))

        # Fallback: block with feedback so Claude can review in-session
        block_response(
            f"Claude Auto Review: Review {review_id} created for {files}.",
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
