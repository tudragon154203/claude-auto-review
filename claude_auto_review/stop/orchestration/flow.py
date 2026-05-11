from pathlib import Path

from claude_auto_review.paths import get_client_id
from claude_auto_review.runtime.setup import ensure_client_runtime
from claude_auto_review.settings import load_settings
from claude_auto_review.state.store_read import consecutive_stop_blocks, get_unreviewed_files, load_state
from claude_auto_review.state.store_write import log_event
from claude_auto_review.stop.orchestration.finalize import finalize_review_stop
from claude_auto_review.stop.orchestration.pending import resolve_pending_review


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

    resolution = resolve_pending_review(
        project_root,
        client_id,
        payload,
        state,
        unreviewed,
        timeout_hours,
        Path(__file__).resolve().parents[2] / "review" / "prompt.py",
    )
    if resolution.is_terminal:
        return resolution.exit_code
    return finalize_review_stop(project_root, client_id, resolution, payload, settings)

