from claude_auto_review.paths import local_now_iso
from claude_auto_review.state.models import StopBlockedRecord
from claude_auto_review.state.store_write import append_state
from claude_auto_review.stop.orchestration.context import RuntimeContext
from claude_auto_review.stop.feedback import block_response, build_unreviewed_files_string


def complete_clean_review(ctx: RuntimeContext, review_id, covered_entries, apply_completed_review):
    remaining = apply_completed_review(ctx.project_root, ctx.client_id, review_id, covered_entries)
    if not remaining:
        return 0
    block_response(
        f"Claude Auto Review: Review {review_id} completed, but {len(remaining)} file(s) still need review.",
        "New edits were made after the review was created. Another review will be generated on the next stop attempt.",
    )
    return 2


def block_pending_review(ctx: RuntimeContext, review_id, review_path, unreviewed):
    files_str = build_unreviewed_files_string(unreviewed)
    review_path_rel = review_path.relative_to(ctx.project_root).as_posix()
    block_response(
        f"Claude Auto Review: Review {review_id} created for {files_str}.",
        (
            f"Review file created at:\n  {review_path_rel}\n\n"
            "Go through each finding in the generated file and set its verdict "
            "(Confirmed, Skipped). Once all findings are resolved, "
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