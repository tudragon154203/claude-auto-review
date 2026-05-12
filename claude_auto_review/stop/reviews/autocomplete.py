import shutil
import subprocess
from pathlib import Path

from claude_auto_review.review.completion import apply_completed_review
from claude_auto_review.state.reviews import is_review_clean, is_review_complete
from claude_auto_review.runtime.helpers import log_event


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
        cli_result = subprocess.run(
            [
                claude_cli,
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
                "--system-prompt-file",
                str(prompt_file),
                user_prompt,
            ],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=float(reviewer_timeout_seconds),
        )
        log_event(
            project_root,
            "stop_hook_claude_cli_done",
            returncode=cli_result.returncode,
            stdout=cli_result.stdout[:500],
            stderr=cli_result.stderr[:500] if cli_result.stderr else "",
        )
        if cli_result.returncode == 0 and cli_result.stdout.strip():
            if not is_review_complete(review_path):
                review_path.write_text(cli_result.stdout, encoding="utf-8", newline="\n")
        if is_review_complete(review_path) and is_review_clean(review_path):
            remaining = apply_completed_review(project_root, client_id, review_id, covered_entries)
            if not remaining:
                return True
            return False
    except subprocess.TimeoutExpired:
        log_event(project_root, "stop_hook_claude_cli_timeout", reviewId=review_id)
    except Exception as e:
        log_event(project_root, "stop_hook_claude_cli_error", error=str(e))
    return False
