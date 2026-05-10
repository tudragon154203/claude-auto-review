import shutil
import subprocess
from pathlib import Path

from scripts.paths import utc_now_iso
from scripts.reviews import is_review_complete
from scripts.state import append_state, get_unreviewed_files, load_state, log_event, mark_files_reviewed


def attempt_stop_autocomplete(project_root, client_id, review_id, review_path, prompt_file, covered_entries, user_prompt):
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
                "--permission-mode",
                "acceptEdits",
                "--model",
                "fast",
                "--system-prompt-file",
                str(prompt_file),
                user_prompt,
            ],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=600,
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
        if is_review_complete(review_path):
            mark_files_reviewed(covered_entries, review_id, project_root, client_id=client_id)
            state = load_state(project_root, client_id)
            remaining = get_unreviewed_files(state)
            if not remaining:
                log_event(project_root, "stop_approved", reason="review_completed", reviewId=review_id)
                return True
            log_event(project_root, "stop_blocked_after_partial_review", remaining=[e["file"] for e in remaining])
            append_state({"type": "stop_blocked", "reason": "partial_review", "timestamp": utc_now_iso()}, project_root, client_id=client_id)
            return False
    except subprocess.TimeoutExpired:
        log_event(project_root, "stop_hook_claude_cli_timeout", reviewId=review_id)
    except Exception as e:
        log_event(project_root, "stop_hook_claude_cli_error", error=str(e))
    return False
