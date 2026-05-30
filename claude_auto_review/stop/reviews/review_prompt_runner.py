from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from claude_auto_review.runtime.client_dirs import client_run_dir
from claude_auto_review.runtime.events import log_event
from claude_auto_review.runtime.process import run_captured
from claude_auto_review.state.store.queries import get_unreviewed_files
from claude_auto_review.state.store.read import load_state
from claude_auto_review.stop.response import block_response
from claude_auto_review.stop.orchestration.context import RuntimeContext


def _review_prompt_command(review_prompt_script):
    return [sys.executable, str(review_prompt_script)]


def run_review_prompt(ctx: RuntimeContext, review_prompt_script, env):
    cmd = _review_prompt_command(review_prompt_script)
    result = run_captured(cmd, cwd=ctx.project_root, timeout=60, env=env)
    log_event(
        ctx.project_root,
        "stop_hook_review_invoked",
        client_id=ctx.client_id,
        stdout=result.stdout,
        stderr=result.stderr,
        returncode=result.returncode,
    )
    return result


def _review_prompt_path(ctx: RuntimeContext, review_id: str) -> Path:
    return client_run_dir(ctx.project_root, ctx.client_id) / f"review-{review_id}-prompt.md"


def _reload_client_state(ctx: RuntimeContext):
    state = load_state(ctx.project_root, ctx.client_id)
    return state, get_unreviewed_files(state)


def _block_review_prompt_failure(files_str, result):
    block_response(
        f"Claude Auto Review: Failed to create review for {files_str}.",
        f"review_prompt.py ran but no review was created.\n\nOutput:\n{result.stdout}\n\nErrors:\n{result.stderr}",
    )


def build_review_prompt_env(payload: dict[str, Any]) -> dict[str, str]:
    """Build the subprocess environment for running the review prompt script."""
    env = os.environ.copy()
    session_id = payload.get("session_id")
    if session_id:
        env["CLAUDE_SESSION_ID"] = session_id
    return env
