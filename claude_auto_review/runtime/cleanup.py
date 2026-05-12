import shutil

from claude_auto_review.paths import RUNTIME_DIR, get_client_runtime_dir
from claude_auto_review.runtime.helpers import log_event, log_failure, resolve_client_id, resolve_project_root
from claude_auto_review.runtime.pending_cleanup import cleanup_expired_pending_reviews


def _remove_tree(target, project_root=None):
    try:
        if target.is_dir():
            shutil.rmtree(target)
            return True
        elif target.exists():
            target.unlink()
            return True
        return False
    except OSError as error:
        if project_root is not None:
            log_failure(project_root, "runtime_cleanup_failed", error, operation="remove_tree", target=str(target))
        return False


def _remove_empty_runtime_dir(runtime, project_root=None):
    try:
        if runtime.exists() and not any(runtime.iterdir()):
            runtime.rmdir()
            return True
    except OSError as error:
        if project_root is not None:
            log_failure(project_root, "runtime_cleanup_failed", error, operation="rmdir", target=str(runtime))
    return False


def cancel_runtime(project_root=None, client_id=""):
    project_root = resolve_project_root(project_root)
    removed = []
    if client_id:
        client_dir = get_client_runtime_dir(project_root, client_id)
        if _remove_tree(client_dir, project_root=project_root):
            removed.append(client_dir)
        return removed
    runtime = project_root / RUNTIME_DIR
    if runtime.exists():
        for target in [
            runtime / "run",
            runtime / "reviews",
            runtime / "clients",
        ]:
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
        removed.append(client_dir)
        return removed
    return []
