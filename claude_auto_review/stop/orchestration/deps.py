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
class StateDeps:
    """State-related dependencies used by the state-loading and circuit-breaker stages."""
    load_state_snapshot: StateLoader
    get_unreviewed_files: UnreviewedFilesQuery
    consecutive_stop_blocks: StopBlockCounter


@dataclass(frozen=True)
class ClassifierDeps:
    """Dependencies used by the classifier stage."""
    classify_last_assistant_message: LastAssistantMessageClassifier


@dataclass(frozen=True)
class ReviewDeps:
    """Dependencies used by the pending-review stage."""
    resolve_pending_review: PendingReviewResolver
    get_reviewer_prompt_script: ReviewerPromptScriptProvider


@dataclass(frozen=True)
class StopFlowDependencies:
    """Composite dependency container; composed of focused sub-containers."""
    state: StateDeps
    classifier: ClassifierDeps
    review: ReviewDeps
    log_event: EventLogger
    emitter: ResponseEmitter


def _resolve(default, override):
    return override if override is not None else default


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
    return StopFlowDependencies(
        state=StateDeps(
            load_state_snapshot=_resolve(load_state_snapshot, load_state_snapshot_fn),  # type: ignore[arg-type]
            get_unreviewed_files=_resolve(get_unreviewed_files, get_unreviewed_files_fn),  # type: ignore[arg-type]
            consecutive_stop_blocks=_resolve(consecutive_stop_blocks, consecutive_stop_blocks_fn),  # type: ignore[arg-type]
        ),
        classifier=ClassifierDeps(
            classify_last_assistant_message=_resolve(classify_last_assistant_message, classify_last_assistant_message_fn),  # type: ignore[arg-type]
        ),
        review=ReviewDeps(
            resolve_pending_review=_resolve(resolve_pending_review, resolve_pending_review_fn),  # type: ignore[arg-type]
            get_reviewer_prompt_script=_resolve(get_reviewer_prompt_script, get_reviewer_prompt_script_fn),  # type: ignore[arg-type]
        ),
        log_event=_resolve(log_event, log_event_fn),  # type: ignore[arg-type]
        emitter=emitter or StdoutResponseEmitter(),
    ), _resolve(finalize_review_stop, finalize_review_stop_fn)  # type: ignore[arg-type]
