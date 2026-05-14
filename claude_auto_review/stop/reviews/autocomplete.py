import shutil
import subprocess
from pathlib import Path

from claude_auto_review.review.completion import apply_completed_review
from claude_auto_review.state.reviews import is_review_clean, is_review_complete
from claude_auto_review.runtime.helpers import log_event


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


def _run_claude_cli(claude_cli, prompt_file, user_prompt, cwd, timeout):
    """Run the claude CLI for auto-review. Returns subprocess result or raises."""
    cmd = [
        claude_cli,
        *CLAUDE_REVIEW_ARGS,
        "--system-prompt-file",
        str(prompt_file),
        user_prompt,
    ]
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=float(timeout),
    )


def _process_review_result(result, review_path, review_id, project_root, client_id, covered_entries):
    """Handle the completed review: log, write, and apply if clean."""
    log_event(
        project_root,
        "stop_hook_claude_cli_done",
        returncode=result.returncode,
        stdout=result.stdout[:500],
        stderr=result.stderr[:500] if result.stderr else "",
    )
    if result.returncode == 0 and result.stdout.strip():
        if not is_review_complete(review_path):
            review_path.write_text(result.stdout, encoding="utf-8", newline="\n")
        if is_review_complete(review_path) and is_review_clean(review_path):
            remaining = apply_completed_review(project_root, client_id, review_id, covered_entries)
            return not remaining
    return False


def attempt_stop_autocomplete(
    project_root,
    client_id,
    review_id,
    review_path,
    prompt_file,
    covered_entries,
    user_prompt,
    reviewer_timeout_seconds=600,
):
    claude_cli = shutil.which("claude")
    if not claude_cli:
        log_event(project_root, "stop_hook_claude_cli_not_found")
        return False
    if not prompt_file.is_file():
        log_event(project_root, "stop_hook_prompt_not_found", path=str(prompt_file))
        return False

    try:
        cli_result = _run_claude_cli(
            claude_cli, prompt_file, user_prompt, project_root, reviewer_timeout_seconds
        )
    except subprocess.TimeoutExpired:
        log_event(project_root, "stop_hook_claude_cli_timeout", reviewId=review_id)
        return False
    except Exception as e:
        log_event(project_root, "stop_hook_claude_cli_error", error=str(e))
        return False

    return _process_review_result(
        cli_result, review_path, review_id, project_root, client_id, covered_entries,
    )
