import shutil
import subprocess
import sys

from claude_auto_review.runtime.core.client_dirs import client_run_dir
from claude_auto_review.paths.core.path_utils import local_now_iso
from claude_auto_review.runtime.core.events import log_event
from claude_auto_review.runtime.core.process import run_captured
from claude_auto_review.review.core.completion import apply_completed_review
from claude_auto_review.state.reviews import (
    is_review_clean_content,
    normalize_review_verdict_content,
)
from claude_auto_review.state.store.read import get_unreviewed_files, load_state
from claude_auto_review.stop.core.feedback import block_response
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
        return False
    if not prompt_file.is_file():
        log_event(ctx.project_root, "stop_hook_prompt_not_found", path=str(prompt_file))
        return False

    try:
        cli_result = _run_claude_cli(
            claude_cli, prompt_file, user_prompt, ctx.project_root, reviewer_timeout_seconds
        )
    except subprocess.TimeoutExpired:
        log_event(ctx.project_root, "stop_hook_claude_cli_timeout", reviewId=review_id)
        return False
    except (OSError, ValueError, subprocess.SubprocessError) as e:
        log_event(ctx.project_root, "stop_hook_claude_cli_error", error=str(e))
        return False

    return _process_review_result(
        ctx, cli_result, review_path, review_id, covered_entries
    )


def _process_review_result(ctx: RuntimeContext, result, review_path, review_id, covered_entries):
    log_event(
        ctx.project_root,
        "stop_hook_claude_cli_done",
        returncode=result.returncode,
        stdout=result.stdout[:500],
        stderr=result.stderr[:500] if result.stderr else "",
    )
    if result.returncode == 0 and result.stdout.strip():
        normalized_output = normalize_review_verdict_content(result.stdout)
        review_path.write_text(normalized_output, encoding="utf-8", newline="\n")
        if is_review_clean_content(normalized_output):
            remaining = apply_completed_review(
                ctx.project_root, ctx.client_id, review_id, covered_entries
            )
            return not remaining
    return False
