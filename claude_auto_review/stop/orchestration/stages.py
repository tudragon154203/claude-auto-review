"""Individual stage functions for the stop-flow pipeline.

Each ``run_*_stage`` returns a :class:`StopDecision` when the pipeline can
terminate early, or ``None`` when it should continue to the next stage.
"""

from __future__ import annotations

from claude_auto_review.stop.classifier.enums import ClassifierStatus
from claude_auto_review.stop.orchestration.context import RuntimeContext, StopDecision
from claude_auto_review.stop.orchestration.protocols import (
    EventLogger,
    LastAssistantMessageClassifier,
    PendingReviewResolver,
    ReviewerPromptScriptProvider,
    StateLoader,
    StopBlockCounter,
    UnreviewedFilesQuery,
)
from claude_auto_review.stop.orchestration.resolution import StopDecisionKind, TerminalResolution
from claude_auto_review.stop.reviews.enums import StopAllowReason


def run_enabled_stage(ctx: RuntimeContext, *, log_event_fn: EventLogger) -> StopDecision | None:
    if ctx.settings.enabled:
        return None
    log_event_fn(ctx.project_root, "stop_disabled", client_id=ctx.client_id)
    return StopDecision(kind=StopDecisionKind.ALLOW, reason=StopAllowReason.DISABLED)


def run_state_stage(ctx: RuntimeContext, *, load_state_snapshot_fn: StateLoader, get_unreviewed_files_fn: UnreviewedFilesQuery):
    state_snapshot = load_state_snapshot_fn(ctx.project_root, ctx.client_id)
    state = state_snapshot.events
    unreviewed = get_unreviewed_files_fn(state_snapshot)
    return state_snapshot, state, unreviewed


def run_allow_no_unreviewed_stage(unreviewed) -> StopDecision | None:
    if unreviewed:
        return None
    return StopDecision(kind=StopDecisionKind.ALLOW, reason=StopAllowReason.NO_UNREVIEWED_FILES)


def run_circuit_breaker_stage(
    ctx: RuntimeContext, state_snapshot, *, consecutive_stop_blocks_fn: StopBlockCounter
) -> StopDecision | None:
    block_count = consecutive_stop_blocks_fn(state_snapshot)
    if block_count < ctx.settings.max_stop_passes:
        return None
    return StopDecision(
        kind=StopDecisionKind.ALLOW,
        reason=StopAllowReason.CIRCUIT_BREAKER,
        details={"block_count": block_count, "max_passes": ctx.settings.max_stop_passes},
    )


def run_classifier_stage(ctx: RuntimeContext, *, classify_last_assistant_message_fn: LastAssistantMessageClassifier) -> StopDecision | None:
    if not ctx.settings.last_assistant_message_classifier_enabled:
        return None
    from claude_auto_review.state.store.writer import StateEventWriter

    def _persist(result):
        StateEventWriter(project_root=ctx.project_root, client_id=ctx.client_id).append(
            result.as_state_entry(include_debug=ctx.settings.debug)
        )

    result = classify_last_assistant_message_fn(ctx, persist=_persist)
    if result is None or result.status != ClassifierStatus.INCOMPLETE:
        return None
    return StopDecision(
        kind=StopDecisionKind.ALLOW,
        reason=StopAllowReason.CLASSIFIER_INCOMPLETE,
        details={"classifier_status": result.status, "classifier_reason": result.reason},
    )


def run_pending_stage(
    ctx: RuntimeContext,
    state,
    unreviewed,
    *,
    resolve_pending_review_fn: PendingReviewResolver,
    get_reviewer_prompt_script_fn: ReviewerPromptScriptProvider,
    emitter=None,
) -> StopDecision:
    kwargs = {}
    if emitter is not None:
        kwargs["emitter"] = emitter
    resolution = resolve_pending_review_fn(
        ctx,
        state,
        unreviewed,
        ctx.settings.pending_review_timeout_hours,
        get_reviewer_prompt_script_fn(),
        **kwargs,
    )
    if isinstance(resolution, TerminalResolution):
        return StopDecision(kind=StopDecisionKind.TERMINAL, details={"exit_code": resolution.exit_code})
    return StopDecision(kind=StopDecisionKind.FINALIZE, details={"resolution": resolution})
