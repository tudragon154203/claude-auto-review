"""Dependency injection container for the stop-flow pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from claude_auto_review.paths.path_utils import get_reviewer_prompt_script
from claude_auto_review.runtime.events import log_event
from claude_auto_review.state.store.queries import consecutive_stop_blocks, get_unreviewed_files
from claude_auto_review.state.store.read import load_state_snapshot
from claude_auto_review.state.store.writer import StateEventWriter as _ConcreteStateEventWriter
from claude_auto_review.stop.classifier.last_assistant_message import classify_last_assistant_message
from claude_auto_review.stop.orchestration.finalize.core import finalize_review_stop
from claude_auto_review.stop.orchestration.finalize.pending import resolve_pending_review
from claude_auto_review.stop.orchestration.types.protocols import (
    AutocompleteDeps,
    ClassifierPersistFactory,
    EventLogger,
    FinalizeReviewStop,
    LastAssistantMessageClassifier,
    PendingReviewResolver,
    ResponseEmitter,
    ReviewClassifierDeps,
    ReviewEvalDeps,
    ReviewExecutorDeps,
    ReviewPlannerDeps,
    ReviewerPromptScriptProvider,
    StateLoader,
    StopBlockCounter,
    UnreviewedFilesQuery,
)


@dataclass(frozen=True)
class DependencyOverrides:
    emitter: ResponseEmitter | None = None
    load_state_snapshot_fn: Callable | None = None
    get_unreviewed_files_fn: Callable | None = None
    consecutive_stop_blocks_fn: Callable | None = None
    classify_last_assistant_message_fn: Callable | None = None
    classifier_persist_factory: Callable | None = None
    resolve_pending_review_fn: Callable | None = None
    get_reviewer_prompt_script_fn: Callable | None = None
    log_event_fn: EventLogger | None = None
    finalize_review_stop_fn: Callable | None = None
    state_event_writer_factory: Callable | None = None
    eval_classify_fn: Callable | None = None
    eval_plan_fn: Callable | None = None
    eval_apply_fn: Callable | None = None
    eval_attempt_fn: Callable | None = None


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


def _resolve_overrides_field(default_fn: Callable, override: Callable | None) -> Callable:
    return override if override is not None else default_fn


def _resolve_log_fn(default: Callable[..., Any], override: EventLogger | None) -> EventLogger:
    return override if override is not None else default  # type: ignore[return-value]


def _default_eval_fns():
    """Resolve default functions for review eval deps.

    Imports are deferred to allow test patching at source modules.
    """
    from claude_auto_review.stop.orchestration.finalize.autocomplete import attempt_review_autocomplete
    from claude_auto_review.stop.orchestration.finalize.outcomes import plan_for_artifact_state
    from claude_auto_review.stop.orchestration.finalize.plan_executor import apply_finalize_plan_result
    from claude_auto_review.stop.orchestration.finalize.review_artifact_evaluator import classify_review_artifact
    return classify_review_artifact, plan_for_artifact_state, apply_finalize_plan_result, attempt_review_autocomplete


from claude_auto_review.stop.orchestration.pipeline.stages import _build_classifier_result_persistor


def _default_classifier_persist_factory(ctx):
    return _build_classifier_result_persistor(ctx, writer_factory=lambda p, c: _ConcreteStateEventWriter(p, c))


def build_default_dependencies(
    overrides: DependencyOverrides,
    *,
    emitter: ResponseEmitter,
):
    return StopFlowDependencies(
        state=StateDeps(
            load_state_snapshot=_resolve_overrides_field(load_state_snapshot, overrides.load_state_snapshot_fn),
            get_unreviewed_files=_resolve_overrides_field(get_unreviewed_files, overrides.get_unreviewed_files_fn),
            consecutive_stop_blocks=_resolve_overrides_field(consecutive_stop_blocks, overrides.consecutive_stop_blocks_fn),
        ),
        classifier=ClassifierDeps(
            classify_last_assistant_message=_resolve_overrides_field(
                classify_last_assistant_message,
                overrides.classify_last_assistant_message_fn,
            ),
            classifier_persist_factory=_resolve_overrides_field(
                _default_classifier_persist_factory,
                overrides.classifier_persist_factory,
            ),
        ),
        review=ReviewDeps(
            resolve_pending_review=_resolve_overrides_field(resolve_pending_review, overrides.resolve_pending_review_fn),
            get_reviewer_prompt_script=_resolve_overrides_field(get_reviewer_prompt_script, overrides.get_reviewer_prompt_script_fn),
        ),
        log_event=_resolve_overrides_field(log_event, overrides.log_event_fn),
        emitter=emitter,
        finalize_review_stop=_resolve_overrides_field(finalize_review_stop, overrides.finalize_review_stop_fn),
    )


def _make_state_writer_factory(overrides: DependencyOverrides):
    if overrides.state_event_writer_factory is not None:
        return overrides.state_event_writer_factory
    return lambda p, c: _ConcreteStateEventWriter(p, c)


def build_default_eval_deps(
    overrides: DependencyOverrides,
    *,
    emitter: ResponseEmitter,
):
    defaults = _default_eval_fns()
    _classify_fn, _plan_fn, _apply_fn, _attempt_fn = defaults

    return ReviewEvalDeps(
        classifier=ReviewClassifierDeps(
            classify_fn=overrides.eval_classify_fn or _classify_fn,
        ),
        planner=ReviewPlannerDeps(
            plan_for_artifact_state_fn=overrides.eval_plan_fn or _plan_fn,
        ),
        executor=ReviewExecutorDeps(
            apply_plan_fn=overrides.eval_apply_fn or _apply_fn,
            state_event_writer_factory=_make_state_writer_factory(overrides),
            emitter=emitter,
        ),
        autocomplete=AutocompleteDeps(
            attempt_autocomplete_fn=overrides.eval_attempt_fn or _attempt_fn,
            log_event_fn=_resolve_log_fn(log_event, overrides.log_event_fn),
        ),
    )