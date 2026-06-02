from __future__ import annotations

import re
import subprocess
from pathlib import Path

from claude_auto_review.stop.reviews.runners.args import _build_opencode_review_args
from claude_auto_review.stop.reviews.runners.cli import run_review_cli
from claude_auto_review.stop.reviews.runners.preamble import (
    handle_subprocess_errors,
    resolve_cli_or_fail,
)
from claude_auto_review.stop.reviews.types.enums import AutocompleteStatus
from claude_auto_review.stop.reviews.types.request import ReviewRequest
from claude_auto_review.stop.reviews.types.result import AutocompleteResult, _process_review_result

_SAFE_RE = re.compile(r"[^A-Za-z0-9_-]")


def _write_merged_prompt(content: str, directory: Path, review_id: str) -> Path:
    safe_id = _SAFE_RE.sub("_", review_id)
    merged = directory / f"opencode-{safe_id}-merged-prompt.md"
    merged.write_text(content, encoding="utf-8", newline="\n")
    return merged


def _attempt_opencode_autocomplete(request: ReviewRequest, *, log_event_fn) -> AutocompleteResult:
    ctx = request.ctx
    review_id = request.review_id
    review_path = request.review_path
    prompt_file = request.prompt_file
    user_prompt = request.user_prompt
    reviewer_timeout_seconds = request.reviewer_timeout_seconds
    model = request.model

    opencode_cli, failure = resolve_cli_or_fail(ctx, "opencode", prompt_file, log_event_fn=log_event_fn)
    if failure is not None:
        return failure

    try:
        prompt_content = prompt_file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        log_event_fn(
            ctx.project_root,
            "stop_hook_reviewer_error",
            client_id=ctx.client_id,
            reviewId=review_id,
            backend="opencode",
            error=str(e),
        )
        return AutocompleteResult(status=AutocompleteStatus.ERROR, stderr=str(e))

    combined_prompt = f"{prompt_content}\n\n{user_prompt}" if prompt_content else user_prompt
    merged_file = _write_merged_prompt(combined_prompt, prompt_file.parent, review_id)
    try:
        args = _build_opencode_review_args(model, merged_file)
        with handle_subprocess_errors(ctx, review_id, "opencode", log_event_fn) as build_result:
            try:
                cli_result = run_review_cli(
                    opencode_cli,
                    args,
                    cwd=ctx.project_root,
                    timeout=reviewer_timeout_seconds,
                )
            except subprocess.TimeoutExpired:
                return build_result(AutocompleteStatus.TIMEOUT)
            except (OSError, ValueError, subprocess.SubprocessError) as e:
                return build_result(AutocompleteStatus.ERROR, stderr=str(e))

        return _process_review_result(ctx, cli_result, review_path, review_id, "opencode", log_event_fn=log_event_fn)
    finally:
        if merged_file is not None:
            merged_file.unlink(missing_ok=True)
