from __future__ import annotations

from claude_auto_review.config.models import DEFAULT_REVIEWER_MODEL
from claude_auto_review.runtime.process import run_captured
from claude_auto_review.stop.orchestration.context import RuntimeContext


def _run_review_cli(cli_path, args, *, cwd, timeout, input_text=None):
    return run_captured(
        [cli_path, *args],
        cwd=cwd,
        timeout=float(timeout),
        input=input_text,
    )


def attempt_stop_autocomplete(
    ctx: RuntimeContext,
    review_id,
    review_path,
    prompt_file,
    user_prompt,
    reviewer_timeout_seconds=600,
    model=DEFAULT_REVIEWER_MODEL,
    backend="claude",
):
    if backend == "codex":
        from .prompt_runner_codex import _attempt_codex_autocomplete

        return _attempt_codex_autocomplete(
            ctx,
            review_id,
            review_path,
            prompt_file,
            user_prompt,
            reviewer_timeout_seconds,
            model,
        )
    if backend == "claude":
        from .prompt_runner_claude import _attempt_claude_autocomplete

        return _attempt_claude_autocomplete(
            ctx,
            review_id,
            review_path,
            prompt_file,
            user_prompt,
            reviewer_timeout_seconds,
            model,
        )
    raise ValueError(f"Unsupported reviewer backend: {backend}")
