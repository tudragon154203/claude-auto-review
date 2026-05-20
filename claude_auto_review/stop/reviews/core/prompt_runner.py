import json
import shutil
import subprocess
from dataclasses import dataclass

from claude_auto_review.runtime.events import log_event
from claude_auto_review.runtime.process import run_captured
from claude_auto_review.state.reviews.verdicts import (
    normalize_review_verdict_content,
)
from claude_auto_review.config.models import DEFAULT_REVIEWER_MODEL
from claude_auto_review.stop.orchestration.core.context import RuntimeContext


def _build_claude_review_args(model):
    return [
        "--print",
        "--bare",
        "--allowedTools",
        "Read",
        "Grep",
        "Glob",
        "Bash",
        "--model",
        model,
        "--effort",
        "low",
    ]


def _build_codex_review_args(model):
    return [
        "exec",
        "--json",
        "--skip-git-repo-check",
        "--sandbox",
        "read-only",
        "--model",
        model,
        "-",
    ]


@dataclass(frozen=True)
class AutocompleteResult:
    status: str
    stdout: str = ""
    stderr: str = ""
    returncode: int | None = None

    @property
    def output_written(self):
        return self.status == "output_written"

    def __bool__(self):
        return self.output_written


def _run_review_cli(cli_path, args, *, cwd, timeout, input_text=None):
    return run_captured(
        [cli_path, *args],
        cwd=cwd,
        timeout=float(timeout),
        input=input_text,
    )


def _extract_codex_final_message(stdout):
    last_message = None
    for line in (stdout or "").splitlines():
        try:
            event = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue
        event_type = event.get("type")
        msg = None
        if event_type == "turn.completed":
            msg = event.get("message") or event.get("output") or event.get("content")
        elif event_type == "item.completed":
            item = event.get("item")
            if isinstance(item, dict) and item.get("type") == "agent_message":
                msg = item.get("text") or item.get("message") or item.get("content")
        if msg is None:
            continue
        if isinstance(msg, str) and msg.strip():
            last_message = msg.strip()
        elif isinstance(msg, dict):
            text = msg.get("text")
            if isinstance(text, str) and text.strip():
                last_message = text.strip()
        elif isinstance(msg, list):
            text_parts = []
            for item in msg:
                if isinstance(item, str) and item.strip():
                    text_parts.append(item.strip())
                elif isinstance(item, dict):
                    text = item.get("text")
                    if isinstance(text, str) and text.strip():
                        text_parts.append(text.strip())
            if text_parts:
                last_message = "\n".join(text_parts)
    return last_message or (stdout or "").strip()


def _run_claude_cli(cli_path, prompt_file, user_prompt, cwd, timeout, model):
    args = [
        *_build_claude_review_args(model),
        "--append-system-prompt-file",
        str(prompt_file),
        user_prompt,
    ]
    return _run_review_cli(
        cli_path, args, cwd=cwd, timeout=timeout,
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
        return _attempt_codex_autocomplete(
            ctx, review_id, review_path, prompt_file, user_prompt,
            reviewer_timeout_seconds, model,
        )
    if backend == "claude":
        return _attempt_claude_autocomplete(
            ctx, review_id, review_path, prompt_file, user_prompt,
            reviewer_timeout_seconds, model,
        )
    raise ValueError(f"Unsupported reviewer backend: {backend}")


def _attempt_claude_autocomplete(
    ctx, review_id, review_path, prompt_file, user_prompt,
    reviewer_timeout_seconds, model,
):
    claude_cli = shutil.which("claude")
    if not claude_cli:
        log_event(ctx.project_root, "stop_hook_reviewer_not_found", client_id=ctx.client_id, backend="claude")
        return AutocompleteResult(status="cli_not_found")
    if not prompt_file.is_file():
        log_event(ctx.project_root, "stop_hook_prompt_not_found", client_id=ctx.client_id, path=str(prompt_file))
        return AutocompleteResult(status="prompt_not_found")

    args = [
        *_build_claude_review_args(model),
        "--append-system-prompt-file",
        str(prompt_file),
        user_prompt,
    ]
    try:
        cli_result = _run_review_cli(
            claude_cli, args, cwd=ctx.project_root, timeout=reviewer_timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        log_event(ctx.project_root, "stop_hook_reviewer_timeout", client_id=ctx.client_id, reviewId=review_id, backend="claude")
        return AutocompleteResult(status="timeout")
    except (OSError, ValueError, subprocess.SubprocessError) as e:
        log_event(ctx.project_root, "stop_hook_reviewer_error", client_id=ctx.client_id, reviewId=review_id, backend="claude", error=str(e))
        return AutocompleteResult(status="error", stderr=str(e))

    return _process_review_result(ctx, cli_result, review_path, review_id, "claude")


def _attempt_codex_autocomplete(
    ctx, review_id, review_path, prompt_file, user_prompt,
    reviewer_timeout_seconds, model,
):
    codex_cli = shutil.which("codex")
    if not codex_cli:
        log_event(ctx.project_root, "stop_hook_reviewer_not_found", client_id=ctx.client_id, backend="codex")
        return AutocompleteResult(status="cli_not_found")
    if not prompt_file.is_file():
        log_event(ctx.project_root, "stop_hook_prompt_not_found", client_id=ctx.client_id, path=str(prompt_file))
        return AutocompleteResult(status="prompt_not_found")

    args = _build_codex_review_args(model)
    prompt_content = prompt_file.read_text(encoding="utf-8") if prompt_file.is_file() else ""
    full_input = f"{prompt_content}\n\n{user_prompt}" if prompt_content else user_prompt
    try:
        cli_result = _run_review_cli(
            codex_cli, args, cwd=ctx.project_root, timeout=reviewer_timeout_seconds,
            input_text=full_input,
        )
    except subprocess.TimeoutExpired:
        log_event(ctx.project_root, "stop_hook_reviewer_timeout", client_id=ctx.client_id, reviewId=review_id, backend="codex")
        return AutocompleteResult(status="timeout")
    except (OSError, ValueError, subprocess.SubprocessError) as e:
        log_event(ctx.project_root, "stop_hook_reviewer_error", client_id=ctx.client_id, reviewId=review_id, backend="codex", error=str(e))
        return AutocompleteResult(status="error", stderr=str(e))

    raw_stdout = cli_result.stdout or ""
    extracted = _extract_codex_final_message(raw_stdout)
    if extracted and extracted != raw_stdout.strip():
        cli_result = subprocess.CompletedProcess(
            cli_result.args, cli_result.returncode,
            stdout=extracted, stderr=cli_result.stderr,
        )

    return _process_review_result(ctx, cli_result, review_path, review_id, "codex")


def _process_review_result(ctx: RuntimeContext, result, review_path, review_id, backend):
    stdout_len = len(result.stdout) if result.stdout else 0
    log_event(
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
        log_event(
            ctx.project_root,
            "stop_hook_reviewer_nonzero",
            client_id=ctx.client_id,
            backend=backend,
            returncode=result.returncode,
            reviewId=review_id,
            stderr=result.stderr[:500] if result.stderr else "",
        )
        return AutocompleteResult(
            status="nonzero",
            stdout=result.stdout or "",
            stderr=result.stderr or "",
            returncode=result.returncode,
        )

    if not result.stdout.strip():
        log_event(
            ctx.project_root,
            "stop_hook_reviewer_empty",
            client_id=ctx.client_id,
            backend=backend,
            reviewId=review_id,
            stdout_len=stdout_len,
            stderr=result.stderr[:500] if result.stderr else "",
        )
        return AutocompleteResult(
            status="empty_stdout",
            stdout=result.stdout or "",
            stderr=result.stderr or "",
            returncode=result.returncode,
        )

    normalized_output = normalize_review_verdict_content(result.stdout)
    review_path.write_text(normalized_output, encoding="utf-8", newline="\n")
    log_event(ctx.project_root, "stop_hook_reviewer_output_written", client_id=ctx.client_id, backend=backend, reviewId=review_id, stdout_len=stdout_len)
    return AutocompleteResult(
        status="output_written",
        stdout=normalized_output,
        stderr=result.stderr or "",
        returncode=result.returncode,
    )
