import shutil

from claude_auto_review.runtime.core.events import log_failure


def _is_contained(target, parent):
    try:
        target.resolve().relative_to(parent.resolve())
    except (OSError, ValueError):
        return False
    return True


def _remove_path(target, project_root=None):
    if project_root is not None and not _is_contained(target, project_root):
        log_failure(project_root, "runtime_cleanup_failed", RuntimeError("path escapes project root"),
                    operation="remove_tree", target=str(target))
        return False
    try:
        if target.is_dir():
            shutil.rmtree(target)
            return True
        if target.exists():
            target.unlink()
            return True
        return False
    except OSError as error:
        if project_root is not None:
            log_failure(project_root, "runtime_cleanup_failed", error, operation="remove_tree", target=str(target))
        return False


def _remove_tree(target, project_root=None):
    return _remove_path(target, project_root=project_root)


def _remove_empty_runtime_dir(runtime, project_root=None):
    try:
        if runtime.exists() and not any(runtime.iterdir()):
            runtime.rmdir()
            return True
    except OSError as error:
        if project_root is not None:
            log_failure(project_root, "runtime_cleanup_failed", error, operation="rmdir", target=str(runtime))
        return False


def _iter_runtime_cleanup_targets(runtime):
    for name in ("run", "reviews", "clients"):
        yield runtime / name
