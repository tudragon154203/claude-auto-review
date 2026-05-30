"""Fine-grained protocols for stop-flow dependency injection."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from claude_auto_review.state.snapshot import StateSnapshot
from claude_auto_review.stop.orchestration.context import RuntimeContext


@runtime_checkable
class StateLoader(Protocol):
    def __call__(self, project_root: str | Path | None = ..., client_id: str | None = ...) -> StateSnapshot: ...


@runtime_checkable
class UnreviewedFilesQuery(Protocol):
    def __call__(self, snapshot: StateSnapshot) -> list: ...


@runtime_checkable
class StopBlockCounter(Protocol):
    def __call__(self, snapshot: StateSnapshot) -> int: ...


@runtime_checkable
class LastAssistantMessageClassifier(Protocol):
    def __call__(self, ctx: RuntimeContext, env: Any = ..., urlopen: Any = ...) -> Any: ...


@runtime_checkable
class PendingReviewResolver(Protocol):
    def __call__(self, ctx: RuntimeContext, state: list, unreviewed: list, timeout_hours: float, review_prompt_script: Any) -> Any: ...


@runtime_checkable
class ReviewerPromptScriptProvider(Protocol):
    def __call__(self) -> Any: ...


@runtime_checkable
class EventLogger(Protocol):
    def __call__(self, project_root: str | Path, event_type: str, client_id: str | None = ..., **kwargs: Any) -> Any: ...


@runtime_checkable
class FinalizeReviewStop(Protocol):
    def __call__(self, ctx: RuntimeContext, resolution: Any) -> Any: ...
