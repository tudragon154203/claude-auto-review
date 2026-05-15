#!/usr/bin/env python3
import sys

from bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from claude_auto_review.paths.path_utils import DELETED_FILE_HASH, get_project_root, local_now_iso
from claude_auto_review.runtime.client_dirs import get_client_id
from claude_auto_review.paths.uri_utils import normalize_relative_path
from claude_auto_review.runtime.context import read_json_payload
from claude_auto_review.runtime.events import log_event
from claude_auto_review.runtime.process import run_fail_open
from claude_auto_review.runtime.setup import ensure_client_runtime
from claude_auto_review.config.settings import load_settings, should_skip_file
from claude_auto_review.state.hook_input import extract_file_paths_from_hook_input
from claude_auto_review.state.models import EditRecord
from claude_auto_review.state.store.read import (
    get_file_hash,
    load_state,
    was_hash_reviewed,
)
from claude_auto_review.state.store.write import append_state


def _run_post_tool_use():
    project_root = get_project_root()
    raw = sys.stdin.read()
    payload = read_json_payload(raw)
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
            reason = "runtime" if file_path.startswith(".claude/claude-auto-review/") else "settings"
            log_event(project_root, "post_tool_use_skipped_file", file=file_path, reason=reason)
            continue
        file_hash = get_file_hash(file_path, project_root)
        if not file_hash:
            append_state(
                EditRecord(
                    timestamp=timestamp,
                    file=file_path,
                    hash=DELETED_FILE_HASH,
                    reviewed=False,
                    deleted=True,
                ),
                project_root,
                client_id=client_id,
            )
            log_event(project_root, "file_deletion_tracked", file=file_path, hash=DELETED_FILE_HASH, reviewed=False)
            continue
        reviewed = was_hash_reviewed(state, file_path, file_hash)
        append_state(
                EditRecord(
                    timestamp=timestamp,
                    file=file_path,
                    hash=file_hash,
                    reviewed=reviewed,
                ),
                project_root,
                client_id=client_id,
            )
        log_event(project_root, "file_tracked", file=file_path, hash=file_hash, reviewed=reviewed)
    return 0


def main():
    return run_fail_open(_run_post_tool_use, event_type="post_tool_use_error")


if __name__ == "__main__":
    raise SystemExit(main())
