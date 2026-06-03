#!/usr/bin/env python3
from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from claude_auto_review.config.resolvers.files import should_skip_file as _default_should_skip
from claude_auto_review.hooks.common import run_hook
from claude_auto_review.paths.path_utils import DELETED_FILE_HASH
from claude_auto_review.timestamps import local_now_iso as _default_now
from claude_auto_review.paths.uri_utils import normalize_relative_path as _default_normalize
from claude_auto_review.review.prompting.diff_mode import capture_session_snapshot as _default_snapshot
from claude_auto_review.runtime.events import log_event as _default_log_event
from claude_auto_review.state.extraction.hook_input import extract_file_paths_from_hook_input as _default_extract_paths
from claude_auto_review.state.records.edit import EditRecord
from claude_auto_review.state.store.queries import was_hash_reviewed as _default_was_reviewed
from claude_auto_review.state.hashing import get_file_hash as _default_get_hash
from claude_auto_review.state.store.read import load_state_snapshot as _default_load_snapshot
from claude_auto_review.state.store.write import append_state_event as _default_append


def _track_deleted_file(ctx, file_path, timestamp, *, append_state_event, log_event_fn):
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
    log_event_fn(
        ctx.project_root,
        "file_deletion_tracked",
        client_id=ctx.client_id,
        file=file_path,
        hash=DELETED_FILE_HASH,
        reviewed=False,
    )
    return True


def _track_edited_file(ctx, state_snapshot, settings, file_path, timestamp, *, get_file_hash, capture_snapshot, was_hash_reviewed, append_state_event, log_event_fn):
    file_hash = get_file_hash(file_path, ctx.project_root)
    if not file_hash:
        return _track_deleted_file(ctx, file_path, timestamp, append_state_event=append_state_event, log_event_fn=log_event_fn)

    capture_snapshot(file_path, ctx.project_root, ctx.client_id)
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
    log_event_fn(ctx.project_root, "file_tracked", client_id=ctx.client_id, file=file_path, hash=file_hash, reviewed=reviewed)
    return True


def _skip_reason(file_path: str) -> str:
    return "runtime" if file_path.startswith(".claude/claude-auto-review/") else "settings"


def _process_single_edit(ctx, state_snapshot, settings, file_path, timestamp, *, should_skip_file, get_file_hash, capture_snapshot, was_hash_reviewed, append_state_event, log_event_fn):
    if should_skip_file(file_path, settings):
        reason = _skip_reason(file_path)
        log_event_fn(ctx.project_root, "post_tool_use_skipped_file", client_id=ctx.client_id, file=file_path, reason=reason)
        return False
    return _track_edited_file(ctx, state_snapshot, settings, file_path, timestamp, get_file_hash=get_file_hash, capture_snapshot=capture_snapshot, was_hash_reviewed=was_hash_reviewed, append_state_event=append_state_event, log_event_fn=log_event_fn)


def _load_state_and_timestamp(ctx, *, load_state_snapshot, now):
    state_snapshot = load_state_snapshot(ctx.project_root, ctx.client_id)
    timestamp = now()
    return state_snapshot, timestamp


def _process_path_candidate(
    ctx,
    state_snapshot,
    settings,
    timestamp,
    candidate,
    *,
    normalize_path,
    should_skip_file,
    get_file_hash,
    capture_snapshot,
    was_hash_reviewed,
    append_state_event,
    log_event_fn,
):
    file_path = normalize_path(candidate, ctx.project_root)
    if not file_path:
        log_event_fn(ctx.project_root, "post_tool_use_ignored_path", client_id=ctx.client_id, path=candidate)
        return False
    return _process_single_edit(
        ctx, state_snapshot, settings, file_path, timestamp,
        should_skip_file=should_skip_file,
        get_file_hash=get_file_hash,
        capture_snapshot=capture_snapshot,
        was_hash_reviewed=was_hash_reviewed,
        append_state_event=append_state_event,
        log_event_fn=log_event_fn,
    )


def _run_post_tool_use(
    ctx,
    *,
    should_skip_file=_default_should_skip,
    get_file_hash=_default_get_hash,
    capture_snapshot=_default_snapshot,
    was_hash_reviewed=_default_was_reviewed,
    append_state_event=_default_append,
    load_state_snapshot=_default_load_snapshot,
    extract_file_paths=_default_extract_paths,
    normalize_path=_default_normalize,
    now=_default_now,
    log_event_fn=_default_log_event,
):
    project_root = ctx.project_root
    client_id = ctx.client_id
    settings = ctx.settings
    payload = ctx.payload
    if not settings.core.enabled:
        log_event_fn(project_root, "post_tool_use_disabled", client_id=client_id)
        return 0

    state_snapshot, timestamp = _load_state_and_timestamp(
        ctx, load_state_snapshot=load_state_snapshot, now=now
    )

    for candidate in extract_file_paths(payload, project_root=project_root):
        _process_path_candidate(
            ctx, state_snapshot, settings, timestamp, candidate,
            normalize_path=normalize_path,
            should_skip_file=should_skip_file,
            get_file_hash=get_file_hash,
            capture_snapshot=capture_snapshot,
            was_hash_reviewed=was_hash_reviewed,
            append_state_event=append_state_event,
            log_event_fn=log_event_fn,
        )
    return 0


def main():
    return run_hook(_run_post_tool_use, raw_input=sys.stdin.read(), event_type="post_tool_use_error")


if __name__ == "__main__":
    raise SystemExit(main())
