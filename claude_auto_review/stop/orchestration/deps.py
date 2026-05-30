"""Dependency injection container for the stop-flow pipeline."""

from __future__ import annotations

from dataclasses import dataclass

from claude_auto_review.paths.path_utils import get_reviewer_prompt_script
from claude_auto_review.runtime.events import log_event
from claude_auto_review.state.store.queries import (
    consecutive_stop_blocks,
    get_unreviewed_files,
)
from claude_auto_review.state.store.read import load_state_snapshot
from claude_auto_review.stop.classifier.last_assistant_message import (
    classify_last_assistant_message,
)
from claude_auto_review.stop.orchestration.pending import resolve_pending_review
from claude_auto_review.stop.orchestration.finalize import finalize_review_stop
from claude_auto_review.stop.orchestration.protocols import (
    EventLogger,
    FinalizeReviewStop,
    LastAssistantMessageClassifier,
    PendingReviewResolver,
    ResponseEmitter,
    ReviewerPromptScriptProvider,
    StateLoader,
    StopBlockCounter,
    UnreviewedFilesQuery,
)
from claude_auto_review.stop.response import StdoutResponseEmitter


@dataclass(frozen=True)
class StopFlowDependencies:
    load_state_snapshot: StateLoader
    get_unreviewed_files: UnreviewedFilesQuery
    consecutive_stop_blocks: StopBlockCounter
    classify_last_assistant_message: LastAssistantMessageClassifier
    resolve_pending_review: PendingReviewResolver
    get_reviewer_prompt_script: ReviewerPromptScriptProvider
    log_event: EventLogger
    emitter: ResponseEmitter


def build_default_dependencies(
    *,
    load_state_snapshot_fn=None,
    get_unreviewed_files_fn=None,
    consecutive_stop_blocks_fn=None,
    classify_last_assistant_message_fn=None,
    resolve_pending_review_fn=None,
    get_reviewer_prompt_script_fn=None,
    log_event_fn=None,
    finalize_review_stop_fn=None,
    emitter=None,
) -> tuple[StopFlowDependencies, FinalizeReviewStop]:
    """Build StopFlowDependencies with sensible defaults and return (deps, finalize_fn)."""
    emitter = emitter or StdoutResponseEmitter()
    return StopFlowDependencies(
        load_state_snapshot=load_state_snapshot_fn if load_state_snapshot_fn is not None else load_state_snapshot,  # type: ignore[arg-type]
        get_unreviewed_files=get_unreviewed_files_fn if get_unreviewed_files_fn is not None else get_unreviewed_files,  # type: ignore[arg-type]
        consecutive_stop_blocks=consecutive_stop_blocks_fn if consecutive_stop_blocks_fn is not None else consecutive_stop_blocks,  # type: ignore[arg-type]
        classify_last_assistant_message=classify_last_assistant_message_fn if classify_last_assistant_message_fn is not None else classify_last_assistant_message,  # type: ignore[arg-type]
        resolve_pending_review=resolve_pending_review_fn if resolve_pending_review_fn is not None else resolve_pending_review,  # type: ignore[arg-type]
        get_reviewer_prompt_script=get_reviewer_prompt_script_fn if get_reviewer_prompt_script_fn is not None else get_reviewer_prompt_script,  # type: ignore[arg-type]
        log_event=log_event_fn if log_event_fn is not None else log_event,  # type: ignore[arg-type]
        emitter=emitter,
    ), finalize_review_stop_fn if finalize_review_stop_fn is not None else finalize_review_stop  # type: ignore[arg-type]
