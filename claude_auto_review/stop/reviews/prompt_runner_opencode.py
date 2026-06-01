from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from claude_auto_review.runtime.events import log_event

from claude_auto_review.stop.reviews.cli_runner import run_review_cli
from claude_auto_review.stop.reviews.review_args import _build_opencode_review_args
from claude_auto_review.stop.reviews.review_result import AutocompleteResult, _process_review_result
from claude_auto_review.stop.reviews.enums import AutocompleteStatus


def _attempt_opencode_autocomplete(
    ctx,
    review_id,
    review_path,
    prompt_file,
    user_prompt,
    reviewer_timeout_seconds,
    model,
):
    opencode_cli = shutil.which("opencode")
    if not opencode_cli:
        log_event(ctx.project_root, "stop_hook_reviewer_not_found", client_id=ctx.client_id, backend="opencode")
        return AutocompleteResult(status=AutocompleteStatus.CLI_NOT_FOUND)
    if not prompt_file.is_file():
        log_event(ctx.project_root, "stop_hook_prompt_not_found", client_id=ctx.client_id, path=str(prompt_file))
        return AutocompleteResult(status=AutocompleteStatus.PROMPT_NOT_FOUND)

    try:
        prompt_content = prompt_file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        log_event(
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
        try:
            cli_result = run_review_cli(
                opencode_cli,
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
                backend="opencode",
            )
            return AutocompleteResult(status=AutocompleteStatus.TIMEOUT)
        except (OSError, ValueError, subprocess.SubprocessError) as e:
            log_event(
                ctx.project_root,
                "stop_hook_reviewer_error",
                client_id=ctx.client_id,
                reviewId=review_id,
                backend="opencode",
                error=str(e),
            )
            return AutocompleteResult(status=AutocompleteStatus.ERROR, stderr=str(e))

        return _process_review_result(ctx, cli_result, review_path, review_id, "opencode")
    finally:
        if merged_file is not None:
            merged_file.unlink(missing_ok=True)


_SAFE_RE = re.compile(r"[^A-Za-z0-9_-]")


def _write_merged_prompt(content: str, run_dir: Path, review_id: str) -> Path:
    safe_id = _SAFE_RE.sub("_", review_id)
    path = run_dir / f"opencode-{safe_id}-merged-prompt.md"
    path.write_text(content, encoding="utf-8", newline="\n")
    return path
