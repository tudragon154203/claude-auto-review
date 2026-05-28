from __future__ import annotations

from claude_auto_review.config.io import load_settings
from claude_auto_review.runtime.client_dirs import client_state_path
from claude_auto_review.runtime.context import resolve_client_id, resolve_project_root
from claude_auto_review.runtime.events import log_event, log_failure
from claude_auto_review.state.models import ReviewMetadata
from claude_auto_review.state.reviews.expiry import is_review_expired
from claude_auto_review.state.store.read import read_jsonl_state_records
from claude_auto_review.state.store.rewrite import prune_state_records


def _latest_review_statuses(records):
    latest = {}
    for record in records:
        if not isinstance(record.event, ReviewMetadata):
            continue
        review_id = record.event.reviewId
        if review_id:
            latest[review_id] = record.event.status
    return latest


def cleanup_expired_pending_reviews(project_root=None, client_id=""):
    project_root = resolve_project_root(project_root)
    client_id = resolve_client_id(client_id)
    settings = load_settings(project_root)
    timeout_hours = settings.pending_review_timeout_hours

    state_path = client_state_path(project_root, client_id)
    if not state_path.exists():
        return 0

    records = read_jsonl_state_records(state_path)
    latest_statuses = _latest_review_statuses(records)

    def _should_prune(event):
        return (
            isinstance(event, ReviewMetadata)
            and event.status == "pending"
            and latest_statuses.get(event.reviewId) == "pending"
            and is_review_expired(event, timeout_hours)
        )

    try:
        removed = prune_state_records(state_path, records, _should_prune)
    except OSError as error:
        log_failure(
            project_root,
            "runtime_cleanup_failed",
            error,
            client_id=client_id,
            operation="rewrite_state",
            target=str(state_path),
        )
        return 0

    if removed > 0:
        log_event(project_root, "expired_reviews_cleaned", count=removed)
    return removed
