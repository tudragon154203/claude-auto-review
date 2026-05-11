#!/usr/bin/env python3
import json
import sys

from bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from claude_auto_review.paths import DELETED_FILE_HASH, get_client_id, get_project_root, local_now_iso, normalize_relative_path
from claude_auto_review.runtime.setup import ensure_client_runtime
from claude_auto_review.settings import load_settings, should_skip_file
from claude_auto_review.state.store_read import (
    extract_file_paths_from_hook_input,
    get_file_hash,
    load_state,
    was_hash_reviewed,
)
from claude_auto_review.state.store_write import append_state, log_event


def main():
    try:
        project_root = get_project_root()
        raw = sys.stdin.read().strip()
        payload = json.loads(raw) if raw else {}
        client_id = get_client_id(payload.get("session_id"))
        ensure_client_runtime(project_root, client_id)
        settings = load_settings(project_root)
        if not settings.get("enabled", True):
            log_event(project_root, "post_tool_use_disabled")
            return 0

        state = load_state(project_root, client_id)
        timestamp = local_now_iso()

        for candidate in extract_file_paths_from_hook_input(payload):
            file_path = normalize_relative_path(candidate, project_root)
            if not file_path:
                log_event(project_root, "post_tool_use_ignored_path", path=candidate)
                continue
            if should_skip_file(file_path, settings):
                log_event(project_root, "post_tool_use_skipped_file", file=file_path)
                continue
            file_hash = get_file_hash(file_path, project_root)
            if not file_hash:
                append_state(
                    {
                        "type": "edit",
                        "file": file_path,
                        "hash": DELETED_FILE_HASH,
                        "timestamp": timestamp,
                        "reviewed": False,
                        "deleted": True,
                    },
                    project_root,
                    client_id=client_id,
                )
                log_event(project_root, "file_deletion_tracked", file=file_path, hash=DELETED_FILE_HASH, reviewed=False)
                continue
            reviewed = was_hash_reviewed(state, file_path, file_hash)
            append_state(
                {
                    "type": "edit",
                    "file": file_path,
                    "hash": file_hash,
                    "timestamp": timestamp,
                    "reviewed": reviewed,
                },
                project_root,
                client_id=client_id,
            )
            log_event(project_root, "file_tracked", file=file_path, hash=file_hash, reviewed=reviewed)
        return 0
    except Exception as error:
        try:
            log_event(get_project_root(), "post_tool_use_error", error=str(error))
        except Exception:
            pass
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

