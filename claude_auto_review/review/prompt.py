#!/usr/bin/env python3
import sys
import traceback
from pathlib import Path

# Ensure repo root is on path so claude_auto_review package is importable
_repo_root = Path(__file__).resolve().parent.parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))
from claude_auto_review.bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from claude_auto_review.paths import get_client_id, get_project_root
from claude_auto_review.review.prompt_flow import create_review_prompt_files
from claude_auto_review.install.shims import write_project_script_shim
from claude_auto_review.runtime.helpers import run_fail_open
from claude_auto_review.runtime.setup import ensure_client_runtime
from claude_auto_review.settings import load_settings
from claude_auto_review.state.store_read import get_unreviewed_files, load_state
from claude_auto_review.runtime.helpers import log_event
from claude_auto_review.state.store_write import append_review_started
from claude_auto_review.stop.orchestration.context import RuntimeContext


def _log_failure(project_root, error):
    message = f"Claude Auto Review failed open: {error}"
    traceback_text = traceback.format_exc()
    try:
        log_event(project_root, "review_prompt_error", error=str(error), traceback=traceback_text)
    except Exception:
        print(message, file=sys.stderr)
        print(traceback_text, file=sys.stderr)
    else:
        print(message, file=sys.stderr)
    return True


def _run_review_prompt(project_root, client_id):
    ensure_client_runtime(project_root, client_id)
    write_project_script_shim(
        Path(project_root) / ".claude" / "claude-auto-review" / "scripts" / "review_prompt.py",
        Path(__file__).resolve(),
    )

    settings = load_settings(project_root)
    if not settings.get("enabled", True):
        log_event(project_root, "review_prompt_disabled")
        print("Claude Auto Review is disabled in .claude/settings.json.")
        return 0

    unreviewed = get_unreviewed_files(load_state(project_root, client_id))
    if not unreviewed:
        log_event(project_root, "review_prompt_noop")
        print("Claude Auto Review: no unreviewed changes.")
        return 0

    ctx = RuntimeContext(
        project_root=project_root,
        client_id=client_id,
        settings=settings,
    )
    artifacts = create_review_prompt_files(ctx, unreviewed, settings=settings)

    append_review_started(unreviewed, artifacts.review_id, artifacts.review_path, project_root, client_id=client_id)
    log_event(
        project_root,
        "review_prompt_created",
        reviewId=artifacts.review_id,
        files=artifacts.files,
        prompt=str(artifacts.prompt_path),
        review=str(artifacts.review_path),
        clientId=client_id,
    )
    print(f"Claude Auto Review prompt created: {artifacts.prompt_path}")
    print(f"Review file initialized: {artifacts.review_path}")
    print("Read the prompt, complete the review file, and fix all Confirmed findings before stopping.")
    return 0


def main():
    project_root = get_project_root()

    def _run():
        client_id = get_client_id()
        return _run_review_prompt(project_root, client_id)

    return run_fail_open(_run, on_error=lambda error: _log_failure(project_root, error), fallback=1)


if __name__ == "__main__":
    raise SystemExit(main())
