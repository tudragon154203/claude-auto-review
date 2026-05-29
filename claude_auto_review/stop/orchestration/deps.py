"""Dependency injection container for the stop-flow pipeline."""

from __future__ import annotations

from collections.abc import Callable
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


@dataclass(frozen=True)
class StopFlowDependencies:
    """Injectable callables for each stage of the stop-flow pipeline."""

    load_state_snapshot: Callable
    get_unreviewed_files: Callable
    consecutive_stop_blocks: Callable
    classify_last_assistant_message: Callable
    resolve_pending_review: Callable
    get_reviewer_prompt_script: Callable
    log_event: Callable


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
) -> tuple[StopFlowDependencies, Callable]:
    """Build StopFlowDependencies with sensible defaults and return (deps, finalize_fn)."""
    return StopFlowDependencies(
        load_state_snapshot=load_state_snapshot_fn or load_state_snapshot,
        get_unreviewed_files=get_unreviewed_files_fn or get_unreviewed_files,
        consecutive_stop_blocks=consecutive_stop_blocks_fn or consecutive_stop_blocks,
        classify_last_assistant_message=classify_last_assistant_message_fn or classify_last_assistant_message,
        resolve_pending_review=resolve_pending_review_fn or resolve_pending_review,
        get_reviewer_prompt_script=get_reviewer_prompt_script_fn or get_reviewer_prompt_script,
        log_event=log_event_fn or log_event,
    ), finalize_review_stop_fn or finalize_review_stop
