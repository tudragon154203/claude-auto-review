from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from claude_auto_review.config.models import DEFAULT_REVIEWER_MODEL
from claude_auto_review.runtime.events import log_event
from claude_auto_review.runtime.process import run_captured
from claude_auto_review.stop.orchestration.context import RuntimeContext
from claude_auto_review.stop.reviews.codex_output import (
    _extract_codex_final_message,
)
from claude_auto_review.stop.reviews.enums import AutocompleteStatus
from claude_auto_review.stop.reviews.review_args import (
    _build_claude_review_args,
    _build_codex_review_args,
)
from claude_auto_review.stop.reviews.review_result import (
    AutocompleteResult,
    _process_review_result,
)


def _run_review_cli(cli_path, args, *, cwd, timeout, input_text=None):
    return run_captured(
        [cli_path, *args],
        cwd=cwd,
        timeout=float(timeout),
        input=input_text,
    )


def _read_text_with_bom_fallback(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-16", "utf-16-le", "utf-16-be", "utf-8"):
        try:
            return raw.decode(encoding).strip()
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace").strip()


def _run_claude_cli(cli_path, prompt_file, user_prompt, cwd, timeout, model):
    args = [
        *_build_claude_review_args(model),
        "--append-system-prompt-file",
        str(prompt_file),
        user_prompt,
    ]
    return _run_review_cli(cli_path, args, cwd=cwd, timeout=timeout)


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
        cli_result = _run_review_cli(
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


def _attempt_codex_autocomplete(
    ctx,
    review_id,
    review_path,
    prompt_file,
    user_prompt,
    reviewer_timeout_seconds,
    model,
):
    codex_cli = shutil.which("codex")
    if not codex_cli:
        log_event(ctx.project_root, "stop_hook_reviewer_not_found", client_id=ctx.client_id, backend="codex")
        return AutocompleteResult(status=AutocompleteStatus.CLI_NOT_FOUND)
    if not prompt_file.is_file():
        log_event(ctx.project_root, "stop_hook_prompt_not_found", client_id=ctx.client_id, path=str(prompt_file))
        return AutocompleteResult(status=AutocompleteStatus.PROMPT_NOT_FOUND)

    output_file = None
    args = _build_codex_review_args(model)
    prompt_content = prompt_file.read_text(encoding="utf-8") if prompt_file.is_file() else ""
    full_input = f"{prompt_content}\n\n{user_prompt}" if prompt_content else user_prompt
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix="-codex-last-message.md",
            delete=False,
        ) as temp_output:
            output_file = Path(temp_output.name)
        args = [*args[:-1], "--output-last-message", str(output_file), args[-1]]
        cli_result = _run_review_cli(
            codex_cli,
            args,
            cwd=ctx.project_root,
            timeout=reviewer_timeout_seconds,
            input_text=full_input,
        )
    except subprocess.TimeoutExpired:
        log_event(
            ctx.project_root, "stop_hook_reviewer_timeout", client_id=ctx.client_id, reviewId=review_id, backend="codex"
        )
        return AutocompleteResult(status=AutocompleteStatus.TIMEOUT)
    except (OSError, ValueError, subprocess.SubprocessError) as e:
        log_event(
            ctx.project_root,
            "stop_hook_reviewer_error",
            client_id=ctx.client_id,
            reviewId=review_id,
            backend="codex",
            error=str(e),
        )
        return AutocompleteResult(status=AutocompleteStatus.ERROR, stderr=str(e))

    file_output = ""
    if output_file is not None and output_file.is_file():
        file_output = _read_text_with_bom_fallback(output_file)

    raw_stdout = cli_result.stdout or ""
    stdout_extracted = _extract_codex_final_message(raw_stdout)
    extracted = file_output if file_output and not file_output.startswith("</") else stdout_extracted
    if extracted and extracted != raw_stdout.strip():
        cli_result = subprocess.CompletedProcess(
            cli_result.args,
            cli_result.returncode,
            stdout=extracted,
            stderr=cli_result.stderr,
        )
    try:
        return _process_review_result(ctx, cli_result, review_path, review_id, "codex")
    finally:
        if output_file is not None:
            output_file.unlink(missing_ok=True)
