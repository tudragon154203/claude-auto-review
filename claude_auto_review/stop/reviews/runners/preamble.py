"""Shared CLI-discovery + prompt-validation preamble for backend runners.

Eliminates the duplicated ``shutil.which``/``prompt_file.is_file`` boilerplate
that was copy-pasted across ``claude.py``, ``codex.py``, and ``opencode.py``.
"""

from __future__ import annotations

import shutil
import subprocess
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Any, Callable

from claude_auto_review.stop.reviews.types.enums import AutocompleteStatus
from claude_auto_review.stop.reviews.types.result import AutocompleteResult

LogEventFn = Callable[..., Any]
_BuildFn = Callable[..., AutocompleteResult]


def resolve_cli_or_fail(
    ctx,
    backend_name: str,
    prompt_file: Path,
    *,
    log_event_fn: LogEventFn,
) -> tuple[str | None, AutocompleteResult | None]:
    """Locate the backend CLI on PATH and confirm the prompt file exists.

    Returns ``(cli_path, None)`` on success. On failure, returns
    ``(None, AutocompleteResult)`` describing the missing prerequisite.
    """
    cli_path = shutil.which(backend_name)
    if not cli_path:
        log_event_fn(
            ctx.project_root,
            "stop_hook_reviewer_not_found",
            client_id=ctx.client_id,
            backend=backend_name,
        )
        return None, AutocompleteResult(status=AutocompleteStatus.CLI_NOT_FOUND)
    if not prompt_file.is_file():
        log_event_fn(
            ctx.project_root,
            "stop_hook_prompt_not_found",
            client_id=ctx.client_id,
            path=str(prompt_file),
        )
        return None, AutocompleteResult(status=AutocompleteStatus.PROMPT_NOT_FOUND)
    return cli_path, None


def handle_subprocess_errors(
    ctx,
    review_id: str,
    backend_name: str,
    log_event_fn: LogEventFn,
) -> AbstractContextManager[_BuildFn]:
    """Return a context manager that translates subprocess failures into AutocompleteResult.

    Usage::

        with handle_subprocess_errors(ctx, review_id, "claude", log_event_fn) as get_result:
            try:
                cli_result = run_review_cli(...)
            except subprocess.TimeoutExpired:
                return get_result(AutocompleteStatus.TIMEOUT)
            except (OSError, ValueError, subprocess.SubprocessError) as e:
                return get_result(AutocompleteStatus.ERROR, stderr=str(e))
    """

    class _Handler:
        def __enter__(self) -> _BuildFn:
            return self._build

        def __exit__(self, exc_type, exc, tb):
            return False

        def _build(self, status: AutocompleteStatus, *, stderr: str | None = None) -> AutocompleteResult:
            if status == AutocompleteStatus.TIMEOUT:
                log_event_fn(
                    ctx.project_root,
                    "stop_hook_reviewer_timeout",
                    client_id=ctx.client_id,
                    reviewId=review_id,
                    backend=backend_name,
                )
                return AutocompleteResult(status=status)
            log_event_fn(
                ctx.project_root,
                "stop_hook_reviewer_error",
                client_id=ctx.client_id,
                reviewId=review_id,
                backend=backend_name,
                error=stderr or "",
            )
            return AutocompleteResult(status=status, stderr=stderr or "")

    return _Handler()
