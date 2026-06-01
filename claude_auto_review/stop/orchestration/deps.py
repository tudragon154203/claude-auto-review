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
from claude_auto_review.stop.orchestration.finalize import finalize_review_stop
from claude_auto_review.stop.orchestration.pending import resolve_pending_review
from claude_auto_review.stop.orchestration.protocols import (
    ApplyFinalizePlan,
    AttemptReviewAutocomplete,
    ClassifierPersistFactory,
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
from claude_auto_review.stop.orchestration.stages import _build_classifier_result_persistor
from claude_auto_review.stop.response import StdoutResponseEmitter


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


@dataclass(frozen=True)
class EvalDeps:
    classify_fn: ClassifyReviewArtifact
    plan_for_artifact_state_fn: PlanForArtifactState
    apply_plan_fn: ApplyFinalizePlan
    attempt_autocomplete_fn: AttemptReviewAutocomplete
    log_event_fn: EventLogger
    state_event_writer_factory: Callable[[Path, str], StateEventWriterProtocol]
    emitter: ResponseEmitter


def _resolve(default, override):
    return default if override is None else override


def _default_classifier_persist_factory(ctx):
    return _build_classifier_result_persistor(ctx, writer_factory=_ConcreteStateEventWriter)


def build_default_dependencies(
    *,
    load_state_snapshot_fn=None,
    get_unreviewed_files_fn=None,
    consecutive_stop_blocks_fn=None,
    classify_last_assistant_message_fn=None,
    classifier_persist_factory=None,
    resolve_pending_review_fn=None,
    get_reviewer_prompt_script_fn=None,
    log_event_fn=None,
    emitter=None,
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
        emitter=emitter or StdoutResponseEmitter(),
        finalize_review_stop=_resolve(finalize_review_stop, finalize_review_stop_fn),
    )
    return deps, deps.finalize_review_stop


def build_default_eval_deps(
    *,
    classify_fn=None,
    plan_for_artifact_state_fn=None,
    apply_plan_fn=None,
    attempt_autocomplete_fn=None,
    log_event_fn=None,
    state_event_writer_factory=None,
    emitter=None,
):
    from claude_auto_review.stop.orchestration.finalize_autocomplete import attempt_review_autocomplete
    from claude_auto_review.stop.orchestration.finalize_outcomes import plan_for_artifact_state
    from claude_auto_review.stop.orchestration.finalize_plan_executor import apply_finalize_plan_result
    from claude_auto_review.stop.orchestration.review_artifact_evaluator import classify_review_artifact

    return EvalDeps(
        classify_fn=_resolve(classify_review_artifact, classify_fn),
        plan_for_artifact_state_fn=_resolve(plan_for_artifact_state, plan_for_artifact_state_fn),
        apply_plan_fn=_resolve(apply_finalize_plan_result, apply_plan_fn),
        attempt_autocomplete_fn=_resolve(attempt_review_autocomplete, attempt_autocomplete_fn),
        log_event_fn=_resolve(log_event, log_event_fn),
        state_event_writer_factory=_resolve(_ConcreteStateEventWriter, state_event_writer_factory),
        emitter=emitter or StdoutResponseEmitter(),
    )
