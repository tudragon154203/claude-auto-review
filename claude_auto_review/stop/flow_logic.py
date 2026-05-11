import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from claude_auto_review.paths import client_run_dir, local_now_iso
from claude_auto_review.state.reviews import is_review_clean, is_review_complete
from claude_auto_review.review.completion import apply_completed_review
from claude_auto_review.state.store_read import get_unreviewed_files, load_state
from claude_auto_review.state.store_write import append_state, log_event
from claude_auto_review.settings import DEFAULT_SETTINGS
from claude_auto_review.stop.autocomplete import attempt_stop_autocomplete
from claude_auto_review.stop.last_assistant_message import classify_last_assistant_message
from claude_auto_review.stop.selection import find_pending_review_for_files, get_entries_covered_by_review

@dataclass(frozen=True)
class StopFlowResolution:
    state: list
    unreviewed: list
    review: dict | None = None
    exit_code: int | None = None

    @property
    def is_terminal(self):
        return self.exit_code is not None


def block_response(message, feedback):
    print(
        json.dumps(
            {
                "decision": "block",
                "reason": feedback,
                "systemMessage": message,
            },
            separators=(",", ":"),
        ),
    )
    print(message, file=sys.stderr)


def build_unreviewed_files_string(unreviewed_entries):
    return ", ".join(entry["file"] for entry in unreviewed_entries)


def build_review_completion_prompt(review_path):
    return (
        f"Complete the review at {review_path}. "
        "Read each file, evaluate findings, set verdicts "
        "(Confirmed/Skipped), and write the final review "
        "with a non-Pending Verdict."
    )


def review_feedback_max_chars(settings):
    try:
        return max(0, int(settings.get("reviewFeedbackMaxChars", DEFAULT_SETTINGS["reviewFeedbackMaxChars"])))
    except (TypeError, ValueError):
        return DEFAULT_SETTINGS["reviewFeedbackMaxChars"]


def read_review_feedback(review_path, max_chars=None):
    if max_chars is None:
        max_chars = DEFAULT_SETTINGS["reviewFeedbackMaxChars"]
    path = Path(review_path)
    if not path.is_file():
        return f"Review file is missing: {path}"
    content = path.read_text(encoding="utf-8", errors="replace")
    if len(content) <= max_chars:
        return content
    return (
        f"{content[:max_chars]}\n\n"
        f"[Review truncated at {max_chars} characters. Read the full review at {path}.]"
    )


def build_review_findings_feedback(review_id, review_path, max_chars=None):
    review_text = read_review_feedback(review_path, max_chars=max_chars)
    return (
        f"Claude Auto Review completed review {review_id} and found blocking findings.\n\n"
        f"Review file: {review_path}\n\n"
        "Act on the review below before stopping. Fix each Confirmed finding, "
        "or make a narrowly justified code change that renders it inapplicable. "
        "After making changes, try stopping again so the changed files are reviewed.\n\n"
        f"{review_text}"
    )


def block_completed_review_findings(project_root, client_id, review_id, review_path, unreviewed, settings):
    block_response(
        f"Claude Auto Review: Review {review_id} found issues to address.",
        build_review_findings_feedback(review_id, review_path, review_feedback_max_chars(settings)),
    )
    log_event(project_root, "stop_blocked", files=[entry["file"] for entry in unreviewed], reviewId=review_id)
    append_state(
        {"type": "stop_blocked", "reason": "review_findings", "timestamp": local_now_iso()},
        project_root,
        client_id=client_id,
    )


def _review_prompt_command(review_prompt_script):
    return [sys.executable, str(review_prompt_script)]


def _review_prompt_path(project_root, client_id, review_id):
    return client_run_dir(project_root, client_id) / f"review-{review_id}-prompt.md"


def _run_review_prompt(project_root, review_prompt_script, env):
    result = subprocess.run(
        _review_prompt_command(review_prompt_script),
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
    return result


def _reload_client_state(project_root, client_id):
    state = load_state(project_root, client_id)
    return state, get_unreviewed_files(state)


def _block_review_prompt_failure(files_str, result):
    block_response(
        f"Claude Auto Review: Failed to create review for {files_str}.",
        f"review_prompt.py ran but no review was created.\n\nOutput:\n{result.stdout}\n\nErrors:\n{result.stderr}",
    )


def _classify_last_assistant_message_if_enabled(project_root, client_id, payload, settings):
    if settings.get("lastAssistantMessageClassifierEnabled", False):
        classify_last_assistant_message(project_root, client_id, payload, settings)


def resolve_pending_review(project_root, client_id, payload, state, unreviewed, timeout_hours, review_prompt_script):
    review = find_pending_review_for_files(state, unreviewed, project_root, timeout_hours)
    if review:
        return StopFlowResolution(state=state, unreviewed=unreviewed, review=review)

    files_str = build_unreviewed_files_string(unreviewed)
    env = os.environ.copy()
    session_id = payload.get("session_id")
    if session_id:
        env["CLAUDE_SESSION_ID"] = session_id
    try:
        result = _run_review_prompt(project_root, review_prompt_script, env)
    except subprocess.TimeoutExpired:
        log_event(project_root, "stop_hook_review_timeout", script=str(review_prompt_script))
        block_response(
            f"Claude Auto Review: Timeout generating review for {files_str}.",
            "The review generation timed out. Check the logs and try again.",
        )
        return StopFlowResolution(state=state, unreviewed=unreviewed, exit_code=2)
    except Exception as e:
        log_event(project_root, "stop_hook_review_error", error=str(e))
        block_response(
            f"Claude Auto Review: Error generating review for {files_str}.",
            f"Failed to run review_prompt.py: {e}",
        )
        return StopFlowResolution(state=state, unreviewed=unreviewed, exit_code=2)

    state, unreviewed = _reload_client_state(project_root, client_id)
    if not unreviewed:
        log_event(project_root, "stop_approved", reason="no_unreviewed_files_after_review")
        return StopFlowResolution(state=state, unreviewed=unreviewed, exit_code=0)
    review = find_pending_review_for_files(state, unreviewed, project_root, timeout_hours)
    if not review:
        _block_review_prompt_failure(files_str, result)
        return StopFlowResolution(state=state, unreviewed=unreviewed, exit_code=2)
    return StopFlowResolution(state=state, unreviewed=unreviewed, review=review)


def finalize_review_stop(project_root, client_id, resolution, payload, settings):
    state = resolution.state
    unreviewed = resolution.unreviewed
    review = resolution.review
    covered_entries = get_entries_covered_by_review(review, state)
    review_id = review.get("reviewId", "")
    review_path = Path(review.get("reviewPath", ""))
    prompt_file = _review_prompt_path(project_root, client_id, review_id)
    reviewer_timeout_seconds = settings.get("reviewerTimeoutSeconds", 600)

    if is_review_complete(review_path) and is_review_clean(review_path):
        remaining = apply_completed_review(project_root, client_id, review_id, covered_entries)
        if not remaining:
            return 0
        _classify_last_assistant_message_if_enabled(project_root, client_id, payload, settings)
        block_response(
            f"Claude Auto Review: Review {review_id} completed, but {len(remaining)} file(s) still need review.",
            "New edits were made after the review was created. Another review will be generated on the next stop attempt.",
        )
        return 2
    if is_review_complete(review_path):
        _classify_last_assistant_message_if_enabled(project_root, client_id, payload, settings)
        block_completed_review_findings(project_root, client_id, review_id, review_path, unreviewed, settings)
        return 2

    user_prompt = build_review_completion_prompt(review_path)
    if attempt_stop_autocomplete(
        project_root,
        client_id,
        review_id,
        review_path,
        prompt_file,
        covered_entries,
        user_prompt,
        reviewer_timeout_seconds=reviewer_timeout_seconds,
    ):
        return 0

    if is_review_complete(review_path) and not is_review_clean(review_path):
        _classify_last_assistant_message_if_enabled(project_root, client_id, payload, settings)
        block_completed_review_findings(project_root, client_id, review_id, review_path, unreviewed, settings)
        return 2

    _classify_last_assistant_message_if_enabled(project_root, client_id, payload, settings)
    files_str = build_unreviewed_files_string(unreviewed)
    block_response(
        f"Claude Auto Review: Review {review_id} created for {files_str}.",
        (
            f"Review file created at:\n  {review_path}\n\n"
            "Go through each finding in the generated file and set its verdict "
            "(Confirmed, Skipped). Once all findings are resolved, "
            "stopping will be allowed."
        ),
    )
    log_event(project_root, "stop_blocked", files=[entry["file"] for entry in unreviewed])
    append_state({"type": "stop_blocked", "reason": "review_pending", "timestamp": local_now_iso()}, project_root, client_id=client_id)
    return 2
