"""Dependency injection container for the stop-flow pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from claude_auto_review.paths.path_utils import get_reviewer_prompt_script
from claude_auto_review.runtime.events import log_event
from claude_auto_review.state.store.queries import consecutive_stop_blocks, get_unreviewed_files
from claude_auto_review.state.store.read import load_state_snapshot
from claude_auto_review.state.store.writer import StateEventWriter as _ConcreteStateEventWriter
from claude_auto_review.stop.classifier.last_assistant_message import classify_last_assistant_message
from claude_auto_review.stop.orchestration.finalize.core import finalize_review_stop
from claude_auto_review.stop.orchestration.finalize.pending import resolve_pending_review
from claude_auto_review.stop.orchestration.types.protocols import (
    ApplyFinalizePlan,
    AttemptReviewAutocomplete,
    AutocompleteDeps,
    ClassifierPersistFactory,
    ClassifyReviewArtifact,
    EventLogger,
    FinalizeReviewStop,
    LastAssistantMessageClassifier,
    PendingReviewResolver,
    PlanForArtifactState,
    ResponseEmitter,
    ReviewClassifierDeps,
    ReviewEvalDeps,
    ReviewExecutorDeps,
    ReviewPlannerDeps,
    ReviewerPromptScriptProvider,
    StateEventWriterProtocol,
    StateLoader,
    StopBlockCounter,
    UnreviewedFilesQuery,
)
from claude_auto_review.stop.orchestration.types.context import (
    CircuitBreakerDetails,
    ClassifierDetails,
    FinalizeDetails,
    RuntimeContext,
)
from claude_auto_review.stop.orchestration.types.resolution import ReviewResolution, TerminalResolution
from claude_auto_review.stop.orchestration.pipeline.stages import _build_classifier_result_persistor


@dataclass(frozen=True)
class StateDeps:
    load_state_snapshot: StateLoader
    get_unreviewed_files: UnreviewedFilesQuery
    consecutive_stop_blocks: StopBlockCounter


@dataclass(frozen=True)
class ClassifierDeps:
    classify_last_assistant_message: LastAssistantMessageClassifier
    classifier_persist_factory: ClassifierPersistFactory


@dataclass(frozen=True)
class ReviewDeps:
    resolve_pending_review: PendingReviewResolver
    get_reviewer_prompt_script: ReviewerPromptScriptProvider


@dataclass(frozen=True)
class StopFlowDependencies:
    state: StateDeps
    classifier: ClassifierDeps
    review: ReviewDeps
    log_event: EventLogger
    emitter: ResponseEmitter
    finalize_review_stop: FinalizeReviewStop


def _resolve(default, override):
    return override if override is not None else default


def _default_eval_fns():
    """Resolve default functions for review eval deps.

    Imports are deferred to allow test patching at source modules.
    """
    from claude_auto_review.stop.orchestration.finalize.autocomplete import attempt_review_autocomplete
    from claude_auto_review.stop.orchestration.finalize.outcomes import plan_for_artifact_state
    from claude_auto_review.stop.orchestration.finalize.plan_executor import apply_finalize_plan_result
    from claude_auto_review.stop.orchestration.finalize.review_artifact_evaluator import classify_review_artifact
    return classify_review_artifact, plan_for_artifact_state, apply_finalize_plan_result, attempt_review_autocomplete


def _default_classifier_persist_factory(ctx):
    return _build_classifier_result_persistor(ctx, writer_factory=_ConcreteStateEventWriter)


def build_default_dependencies(
    *,
    emitter: ResponseEmitter,
    load_state_snapshot_fn=None,
    get_unreviewed_files_fn=None,
    consecutive_stop_blocks_fn=None,
    classify_last_assistant_message_fn=None,
    classifier_persist_factory=None,
    resolve_pending_review_fn=None,
    get_reviewer_prompt_script_fn=None,
    log_event_fn=None,
    finalize_review_stop_fn=None,
):
    deps = StopFlowDependencies(
        state=StateDeps(
            load_state_snapshot=_resolve(load_state_snapshot, load_state_snapshot_fn),
            get_unreviewed_files=_resolve(get_unreviewed_files, get_unreviewed_files_fn),
            consecutive_stop_blocks=_resolve(consecutive_stop_blocks, consecutive_stop_blocks_fn),
        ),
        classifier=ClassifierDeps(
            classify_last_assistant_message=_resolve(
                classify_last_assistant_message,
                classify_last_assistant_message_fn,
            ),
            classifier_persist_factory=_resolve(
                _default_classifier_persist_factory,
                classifier_persist_factory,
            ),
        ),
        review=ReviewDeps(
            resolve_pending_review=_resolve(resolve_pending_review, resolve_pending_review_fn),
            get_reviewer_prompt_script=_resolve(get_reviewer_prompt_script, get_reviewer_prompt_script_fn),
        ),
        log_event=_resolve(log_event, log_event_fn),
        emitter=emitter,
        finalize_review_stop=_resolve(finalize_review_stop, finalize_review_stop_fn),
    )
    return deps


def build_default_eval_deps(
    *,
    emitter: ResponseEmitter,
    state_event_writer_factory: Callable[[Path, str], StateEventWriterProtocol],
    classify_fn=None,
    plan_for_artifact_state_fn=None,
    apply_plan_fn=None,
    attempt_autocomplete_fn=None,
    log_event_fn=None,
):
    defaults = _default_eval_fns()
    _classify_fn, _plan_fn, _apply_fn, _attempt_fn = defaults
    _log = _resolve(log_event, log_event_fn)

    return ReviewEvalDeps(
        classifier=ReviewClassifierDeps(
            classify_fn=_resolve(_classify_fn, classify_fn),
        ),
        planner=ReviewPlannerDeps(
            plan_for_artifact_state_fn=_resolve(_plan_fn, plan_for_artifact_state_fn),
        ),
        executor=ReviewExecutorDeps(
            apply_plan_fn=_resolve(_apply_fn, apply_plan_fn),
            state_event_writer_factory=state_event_writer_factory,
            emitter=emitter,
        ),
        autocomplete=AutocompleteDeps(
            attempt_autocomplete_fn=_resolve(_attempt_fn, attempt_autocomplete_fn),
            log_event_fn=_log,
        ),
    )
