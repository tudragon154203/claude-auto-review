#!/usr/bin/env python3
from __future__ import annotations

import sys

from claude_auto_review.config.file_filters import should_skip_file
from claude_auto_review.hooks.common import run_hook
from claude_auto_review.paths.path_utils import DELETED_FILE_HASH, local_now_iso
from claude_auto_review.paths.uri_utils import normalize_relative_path
from claude_auto_review.runtime.events import log_event
from claude_auto_review.state.hook_input import extract_file_paths_from_hook_input
from claude_auto_review.state.models import EditRecord
from claude_auto_review.state.store.read import was_hash_reviewed
from claude_auto_review.state.store.repository import StateRepository


def _run_post_tool_use(ctx):
    project_root = ctx.project_root
    client_id = ctx.client_id
    settings = ctx.settings
    payload = ctx.payload
    repository = StateRepository.for_client(project_root, client_id)
    if not settings.enabled:
        log_event(project_root, "post_tool_use_disabled", client_id=client_id)
        return 0

    state_snapshot = repository.load_snapshot()
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
        file_hash = repository.get_file_hash(file_path)
        if not file_hash:
            repository.append_event(
                EditRecord(
                    timestamp=timestamp,
                    file=file_path,
                    hash=DELETED_FILE_HASH,
                    reviewed=False,
                    deleted=True,
                )
            )
            log_event(project_root, "file_deletion_tracked", client_id=client_id, file=file_path, hash=DELETED_FILE_HASH, reviewed=False)
            continue
        reviewed = was_hash_reviewed(state_snapshot, file_path, file_hash)
        repository.append_event(
            EditRecord(
                timestamp=timestamp,
                file=file_path,
                hash=file_hash,
                reviewed=reviewed,
            )
        )
        log_event(project_root, "file_tracked", client_id=client_id, file=file_path, hash=file_hash, reviewed=reviewed)
    return 0


def main():
    return run_hook(_run_post_tool_use, raw_input=sys.stdin.read(), event_type="post_tool_use_error")


if __name__ == "__main__":
    raise SystemExit(main())
