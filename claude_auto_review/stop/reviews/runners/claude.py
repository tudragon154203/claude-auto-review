from __future__ import annotations

import subprocess

from claude_auto_review.stop.reviews.runners.args import _build_claude_review_args
from claude_auto_review.stop.reviews.runners.cli import run_review_cli
from claude_auto_review.stop.reviews.runners.preamble import (
    handle_subprocess_errors,
    resolve_cli_or_fail,
)
from claude_auto_review.stop.reviews.types.enums import AutocompleteStatus
from claude_auto_review.stop.reviews.types.request import ReviewRequest
from claude_auto_review.stop.reviews.types.result import AutocompleteResult, _process_review_result


def _run_claude_cli(claude_cli, prompt_file, user_prompt, cwd, timeout, model):
    args = _build_claude_review_args(model)
    return run_review_cli(
        claude_cli,
        [*args, "--append-system-prompt-file", str(prompt_file), user_prompt],
        cwd=cwd,
        timeout=timeout,
    )


def _attempt_claude_autocomplete(request: ReviewRequest, *, log_event_fn) -> AutocompleteResult:
    ctx = request.ctx
    review_id = request.review_id
    review_path = request.review_path
    prompt_file = request.prompt_file
    user_prompt = request.user_prompt
    reviewer_timeout_seconds = request.reviewer_timeout_seconds
    model = request.model

    claude_cli, failure = resolve_cli_or_fail(ctx, "claude", prompt_file, log_event_fn=log_event_fn)
    if failure is not None:
        return failure

    with handle_subprocess_errors(ctx, review_id, "claude", log_event_fn) as build_result:
        try:
            cli_result = _run_claude_cli(
                claude_cli,
                prompt_file,
                user_prompt,
                ctx.project_root,
                reviewer_timeout_seconds,
                model,
            )
        except subprocess.TimeoutExpired:
            return build_result(AutocompleteStatus.TIMEOUT)
        except (OSError, ValueError, subprocess.SubprocessError) as e:
            return build_result(AutocompleteStatus.ERROR, stderr=str(e))

    return _process_review_result(ctx, cli_result, review_path, review_id, "claude", log_event_fn=log_event_fn)
