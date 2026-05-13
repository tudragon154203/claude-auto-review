from pathlib import Path

from claude_auto_review.paths import get_client_id
from claude_auto_review.runtime.setup import ensure_client_runtime
from claude_auto_review.settings import load_settings
from claude_auto_review.state.store_read import consecutive_stop_blocks, get_unreviewed_files, load_state
from claude_auto_review.runtime.helpers import log_event
from claude_auto_review.stop.orchestration.finalize import finalize_review_stop
from claude_auto_review.stop.orchestration.pending import resolve_pending_review


def _setting_float(settings, key, default):
    try:
        return float(settings.get(key, default))
    except (TypeError, ValueError):
        return float(default)


def _setting_int(settings, key, default):
    try:
        return int(settings.get(key, default))
    except (TypeError, ValueError):
        return int(default)


def _allow_stop(project_root, reason, **details):
    log_event(project_root, "stop_approved", reason=reason, **details)
    return 0


def run_stop_flow(project_root, payload):
    client_id = get_client_id(payload.get("session_id"))
    ensure_client_runtime(project_root, client_id)
    settings = load_settings(project_root)
    timeout_hours = _setting_float(settings, "pendingReviewTimeoutHours", 1)

    if not settings.get("enabled", True):
        log_event(project_root, "stop_disabled")
        return 0

    state = load_state(project_root, client_id)
    unreviewed = get_unreviewed_files(state)
    if not unreviewed:
        return _allow_stop(project_root, "no_unreviewed_files")

    max_passes = _setting_int(settings, "maxStopPasses", 3)
    block_count = consecutive_stop_blocks(state)
    if block_count >= max_passes:
        return _allow_stop(
            project_root,
            "circuit_breaker",
            block_count=block_count,
            max_passes=max_passes,
        )

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
