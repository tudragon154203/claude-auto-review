from claude_auto_review.runtime.client_dirs import client_state_path
from claude_auto_review.runtime.context import resolve_client_id, resolve_project_root
from claude_auto_review.runtime.events import log_event, log_failure
from claude_auto_review.config.settings import load_settings
from claude_auto_review.state.models import ReviewMetadata
from claude_auto_review.state.review_expiry import is_review_expired
from claude_auto_review.state.parsing import parse_event
from claude_auto_review.state.store_read import read_jsonl_records


def _latest_review_statuses(entries):
    latest = {}
    for _, entry in entries:
        parsed = parse_event(entry) if isinstance(entry, dict) else None
        if not isinstance(parsed, ReviewMetadata):
            continue
        review_id = parsed.reviewId
        if review_id:
            latest[review_id] = parsed.status
    return latest


def cleanup_expired_pending_reviews(project_root=None, client_id=""):
    project_root = resolve_project_root(project_root)
    client_id = resolve_client_id(client_id)
    settings = load_settings(project_root)
    timeout_hours = float(settings.get("pendingReviewTimeoutHours", 1))

    state_path = client_state_path(project_root, client_id)
    if not state_path.exists():
        return 0

    raw_entries = read_jsonl_records(state_path)
    latest_statuses = _latest_review_statuses(raw_entries)

    entries = []
    removed = 0
    for line, entry in raw_entries:
        if entry is None:
            entries.append(line)
            continue
        parsed = parse_event(entry) if isinstance(entry, dict) else None
        if (
            isinstance(parsed, ReviewMetadata)
            and parsed.status == "pending"
            and latest_statuses.get(parsed.reviewId) == "pending"
            and is_review_expired(parsed, timeout_hours)
        ):
            removed += 1
            continue
        entries.append(line)

    if removed > 0:
        try:
            with state_path.open("w", encoding="utf-8", newline="\n") as handle:
                handle.write("\n".join(entries) + "\n")
        except OSError as error:
            log_failure(
                project_root,
                "runtime_cleanup_failed",
                error,
                operation="rewrite_state",
                target=str(state_path),
            )
            return 0
        log_event(project_root, "expired_reviews_cleaned", count=removed)
    return removed
