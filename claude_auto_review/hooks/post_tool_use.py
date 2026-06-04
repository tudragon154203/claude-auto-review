#!/usr/bin/env python3
from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from claude_auto_review.config.resolvers.files import should_skip_file
from claude_auto_review.hooks.common import run_hook
from claude_auto_review.paths.path_utils import DELETED_FILE_HASH, RUNTIME_DIR_STR
from claude_auto_review.timestamps import local_now_iso
from claude_auto_review.paths.uri_utils import normalize_relative_path
from claude_auto_review.review.prompting.diff_mode import capture_session_snapshot
from claude_auto_review.runtime.events import log_event
from claude_auto_review.state.extraction.hook_input import extract_file_paths_from_hook_input
from claude_auto_review.state.records.edit import EditRecord
from claude_auto_review.state.store.queries import was_hash_reviewed
from claude_auto_review.state.hashing import get_file_hash
from claude_auto_review.state.store.read import load_state_snapshot
from claude_auto_review.state.store.write import append_state_event


@dataclass(frozen=True)
class PostToolUseDeps:
    should_skip_file: Callable
    get_file_hash: Callable
    capture_snapshot: Callable
    was_hash_reviewed: Callable
    append_state_event: Callable
    load_state_snapshot: Callable
    extract_file_paths: Callable
    normalize_path: Callable
    now: Callable
    log_event_fn: Callable


def _current_module_deps() -> PostToolUseDeps:
    """Resolve dependencies from the current module namespace.

    Patch-friendly: ``patch("claude_auto_review.hooks.post_tool_use.<name>")``
    replaces the module attribute, and this factory reads it at call time.
    """
    import claude_auto_review.hooks.post_tool_use as _mod
    return PostToolUseDeps(
        should_skip_file=_mod.should_skip_file,
        get_file_hash=_mod.get_file_hash,
        capture_snapshot=_mod.capture_session_snapshot,
        was_hash_reviewed=_mod.was_hash_reviewed,
        append_state_event=_mod.append_state_event,
        load_state_snapshot=_mod.load_state_snapshot,
        extract_file_paths=_mod.extract_file_paths_from_hook_input,
        normalize_path=_mod.normalize_relative_path,
        now=_mod.local_now_iso,
        log_event_fn=_mod.log_event,
    )


def _track_deleted_file(ctx, file_path, timestamp, *, deps: PostToolUseDeps):
    deps.append_state_event(
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
    deps.log_event_fn(
        ctx.project_root,
        "file_deletion_tracked",
        client_id=ctx.client_id,
        file=file_path,
        hash=DELETED_FILE_HASH,
        reviewed=False,
    )
    return True


def _track_edited_file(ctx, state_snapshot, settings, file_path, timestamp, *, deps: PostToolUseDeps):
    file_hash = deps.get_file_hash(file_path, ctx.project_root)
    if not file_hash:
        return _track_deleted_file(ctx, file_path, timestamp, deps=deps)

    deps.capture_snapshot(file_path, ctx.project_root, ctx.client_id)
    reviewed = deps.was_hash_reviewed(state_snapshot, file_path, file_hash)
    deps.append_state_event(
        EditRecord(
            timestamp=timestamp,
            file=file_path,
            hash=file_hash,
            reviewed=reviewed,
        ),
        ctx.project_root,
        client_id=ctx.client_id,
    )
    deps.log_event_fn(ctx.project_root, "file_tracked", client_id=ctx.client_id, file=file_path, hash=file_hash, reviewed=reviewed)
    return True


def _skip_reason(file_path: str) -> str:
    return "runtime" if file_path.startswith(f"{RUNTIME_DIR_STR}/") else "settings"


def _process_single_edit(ctx, state_snapshot, settings, file_path, timestamp, *, deps: PostToolUseDeps):
    if deps.should_skip_file(file_path, settings):
        reason = _skip_reason(file_path)
        deps.log_event_fn(ctx.project_root, "post_tool_use_skipped_file", client_id=ctx.client_id, file=file_path, reason=reason)
        return False
    return _track_edited_file(ctx, state_snapshot, settings, file_path, timestamp, deps=deps)


def _process_path_candidate(
    ctx,
    state_snapshot,
    settings,
    timestamp,
    candidate,
    *,
    deps: PostToolUseDeps,
):
    file_path = deps.normalize_path(candidate, ctx.project_root)
    if not file_path:
        deps.log_event_fn(ctx.project_root, "post_tool_use_ignored_path", client_id=ctx.client_id, path=candidate)
        return False
    return _process_single_edit(
        ctx, state_snapshot, settings, file_path, timestamp, deps=deps,
    )


def _run_post_tool_use(
    ctx,
    *,
    deps: PostToolUseDeps | None = None,
):
    deps = deps or _current_module_deps()
    project_root = ctx.project_root
    client_id = ctx.client_id
    settings = ctx.settings
    payload = ctx.payload
    if not settings.core.enabled:
        deps.log_event_fn(project_root, "post_tool_use_disabled", client_id=client_id)
        return 0

    state_snapshot = deps.load_state_snapshot(project_root, client_id)
    timestamp = deps.now()

    for candidate in deps.extract_file_paths(payload, project_root=project_root):
        _process_path_candidate(
            ctx, state_snapshot, settings, timestamp, candidate,
            deps=deps,
        )
    return 0


def main():
    return run_hook(_run_post_tool_use, raw_input=sys.stdin.read(), event_type="post_tool_use_error")


if __name__ == "__main__":
    raise SystemExit(main())
