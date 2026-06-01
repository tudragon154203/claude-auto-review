from __future__ import annotations

import shutil
import subprocess

from claude_auto_review.runtime.events import log_event

from claude_auto_review.stop.reviews.cli_runner import run_review_cli
from claude_auto_review.stop.reviews.review_args import _build_claude_review_args
from claude_auto_review.stop.reviews.review_result import AutocompleteResult, _process_review_result
from claude_auto_review.stop.reviews.enums import AutocompleteStatus


def _run_claude_cli(cli_path, prompt_file, user_prompt, cwd, timeout, model):
    args = [
        *_build_claude_review_args(model),
        "--append-system-prompt-file",
        str(prompt_file),
        user_prompt,
    ]
    return run_review_cli(cli_path, args, cwd=cwd, timeout=timeout)


def _attempt_claude_autocomplete(
    ctx,
    review_id,
    review_path,
    prompt_file,
    user_prompt,
    reviewer_timeout_seconds,
    model,
):
    claude_cli = shutil.which("claude")
    if not claude_cli:
        log_event(ctx.project_root, "stop_hook_reviewer_not_found", client_id=ctx.client_id, backend="claude")
        return AutocompleteResult(status=AutocompleteStatus.CLI_NOT_FOUND)
    if not prompt_file.is_file():
        log_event(ctx.project_root, "stop_hook_prompt_not_found", client_id=ctx.client_id, path=str(prompt_file))
        return AutocompleteResult(status=AutocompleteStatus.PROMPT_NOT_FOUND)

    args = [
        *_build_claude_review_args(model),
        "--append-system-prompt-file",
        str(prompt_file),
        user_prompt,
    ]
    try:
        cli_result = run_review_cli(
            claude_cli,
            args,
            cwd=ctx.project_root,
            timeout=reviewer_timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        log_event(
            ctx.project_root,
            "stop_hook_reviewer_timeout",
            client_id=ctx.client_id,
            reviewId=review_id,
            backend="claude",
        )
        return AutocompleteResult(status=AutocompleteStatus.TIMEOUT)
    except (OSError, ValueError, subprocess.SubprocessError) as e:
        log_event(
            ctx.project_root,
            "stop_hook_reviewer_error",
            client_id=ctx.client_id,
            reviewId=review_id,
            backend="claude",
            error=str(e),
        )
        return AutocompleteResult(status=AutocompleteStatus.ERROR, stderr=str(e))

    return _process_review_result(ctx, cli_result, review_path, review_id, "claude")
