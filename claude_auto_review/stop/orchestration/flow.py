from claude_auto_review.config.io import load_settings
from claude_auto_review.paths.path_utils import get_reviewer_prompt_script
from claude_auto_review.runtime.client_dirs import get_client_id
from claude_auto_review.runtime.events import log_event
from claude_auto_review.runtime.setup import ensure_client_runtime
from claude_auto_review.state.store.read import consecutive_stop_blocks, get_unreviewed_files, load_state_snapshot
from claude_auto_review.stop.classifier.last_assistant_message import classify_last_assistant_message
from claude_auto_review.stop.orchestration.context import RuntimeContext
from claude_auto_review.stop.orchestration.finalize import finalize_review_stop
from claude_auto_review.stop.orchestration.pending import resolve_pending_review
from claude_auto_review.stop.response import approve_response


def _allow_stop(project_root, reason, client_id=None, **details):
    log_event(project_root, "stop_approved", client_id=client_id, reason=reason, **details)
    approve_response(f"Claude Auto Review: stop approved ({reason})")
    return 0


def _check_classifier_incomplete(ctx):
    if not ctx.settings.last_assistant_message_classifier_enabled:
        return None
    result = classify_last_assistant_message(ctx)
    if result is not None and result.status == "incomplete":
        return result
    return None


def run_stop_flow(project_root, payload, *, client_id=None, settings=None):
    client_id = client_id or get_client_id(payload.get("session_id"))
    ensure_client_runtime(project_root, client_id)
    settings = settings or load_settings(project_root)

    if not settings.enabled:
        log_event(project_root, "stop_disabled", client_id=client_id)
        approve_response("Claude Auto Review: stop disabled by settings")
        return 0

    timeout_hours = settings.pending_review_timeout_hours
    state_snapshot = load_state_snapshot(project_root, client_id)
    state = state_snapshot.events
    unreviewed = get_unreviewed_files(state_snapshot)
    if not unreviewed:
        return _allow_stop(project_root, "no_unreviewed_files", client_id=client_id)

    max_passes = settings.max_stop_passes
    block_count = consecutive_stop_blocks(state_snapshot)
    if block_count >= max_passes:
        return _allow_stop(
            project_root,
            "circuit_breaker",
            client_id=client_id,
            block_count=block_count,
            max_passes=max_passes,
        )

    ctx = RuntimeContext(
        project_root=project_root,
        client_id=client_id,
        settings=settings,
        payload=payload,
    )
    classifier_result = _check_classifier_incomplete(ctx)
    if classifier_result is not None:
        return _allow_stop(
            ctx.project_root,
            "classifier_incomplete",
            client_id=ctx.client_id,
            classifier_status=classifier_result.status,
            classifier_reason=classifier_result.reason,
        )

    resolution = resolve_pending_review(
        ctx,
        state,
        unreviewed,
        timeout_hours,
        get_reviewer_prompt_script(),
    )
    if resolution.is_terminal:
        return resolution.exit_code
    return finalize_review_stop(ctx, resolution)
