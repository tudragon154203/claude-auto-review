from claude_auto_review.path_utils import local_now_iso
from claude_auto_review.state.models import StopBlockedRecord
from claude_auto_review.state.store_write import append_state
from claude_auto_review.stop.orchestration.context import RuntimeContext
from claude_auto_review.stop.feedback import block_response, build_unreviewed_files_string


def _display_path(path, project_root):
    try:
        return path.relative_to(project_root).as_posix()
    except ValueError:
        return str(path)


def complete_clean_review(ctx: RuntimeContext, review_id, covered_entries, apply_completed_review):
    remaining = apply_completed_review(ctx.project_root, ctx.client_id, review_id, covered_entries)
    if not remaining:
        return 0
    block_response(
        f"Claude Auto Review: Review {review_id} completed, but {len(remaining)} file(s) still need review.",
        "New edits were made after the review was created. Another review will be generated on the next stop attempt.",
    )
    return 2


def block_pending_review(ctx: RuntimeContext, review_id, review_path, prompt_path, unreviewed):
    files_str = build_unreviewed_files_string(unreviewed)
    review_path_rel = _display_path(review_path, ctx.project_root)
    prompt_path_rel = _display_path(prompt_path, ctx.project_root)
    block_response(
        f"Claude Auto Review: Review {review_id} created for {files_str}.",
        (
            f"Review file created at:\n  {review_path_rel}\n\n"
            "This file is only a placeholder until the review is completed.\n\n"
            f"Complete the review from:\n  {prompt_path_rel}\n\n"
            "Then write the findings into the review file and set each finding verdict "
            "(Confirmed, Skipped). Once the review verdict is no longer Pending, "
            "stopping will be allowed."
        ),
    )
    append_state(
        StopBlockedRecord(
            timestamp=local_now_iso(),
            reason="review_pending",
            files=[entry.file for entry in unreviewed],
        ),
        ctx.project_root,
        client_id=ctx.client_id,
    )
    return 2
