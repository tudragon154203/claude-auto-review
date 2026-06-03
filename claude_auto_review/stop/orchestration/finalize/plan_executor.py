from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from claude_auto_review.review.completion import apply_completed_review, record_completed_review
from claude_auto_review.runtime.events import log_event
from claude_auto_review.stop.feedback import block_completed_review_findings
from claude_auto_review.stop.orchestration.types.context import ResponsePayload, RuntimeContext
from claude_auto_review.stop.orchestration.finalize.outcomes import FinalizeEffect, approved_result, plan_for_partial_review
from claude_auto_review.stop.orchestration.types.resolution import FinalizeAction, FinalizeResult
from claude_auto_review.stop.orchestration.finalize.payloads import _approve_payload, _partial_review_payload
from claude_auto_review.stop.orchestration.types.protocols import StateEventWriterProtocol
from claude_auto_review.stop.response import ResponseEmitter


def _apply_completed_clean_review_result(
    ctx: RuntimeContext, review_id: str, covered_entries: list[Any]
) -> tuple[FinalizeResult, ResponsePayload]:
    remaining = apply_completed_review(ctx.project_root, ctx.client_id, review_id, covered_entries)
    if not remaining:
        log_event(
            ctx.project_root,
            "stop_approved",
            client_id=ctx.client_id,
            reason=FinalizeAction.APPROVED,
            reviewId=review_id,
        )
        return approved_result(), _approve_payload(review_id)
    return plan_for_partial_review().result, _partial_review_payload(review_id, len(remaining))


def _record_findings_block(
    ctx: RuntimeContext,
    plan: Any,
    review_id: str,
    review_path: Path,
    covered_entries: list[Any],
    unreviewed: list[Any],
    *,
    state_event_writer: StateEventWriterProtocol,
    emitter: ResponseEmitter,
) -> tuple[FinalizeResult, ResponsePayload | None]:
    record_completed_review(ctx.project_root, ctx.client_id, review_id, covered_entries)
    findings_result = block_completed_review_findings(ctx, review_id, review_path, unreviewed, emitter=emitter)
    state_event_writer.append(findings_result.state_record)
    return plan.result, None


def _handle_apply_completed_clean_review(
    ctx: RuntimeContext, plan: Any, review_id: str, review_path: Path, covered_entries: list[Any], unreviewed: list[Any], *, state_event_writer: StateEventWriterProtocol, emitter: ResponseEmitter | None = None, **kw: Any
) -> tuple[FinalizeResult, ResponsePayload]:
    return _apply_completed_clean_review_result(ctx, review_id, covered_entries)


def _handle_record_findings_block(
    ctx: RuntimeContext, plan: Any, review_id: str, review_path: Path, covered_entries: list[Any], unreviewed: list[Any], *, state_event_writer: StateEventWriterProtocol, emitter: ResponseEmitter | None = None, **kw: Any
) -> tuple[FinalizeResult, ResponsePayload | None]:
    assert emitter is not None, "emitter required for RECORD_FINDINGS_BLOCK"
    return _record_findings_block(ctx, plan, review_id, review_path, covered_entries, unreviewed, state_event_writer=state_event_writer, emitter=emitter)


_EFFECT_DISPATCH: dict[FinalizeEffect, Callable[..., tuple[FinalizeResult, ResponsePayload | None]]] = {
    FinalizeEffect.APPLY_COMPLETED_CLEAN_REVIEW: _handle_apply_completed_clean_review,
    FinalizeEffect.RECORD_FINDINGS_BLOCK: _handle_record_findings_block,
}


def register_finalize_effect_handler(
    effect: FinalizeEffect,
    handler: Callable[..., tuple[FinalizeResult, ResponsePayload | None]],
) -> None:
    """Register a custom finalize effect handler."""
    _EFFECT_DISPATCH[effect] = handler


def apply_finalize_plan_result(
    ctx: RuntimeContext, plan: Any, review_id: str, review_path: Path, covered_entries: list[Any], unreviewed: list[Any], *, state_event_writer: StateEventWriterProtocol, emitter: ResponseEmitter | None = None
) -> tuple[FinalizeResult, ResponsePayload | None]:
    handler = _EFFECT_DISPATCH.get(plan.effect)
    if handler is None:
        raise ValueError(f"Unsupported finalize plan effect: {plan.effect}")
    return handler(ctx, plan, review_id, review_path, covered_entries, unreviewed, state_event_writer=state_event_writer, emitter=emitter)
