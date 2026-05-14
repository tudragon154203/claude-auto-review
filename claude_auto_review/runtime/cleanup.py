import shutil
import time

from claude_auto_review.constants import SECONDS_PER_HOUR
from claude_auto_review.paths import CLIENTS_DIR, RUNTIME_DIR, client_state_path, get_client_runtime_dir, invalidate_client_runtime_dir_cache
from claude_auto_review.runtime.context import resolve_client_id, resolve_project_root
from claude_auto_review.runtime.events import log_event, log_failure
from claude_auto_review.runtime.pending_cleanup import cleanup_expired_pending_reviews
from claude_auto_review.settings import DEFAULT_SETTINGS, SETTING_STALE_CLIENT_TIMEOUT, load_settings
from claude_auto_review.state.store_read import read_jsonl_records
from claude_auto_review.utils.datetime_utils import hours_since


def _remove_path(target, project_root=None):
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
    for child_name in ("run", "reviews", "clients"):
        yield runtime / child_name


def _entry_timestamp(entry) -> str:
    if isinstance(entry, dict):
        return entry.get("timestamp", "")
    return getattr(entry, "timestamp", "")


def _is_stale_entry(entry, timeout_hours) -> bool:
    timestamp = _entry_timestamp(entry)
    if not timestamp:
        return False
    age = hours_since(timestamp)
    return age is not None and age > timeout_hours


def _client_state_mtime_hours(state_path):
    st = state_path.parent.stat()
    return (time.time() - st.st_mtime) / SECONDS_PER_HOUR


def _is_client_state_stale(state_path, timeout_hours):
    if not state_path.is_file():
        return _client_state_mtime_hours(state_path) > timeout_hours
    last_entry = _read_last_jsonl_entry(state_path)
    return bool(last_entry) and _is_stale_entry(last_entry, timeout_hours)


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
    return []


def _read_last_jsonl_entry(state_path):
    try:
        last_entry = None
        for _, raw in read_jsonl_records(state_path):
            if isinstance(raw, dict):
                last_entry = raw
        return last_entry
    except OSError:
        pass
    return None


def _is_safe_client_dir(client_dir, clients_dir_resolved):
    try:
        client_dir_resolved = client_dir.resolve()
    except OSError:
        return False
    try:
        client_dir_resolved.relative_to(clients_dir_resolved)
    except ValueError:
        return False
    return True


def _is_client_stale(state_path, timeout_hours):
    return _is_client_state_stale(state_path, timeout_hours)


def cleanup_stale_clients(project_root=None):
    """Remove client directories that have not seen any activity for a while."""
    project_root = resolve_project_root(project_root)
    settings = load_settings(project_root)
    timeout_hours = settings.get(SETTING_STALE_CLIENT_TIMEOUT, DEFAULT_SETTINGS[SETTING_STALE_CLIENT_TIMEOUT])

    clients_dir = project_root / CLIENTS_DIR
    if not clients_dir.is_dir():
        return []

    try:
        clients_dir_resolved = clients_dir.resolve()
    except OSError:
        return []

    removed = []
    for client_dir in clients_dir.iterdir():
        if not client_dir.is_dir() or not client_dir.name.startswith("client-"):
            continue
        if not _is_safe_client_dir(client_dir, clients_dir_resolved):
            continue

        state_path = client_dir / "state.jsonl"
        if _is_client_stale(state_path, timeout_hours):
            if _remove_tree(client_dir, project_root=project_root):
                invalidate_client_runtime_dir_cache(project_root, client_dir.name)
                removed.append(client_dir)

    if removed:
        log_event(
            project_root,
            "stale_clients_cleaned",
            count=len(removed),
            timeout_hours=timeout_hours,
        )
    return removed
