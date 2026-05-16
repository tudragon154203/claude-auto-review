import shutil
import subprocess
import sys
from dataclasses import dataclass

from claude_auto_review.runtime.client_dirs import client_run_dir
from claude_auto_review.paths.path_utils import local_now_iso
from claude_auto_review.runtime.events import log_event
from claude_auto_review.runtime.process import run_captured
from claude_auto_review.state.reviews.verdicts import (
    normalize_review_verdict_content,
)
from claude_auto_review.state.store.read import get_unreviewed_files, load_state
from claude_auto_review.stop.feedback import block_response
from claude_auto_review.stop.orchestration.core.context import RuntimeContext


CLAUDE_REVIEW_ARGS = [
    "--print",
    "--bare",
    "--allowedTools",
    "Read",
    "Grep",
    "Glob",
    "Bash",
    "--model",
    "fast",
    "--effort",
    "low",
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


def _review_prompt_command(review_prompt_script):
    return [sys.executable, str(review_prompt_script)]


def _run_review_prompt(ctx: RuntimeContext, review_prompt_script, env):
    cmd = _review_prompt_command(review_prompt_script)
    result = run_captured(cmd, cwd=ctx.project_root, timeout=60, env=env)
    log_event(
        ctx.project_root,
        "stop_hook_review_invoked",
        stdout=result.stdout,
        stderr=result.stderr,
        returncode=result.returncode,
    )
    return result


def _review_prompt_path(ctx: RuntimeContext, review_id):
    return client_run_dir(ctx.project_root, ctx.client_id) / f"review-{review_id}-prompt.md"


def _reload_client_state(ctx: RuntimeContext):
    state = load_state(ctx.project_root, ctx.client_id)
    return state, get_unreviewed_files(state)


def _block_review_prompt_failure(files_str, result):
    block_response(
        f"Claude Auto Review: Failed to create review for {files_str}.",
        f"review_prompt.py ran but no review was created.\n\nOutput:\n{result.stdout}\n\nErrors:\n{result.stderr}",
    )


def _run_claude_cli(claude_cli, prompt_file, user_prompt, cwd, timeout):
    cmd = [
        claude_cli,
        *CLAUDE_REVIEW_ARGS,
        "--append-system-prompt-file",
        str(prompt_file),
        user_prompt,
    ]
    return run_captured(cmd, cwd=cwd, timeout=float(timeout))


def attempt_stop_autocomplete(
    ctx: RuntimeContext,
    review_id,
    review_path,
    prompt_file,
    covered_entries,
    user_prompt,
    reviewer_timeout_seconds=600,
):
    claude_cli = shutil.which("claude")
    if not claude_cli:
        log_event(ctx.project_root, "stop_hook_claude_cli_not_found")
        return AutocompleteResult(status="cli_not_found")
    if not prompt_file.is_file():
        log_event(ctx.project_root, "stop_hook_prompt_not_found", path=str(prompt_file))
        return AutocompleteResult(status="prompt_not_found")

    try:
        cli_result = _run_claude_cli(
            claude_cli, prompt_file, user_prompt, ctx.project_root, reviewer_timeout_seconds
        )
    except subprocess.TimeoutExpired:
        log_event(ctx.project_root, "stop_hook_claude_cli_timeout", reviewId=review_id)
        return AutocompleteResult(status="timeout")
    except (OSError, ValueError, subprocess.SubprocessError) as e:
        log_event(ctx.project_root, "stop_hook_claude_cli_error", error=str(e))
        return AutocompleteResult(status="error", stderr=str(e))

    return _process_review_result(
        ctx, cli_result, review_path, review_id
    )


def _process_review_result(ctx: RuntimeContext, result, review_path, review_id):
    stdout_len = len(result.stdout) if result.stdout else 0
    log_event(
        ctx.project_root,
        "stop_hook_claude_cli_done",
        returncode=result.returncode,
        stdout_len=stdout_len,
        stdout=result.stdout[:500],
        stderr=result.stderr[:500] if result.stderr else "",
    )

    if result.returncode != 0:
        log_event(
            ctx.project_root,
            "stop_hook_claude_cli_nonzero",
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
            "stop_hook_claude_cli_empty",
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
    log_event(ctx.project_root, "stop_hook_claude_cli_output_written", reviewId=review_id, stdout_len=stdout_len)
    return AutocompleteResult(
        status="output_written",
        stdout=normalized_output,
        stderr=result.stderr or "",
        returncode=result.returncode,
    )
