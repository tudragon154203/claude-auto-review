import json
import sys
from pathlib import Path

from claude_auto_review.paths import local_now_iso
from claude_auto_review.settings import DEFAULT_SETTINGS
from claude_auto_review.state.store_write import append_state, log_event


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
