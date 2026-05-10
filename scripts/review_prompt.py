#!/usr/bin/env python3
from pathlib import Path

from bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.paths import get_client_id, get_project_root
from scripts.review_prompt_flow import create_review_prompt_files
from scripts.shims import write_project_script_shim
from scripts.state import (
    append_review_started,
    ensure_client_runtime,
    get_unreviewed_files,
    log_event,
    load_settings,
    load_state,
)


def main():
    try:
        project_root = get_project_root()
        client_id = get_client_id()
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

        artifacts = create_review_prompt_files(project_root, client_id, unreviewed, settings)

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
        print("Read the prompt, complete the review file, and fix any agreed CRITICAL or HIGH findings before stopping.")
        return 0
    except Exception as error:
        try:
            log_event(get_project_root(), "review_prompt_error", error=str(error))
        except Exception:
            pass
        print(f"Claude Auto Review failed open: {error}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
