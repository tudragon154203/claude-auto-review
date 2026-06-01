"""Fine-grained protocols for stop-flow dependency injection."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Protocol, runtime_checkable

from claude_auto_review.state.event_types import StateEvent
from claude_auto_review.state.snapshot import StateSnapshot
from claude_auto_review.stop.classifier.models import AssistantMessageClassificationResult
from claude_auto_review.stop.orchestration.context import ResponsePayload, RuntimeContext
from claude_auto_review.stop.orchestration.resolution import FinalizeResult, ReviewResolution
from claude_auto_review.state.edit_record import EditRecord
from claude_auto_review.stop.response import ResponseEmitter
from claude_auto_review.stop.orchestration.finalize_outcomes import FinalizePlan
from claude_auto_review.stop.orchestration.review_artifact_evaluator import ReviewArtifactState


@runtime_checkable
class StateLoader(Protocol):
    def __call__(self, project_root: str | Path | None = ..., client_id: str | None = ...) -> StateSnapshot: ...


@runtime_checkable
class UnreviewedFilesQuery(Protocol):
    def __call__(self, snapshot: StateSnapshot) -> list[EditRecord]: ...


@runtime_checkable
class StopBlockCounter(Protocol):
    def __call__(self, snapshot: StateSnapshot) -> int: ...


@runtime_checkable
class LastAssistantMessageClassifier(Protocol):
    def __call__(
        self, ctx: RuntimeContext, env: dict[str, str] | None = ...,
        urlopen: Callable[..., Any] | None = ...,
        *, persist: Callable[[AssistantMessageClassificationResult], None] | None = ...,
    ) -> AssistantMessageClassificationResult | None: ...


@runtime_checkable
class PendingReviewResolver(Protocol):
    def __call__(
        self,
        ctx: RuntimeContext,
        state: list[StateEvent],
        unreviewed: list[EditRecord],
        timeout_hours: float,
        review_prompt_script: Path | str,
        *,
        emitter: ResponseEmitter,
        log_event_fn: Callable[..., Any] | None = None,
    ) -> ReviewResolution | None: ...


@runtime_checkable
class ReviewerPromptScriptProvider(Protocol):
    def __call__(self) -> Path | str: ...


@runtime_checkable
class EventLogger(Protocol):
    def __call__(self, project_root: str | Path, event_type: str, client_id: str | None = ..., **kwargs: Any) -> None: ...


@runtime_checkable
class FinalizeReviewStop(Protocol):
    def __call__(self, ctx: RuntimeContext, resolution: ReviewResolution, *, deps: Any) -> int: ...


@runtime_checkable
class StateEventWriterProtocol(Protocol):
    def append(self, event: StateEvent) -> None: ...


@runtime_checkable
class ClassifyReviewArtifact(Protocol):
    def __call__(self, review_path: Path, *, minimum_blocking_severity: str = ..., client_id: str | None = ...) -> ReviewArtifactState: ...


@runtime_checkable
class PlanForArtifactState(Protocol):
    def __call__(self, artifact_state: ReviewArtifactState) -> FinalizePlan | None: ...


@runtime_checkable
class ApplyFinalizePlan(Protocol):
    def __call__(
        self,
        ctx: RuntimeContext,
        plan: FinalizePlan,
        review_id: str,
        review_path: Path,
        covered_entries: list[Any],
        unreviewed: list[Any],
        *,
        state_event_writer: StateEventWriterProtocol,
        emitter: ResponseEmitter,
    ) -> tuple[FinalizeResult, ResponsePayload | None]: ...


@runtime_checkable
class AttemptReviewAutocomplete(Protocol):
    def __call__(
        self,
        ctx: RuntimeContext,
        review_id: str,
        review_path: Path,
        prompt_file: Path,
        *,
        log_event_fn: Callable[..., Any] | None = None,
    ) -> Any: ...

