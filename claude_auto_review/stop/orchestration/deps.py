"""Dependency injection container for the stop-flow pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

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
    ApplyFinalizePlan,
    AttemptReviewAutocomplete,
    ClassifyReviewArtifact,
    EventLogger,
    FinalizeReviewStop,
    LastAssistantMessageClassifier,
    PendingReviewResolver,
    PlanForArtifactState,
    ResponseEmitter,
    ReviewerPromptScriptProvider,
    StateEventWriterProtocol,
    StateLoader,
    StopBlockCounter,
    UnreviewedFilesQuery,
)
from claude_auto_review.stop.response import StdoutResponseEmitter
from claude_auto_review.state.store.writer import StateEventWriter as _ConcreteStateEventWriter


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
    state_event_writer_factory: Callable[[Path, str], StateEventWriterProtocol] = _ConcreteStateEventWriter


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


@dataclass(frozen=True)
class EvalDeps:
    """Dependencies for the evaluate-artifact-and-plan step."""
    classify_fn: ClassifyReviewArtifact
    plan_for_artifact_state_fn: PlanForArtifactState
    apply_plan_fn: ApplyFinalizePlan
    attempt_autocomplete_fn: AttemptReviewAutocomplete
    log_event_fn: EventLogger
    state_event_writer_factory: Callable[[Path, str], StateEventWriterProtocol]
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
    state_event_writer_factory=None,
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
            state_event_writer_factory=_resolve(_ConcreteStateEventWriter, state_event_writer_factory),  # type: ignore[arg-type]
        ),
        review=ReviewDeps(
            resolve_pending_review=_resolve(resolve_pending_review, resolve_pending_review_fn),  # type: ignore[arg-type]
            get_reviewer_prompt_script=_resolve(get_reviewer_prompt_script, get_reviewer_prompt_script_fn),  # type: ignore[arg-type]
        ),
        log_event=_resolve(log_event, log_event_fn),  # type: ignore[arg-type]
        emitter=emitter or StdoutResponseEmitter(),
    ), _resolve(finalize_review_stop, finalize_review_stop_fn)  # type: ignore[arg-type]


def build_default_eval_deps(
    *,
    classify_fn=None,
    plan_for_artifact_state_fn=None,
    apply_plan_fn=None,
    attempt_autocomplete_fn=None,
    log_event_fn=None,
    state_event_writer_factory=None,
    emitter=None,
) -> EvalDeps:
    """Build EvalDeps with sensible defaults."""
    from claude_auto_review.stop.orchestration.finalize_eval import evaluate_artifact_and_plan as _eval  # noqa: F401
    from claude_auto_review.stop.orchestration.finalize_plan_executor import _apply_finalize_plan_result
    from claude_auto_review.stop.orchestration.finalize_autocomplete import _attempt_review_autocomplete
    from claude_auto_review.stop.orchestration.review_artifact_evaluator import classify_review_artifact_state
    from claude_auto_review.stop.orchestration.finalize_outcomes import plan_for_artifact_state

    return EvalDeps(
        classify_fn=_resolve(classify_review_artifact_state, classify_fn),
        plan_for_artifact_state_fn=_resolve(plan_for_artifact_state, plan_for_artifact_state_fn),
        apply_plan_fn=_resolve(_apply_finalize_plan_result, apply_plan_fn),
        attempt_autocomplete_fn=_resolve(_attempt_review_autocomplete, attempt_autocomplete_fn),
        log_event_fn=_resolve(log_event, log_event_fn),
        state_event_writer_factory=_resolve(_ConcreteStateEventWriter, state_event_writer_factory),
        emitter=emitter or StdoutResponseEmitter(),
    )
