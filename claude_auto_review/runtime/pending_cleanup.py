from __future__ import annotations

from pathlib import Path

from claude_auto_review.config.io.settings_file import load_settings
from claude_auto_review.runtime.client_dirs import client_state_path
from claude_auto_review.runtime.context import resolve_client_id, resolve_project_root
from claude_auto_review.runtime.events import log_event, log_failure
from claude_auto_review.state.records.review import ReviewMetadata
from claude_auto_review.state.reviews.expiry import is_review_expired
from claude_auto_review.state.store.read import read_jsonl_state_records
from claude_auto_review.state.store.rewrite import prune_state_records


def _collect_pending_reviews(records) -> dict[str, str]:
    latest: dict[str, str] = {}
    for record in records:
        if isinstance(record.event, ReviewMetadata) and record.event.reviewId:
            latest[record.event.reviewId] = record.event.status
    return latest


def _build_prune_predicate(latest_statuses: dict[str, str], timeout_hours: float):
    def _should_prune(event):
        return (
            isinstance(event, ReviewMetadata)
            and event.status == "pending"
            and latest_statuses.get(event.reviewId) == "pending"
            and is_review_expired(event, timeout_hours)
        )

    return _should_prune


def _execute_prune(state_path: Path, records, predicate, *, project_root, client_id) -> int:
    try:
        removed: int = prune_state_records(state_path, records, predicate)
        return removed
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


def cleanup_expired_pending_reviews(project_root=None, client_id=""):
    project_root = resolve_project_root(project_root)
    client_id = resolve_client_id(client_id)
    settings = load_settings(project_root)

    state_path = client_state_path(project_root, client_id)
    if not state_path.exists():
        return 0

    records = read_jsonl_state_records(state_path)
    latest_statuses = _collect_pending_reviews(records)
    predicate = _build_prune_predicate(latest_statuses, settings.pending_review_timeout_hours)
    removed = _execute_prune(state_path, records, predicate, project_root=project_root, client_id=client_id)

    if removed > 0:
        log_event(project_root, "expired_reviews_cleaned", count=removed)
    return removed
