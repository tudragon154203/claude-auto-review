import subprocess
import sys

from claude_auto_review.state.store_read import get_unreviewed_files, load_state
from claude_auto_review.runtime.helpers import log_event
from claude_auto_review.stop.feedback import block_response


def _review_prompt_command(review_prompt_script):
    return [sys.executable, str(review_prompt_script)]


def _review_prompt_path(project_root, client_id, review_id):
    from claude_auto_review.paths import client_run_dir
    return client_run_dir(project_root, client_id) / f"review-{review_id}-prompt.md"


def _run_review_prompt(project_root, review_prompt_script, env):
    result = subprocess.run(
        _review_prompt_command(review_prompt_script),
        cwd=str(project_root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
        env=env,
    )
    log_event(
        project_root,
        "stop_hook_review_invoked",
        stdout=result.stdout,
        stderr=result.stderr,
        returncode=result.returncode,
    )
    return result


def _reload_client_state(project_root, client_id):
    state = load_state(project_root, client_id)
    return state, get_unreviewed_files(state)


def _block_review_prompt_failure(files_str, result):
    block_response(
        f"Claude Auto Review: Failed to create review for {files_str}.",
        f"review_prompt.py ran but no review was created.\n\nOutput:\n{result.stdout}\n\nErrors:\n{result.stderr}",
    )
