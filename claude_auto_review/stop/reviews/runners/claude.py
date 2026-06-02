from __future__ import annotations

import subprocess
from pathlib import Path

from claude_auto_review.runtime.events import log_event
from claude_auto_review.stop.reviews.runners.args import _build_claude_review_args
from claude_auto_review.stop.reviews.runners.cli import run_review_cli
from claude_auto_review.stop.reviews.runners.preamble import (
    handle_subprocess_errors,
    resolve_cli_or_fail,
)
from claude_auto_review.stop.reviews.types.enums import AutocompleteStatus
from claude_auto_review.stop.reviews.types.result import AutocompleteResult, _process_review_result


def _run_claude_cli(cli_path, prompt_file, user_prompt, cwd, timeout, model):
    """Invoke the ``claude`` CLI with a prompt file and inline user prompt.

    Kept as a thin wrapper for backward compatibility and testability.
    """
    args = [
        *_build_claude_review_args(model),
        "--append-system-prompt-file",
        str(prompt_file),
        user_prompt,
    ]
    return run_review_cli(
        cli_path,
        args,
        cwd=cwd,
        timeout=timeout,
    )


def _attempt_claude_autocomplete(
    ctx,
    review_id,
    review_path,
    prompt_file,
    user_prompt,
    reviewer_timeout_seconds,
    model,
    *,
    log_event_fn=None,
):
    _log = log_event_fn or log_event
    claude_cli, failure = resolve_cli_or_fail(ctx, "claude", prompt_file, log_event_fn=_log)
    if failure is not None:
        return failure

    with handle_subprocess_errors(ctx, review_id, "claude", _log) as build_result:
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

    return _process_review_result(ctx, cli_result, review_path, review_id, "claude", log_event_fn=_log)
