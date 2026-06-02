#!/usr/bin/env python3
from __future__ import annotations

import sys

from claude_auto_review.config.resolvers.files import should_skip_file
from claude_auto_review.hooks.common import run_hook
from claude_auto_review.paths.path_utils import DELETED_FILE_HASH, local_now_iso
from claude_auto_review.paths.uri_utils import normalize_relative_path
from claude_auto_review.review.prompting.diff_mode import capture_session_snapshot
from claude_auto_review.runtime.events import log_event
from claude_auto_review.state.extraction.hook_input import extract_file_paths_from_hook_input
from claude_auto_review.state.records.edit import EditRecord
from claude_auto_review.state.store.queries import was_hash_reviewed
from claude_auto_review.state.hashing import get_file_hash
from claude_auto_review.state.store.read import load_state_snapshot
from claude_auto_review.state.store.write import append_state_event


def _track_deleted_file(ctx, file_path, timestamp):
    append_state_event(
        EditRecord(
            timestamp=timestamp,
            file=file_path,
            hash=DELETED_FILE_HASH,
            reviewed=False,
            deleted=True,
        ),
        ctx.project_root,
        client_id=ctx.client_id,
    )
    log_event(
        ctx.project_root,
        "file_deletion_tracked",
        client_id=ctx.client_id,
        file=file_path,
        hash=DELETED_FILE_HASH,
        reviewed=False,
    )
    return True


def _track_edited_file(ctx, state_snapshot, settings, file_path, timestamp):
    file_hash = get_file_hash(file_path, ctx.project_root)
    if not file_hash:
        return _track_deleted_file(ctx, file_path, timestamp)

    capture_session_snapshot(file_path, ctx.project_root, ctx.client_id)
    reviewed = was_hash_reviewed(state_snapshot, file_path, file_hash)
    append_state_event(
        EditRecord(
            timestamp=timestamp,
            file=file_path,
            hash=file_hash,
            reviewed=reviewed,
        ),
        ctx.project_root,
        client_id=ctx.client_id,
    )
    log_event(ctx.project_root, "file_tracked", client_id=ctx.client_id, file=file_path, hash=file_hash, reviewed=reviewed)
    return True


def _process_single_edit(ctx, state_snapshot, settings, file_path, timestamp):
    if should_skip_file(file_path, settings):
        reason = "runtime" if file_path.startswith(".claude/claude-auto-review/") else "settings"
        log_event(ctx.project_root, "post_tool_use_skipped_file", client_id=ctx.client_id, file=file_path, reason=reason)
        return False
    return _track_edited_file(ctx, state_snapshot, settings, file_path, timestamp)


def _run_post_tool_use(ctx):
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
        _process_single_edit(ctx, state_snapshot, settings, file_path, timestamp)
    return 0


def main():
    return run_hook(_run_post_tool_use, raw_input=sys.stdin.read(), event_type="post_tool_use_error")


if __name__ == "__main__":
    raise SystemExit(main())
