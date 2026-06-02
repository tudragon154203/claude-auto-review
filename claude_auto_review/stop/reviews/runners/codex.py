from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from claude_auto_review.runtime.events import log_event
from claude_auto_review.stop.reviews.runners.args import _build_codex_review_args
from claude_auto_review.stop.reviews.runners.cli import run_review_cli
from claude_auto_review.stop.reviews.runners.codex_output import _extract_codex_final_message
from claude_auto_review.stop.reviews.runners.preamble import (
    handle_subprocess_errors,
    resolve_cli_or_fail,
)
from claude_auto_review.stop.reviews.types.enums import AutocompleteStatus
from claude_auto_review.stop.reviews.types.result import AutocompleteResult, _process_review_result


def _read_text_with_bom_fallback(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-16", "utf-16-le", "utf-16-be", "utf-8"):
        try:
            return raw.decode(encoding).strip()
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace").strip()


def _attempt_codex_autocomplete(
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
    codex_cli, failure = resolve_cli_or_fail(ctx, "codex", prompt_file, log_event_fn=_log)
    if failure is not None:
        return failure

    output_file = None
    args = _build_codex_review_args(model)
    prompt_content = prompt_file.read_text(encoding="utf-8") if prompt_file.is_file() else ""
    full_input = f"{prompt_content}\n\n{user_prompt}" if prompt_content else user_prompt
    with handle_subprocess_errors(ctx, review_id, "codex", _log) as build_result:
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                suffix="-codex-last-message.md",
                delete=False,
            ) as temp_output:
                output_file = Path(temp_output.name)
            args = [*args[:-1], "--output-last-message", str(output_file), args[-1]]
            cli_result = run_review_cli(
                codex_cli,
                args,
                cwd=ctx.project_root,
                timeout=reviewer_timeout_seconds,
                input_text=full_input,
            )
        except subprocess.TimeoutExpired:
            return build_result(AutocompleteStatus.TIMEOUT)
        except (OSError, ValueError, subprocess.SubprocessError) as e:
            return build_result(AutocompleteStatus.ERROR, stderr=str(e))

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
        return _process_review_result(ctx, cli_result, review_path, review_id, "codex", log_event_fn=_log)
    finally:
        if output_file is not None:
            output_file.unlink(missing_ok=True)
