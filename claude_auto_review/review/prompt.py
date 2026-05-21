#!/usr/bin/env python3
import sys
import traceback
from pathlib import Path

if __name__ == "__main__":
    _plugin_root = Path(__file__).resolve().parents[2]
    if str(_plugin_root) not in sys.path:
        sys.path.insert(0, str(_plugin_root))

from claude_auto_review.config.io import load_settings
from claude_auto_review.paths.shims import write_project_script_shim
from claude_auto_review.paths.path_utils import get_project_root
from claude_auto_review.review.prompting.flow import create_review_prompt_files
from claude_auto_review.runtime.client_dirs import get_client_id
from claude_auto_review.runtime.events import log_event, log_failure
from claude_auto_review.runtime.process import run_fail_open
from claude_auto_review.runtime.setup import ensure_client_runtime
from claude_auto_review.state.store.read import get_unreviewed_files, load_state
from claude_auto_review.state.store.write import append_review_started
from claude_auto_review.stop.orchestration.context import RuntimeContext


def _log_failure(project_root, client_id, error):
    message = f"Claude Auto Review failed open: {error}"
    traceback_text = traceback.format_exc()
    if not log_failure(project_root, "review_prompt_error", client_id=client_id, error=error, traceback=traceback_text):
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
    if not settings.enabled:
        log_event(project_root, "review_prompt_disabled", client_id=client_id)
        print("Claude Auto Review is disabled in .claude/settings.json.")
        return 0

    unreviewed = get_unreviewed_files(load_state(project_root, client_id))
    if not unreviewed:
        log_event(project_root, "review_prompt_noop", client_id=client_id)
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
        client_id=client_id,
        reviewId=artifacts.review_id,
        files=artifacts.files,
        prompt=str(artifacts.prompt_path),
        review=str(artifacts.review_path),
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

    return run_fail_open(_run, on_error=lambda error: _log_failure(project_root, None, error), fallback=1)


if __name__ == "__main__":
    raise SystemExit(main())
