#!/usr/bin/env python3
import sys

from claude_auto_review.config.file_filters import should_skip_file
from claude_auto_review.paths.path_utils import DELETED_FILE_HASH, local_now_iso
from claude_auto_review.paths.uri_utils import normalize_relative_path
from claude_auto_review.runtime.events import log_event
from claude_auto_review.runtime.hook_context import build_hook_runtime_context
from claude_auto_review.runtime.process import run_fail_open
from claude_auto_review.state.hook_input import extract_file_paths_from_hook_input
from claude_auto_review.state.models import EditRecord
from claude_auto_review.state.store.read import get_file_hash, load_state_snapshot, was_hash_reviewed
from claude_auto_review.state.store.write import append_state_event


def _run_post_tool_use():
    ctx = build_hook_runtime_context(sys.stdin.read())
    project_root = ctx.project_root
    client_id = ctx.client_id
    settings = ctx.settings
    payload = ctx.payload
    if not settings.enabled:
        log_event(project_root, "post_tool_use_disabled", client_id=client_id)
        return 0

    state_snapshot = load_state_snapshot(project_root, client_id)
    timestamp = local_now_iso()

    for candidate in extract_file_paths_from_hook_input(payload, project_root=project_root):
        file_path = normalize_relative_path(candidate, project_root)
        if not file_path:
            log_event(project_root, "post_tool_use_ignored_path", client_id=client_id, path=candidate)
            continue
        if should_skip_file(file_path, settings):
            reason = "runtime" if file_path.startswith(".claude/claude-auto-review/") else "settings"
            log_event(project_root, "post_tool_use_skipped_file", client_id=client_id, file=file_path, reason=reason)
            continue
        file_hash = get_file_hash(file_path, project_root)
        if not file_hash:
            append_state_event(
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
            log_event(project_root, "file_deletion_tracked", client_id=client_id, file=file_path, hash=DELETED_FILE_HASH, reviewed=False)
            continue
        reviewed = was_hash_reviewed(state_snapshot, file_path, file_hash)
        append_state_event(
            EditRecord(
                timestamp=timestamp,
                file=file_path,
                hash=file_hash,
                reviewed=reviewed,
            ),
            project_root,
            client_id=client_id,
        )
        log_event(project_root, "file_tracked", client_id=client_id, file=file_path, hash=file_hash, reviewed=reviewed)
    return 0


def main():
    return run_fail_open(_run_post_tool_use, event_type="post_tool_use_error")


if __name__ == "__main__":
    raise SystemExit(main())

