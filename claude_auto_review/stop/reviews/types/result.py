from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from claude_auto_review.runtime.events import log_event as _default_log_event
from collections.abc import Callable

from claude_auto_review.state.reviews.normalization import normalize_review_verdict_content
from claude_auto_review.stop.orchestration.types.context import RuntimeContext
from claude_auto_review.stop.reviews.types.enums import AutocompleteStatus


@dataclass(frozen=True)
class AutocompleteResult:
    status: str
    stdout: str = ""
    stderr: str = ""
    returncode: int | None = None

    @property
    def output_written(self):
        return self.status == AutocompleteStatus.OUTPUT_WRITTEN



def normalize_and_write_review(
    raw_stdout: str,
    review_path: Path,
    *,
    client_id: str,
    minimum_blocking_severity: str,
) -> str:
    """Normalize review verdict content and write the result to disk.

    Returns the normalized output string.
    """
    normalized = normalize_review_verdict_content(
        raw_stdout,
        client_id=client_id,
        minimum_blocking_severity=minimum_blocking_severity,
    )
    normalized_text = normalized or ""
    review_path.write_text(normalized_text, encoding="utf-8", newline="\n")
    return normalized_text


def _process_review_result(ctx: RuntimeContext, result, review_path, review_id, backend, *, log_event_fn) -> AutocompleteResult:
    _log = log_event_fn
    stdout_len = len(result.stdout) if result.stdout else 0
    _log(
        ctx.project_root,
        "stop_hook_reviewer_done",
        client_id=ctx.client_id,
        backend=backend,
        returncode=result.returncode,
        stdout_len=stdout_len,
        stdout=result.stdout[:500] if result.stdout else "",
        stderr=result.stderr[:500] if result.stderr else "",
    )

    if result.returncode != 0:
        _log(
            ctx.project_root,
            "stop_hook_reviewer_nonzero",
            client_id=ctx.client_id,
            backend=backend,
            returncode=result.returncode,
            reviewId=review_id,
            stderr=result.stderr[:500] if result.stderr else "",
        )
        return AutocompleteResult(
            status=AutocompleteStatus.NONZERO,
            stdout=result.stdout or "",
            stderr=result.stderr or "",
            returncode=result.returncode,
        )

    if not result.stdout.strip():
        _log(
            ctx.project_root,
            "stop_hook_reviewer_empty",
            client_id=ctx.client_id,
            backend=backend,
            reviewId=review_id,
            stdout_len=stdout_len,
            stderr=result.stderr[:500] if result.stderr else "",
        )
        return AutocompleteResult(
            status=AutocompleteStatus.EMPTY_STDOUT,
            stdout=result.stdout or "",
            stderr=result.stderr or "",
            returncode=result.returncode,
        )

    normalized_output = normalize_and_write_review(
        result.stdout,
        Path(review_path),
        client_id=ctx.client_id,
        minimum_blocking_severity=ctx.settings.flow.minimum_blocking_severity,
    )
    _log(
        ctx.project_root,
        "stop_hook_reviewer_output_written",
        client_id=ctx.client_id,
        backend=backend,
        reviewId=review_id,
        stdout_len=stdout_len,
    )
    return AutocompleteResult(
        status=AutocompleteStatus.OUTPUT_WRITTEN,
        stdout=normalized_output or "",
        stderr=result.stderr or "",
        returncode=result.returncode,
    )
