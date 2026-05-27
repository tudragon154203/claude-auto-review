from __future__ import annotations

from claude_auto_review.paths.path_utils import RUNTIME_DIR
from claude_auto_review.runtime.client_dirs import get_client_runtime_dir, invalidate_client_runtime_dir_cache
from claude_auto_review.runtime.cleanup.paths import _iter_runtime_cleanup_targets, _remove_empty_runtime_dir, _remove_tree
from claude_auto_review.runtime.context import resolve_client_id, resolve_project_root


def cancel_runtime(project_root=None, client_id=""):
    project_root = resolve_project_root(project_root)
    removed = []
    if client_id:
        client_dir = get_client_runtime_dir(project_root, client_id)
        if _remove_tree(client_dir, project_root=project_root):
            invalidate_client_runtime_dir_cache(project_root, client_id)
            removed.append(client_dir)
        return removed
    runtime = project_root / RUNTIME_DIR
    if runtime.exists():
        for target in _iter_runtime_cleanup_targets(runtime):
            if _remove_tree(target, project_root=project_root):
                removed.append(target)
        if _remove_empty_runtime_dir(runtime, project_root=project_root):
            removed.append(runtime)
    return removed


def cancel_session(project_root=None, client_id=""):
    project_root = resolve_project_root(project_root)
    client_id = resolve_client_id(client_id)
    client_dir = get_client_runtime_dir(project_root, client_id)
    removed = []
    if _remove_tree(client_dir, project_root=project_root):
        invalidate_client_runtime_dir_cache(project_root, client_id)
        removed.append(client_dir)
    return removed
