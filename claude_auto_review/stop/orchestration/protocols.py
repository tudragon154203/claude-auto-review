"""Fine-grained protocols for stop-flow dependency injection."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from claude_auto_review.state.models import StateEvent
from claude_auto_review.state.snapshot import StateSnapshot
from claude_auto_review.stop.classifier.models import AssistantMessageClassificationResult
from claude_auto_review.stop.orchestration.context import RuntimeContext
from claude_auto_review.stop.orchestration.resolution import ReviewResolution
from claude_auto_review.state.edit_record import EditRecord
from claude_auto_review.stop.response import ResponseEmitter


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
        self, ctx: RuntimeContext, env: dict[str, str] | None = ..., urlopen: Any | None = ...
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
    ) -> ReviewResolution | None: ...


@runtime_checkable
class ReviewerPromptScriptProvider(Protocol):
    def __call__(self) -> Path | str: ...


@runtime_checkable
class EventLogger(Protocol):
    def __call__(self, project_root: str | Path, event_type: str, client_id: str | None = ..., **kwargs: Any) -> None: ...


@runtime_checkable
class FinalizeReviewStop(Protocol):
    def __call__(self, ctx: RuntimeContext, resolution: ReviewResolution, *, emitter: ResponseEmitter) -> int: ...
