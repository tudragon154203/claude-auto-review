import time

from claude_auto_review.config.constants import SECONDS_PER_HOUR
from claude_auto_review.config.settings import DEFAULT_SETTINGS, SETTING_STALE_CLIENT_TIMEOUT, load_settings
from claude_auto_review.paths.path_utils import CLIENTS_DIR
from claude_auto_review.runtime.client_dirs import invalidate_client_runtime_dir_cache
from claude_auto_review.runtime.cleanup.paths import _remove_tree
from claude_auto_review.runtime.context import resolve_project_root
from claude_auto_review.runtime.events import log_event, log_failure
from claude_auto_review.state.store.read import read_last_jsonl_record
from claude_auto_review.utils.datetime_utils import hours_since


def _entry_timestamp(entry):
    return (entry or {}).get("timestamp", "")


def _is_stale_entry(entry, timeout_hours):
    ts = _entry_timestamp(entry)
    if not ts:
        return True
    return hours_since(ts) is not None and hours_since(ts) > timeout_hours


def _client_state_mtime_hours(state_path, project_root=None):
    try:
        st = state_path.parent.stat()
    except OSError as error:
        if project_root is not None:
            log_failure(project_root, "runtime_cleanup_failed", error, operation="stat_state_parent", target=str(state_path))
        return None
    return (time.time() - st.st_mtime) / SECONDS_PER_HOUR


def _is_client_state_stale(state_path, timeout_hours, project_root=None):
    try:
        if not state_path.is_file():
            mtime_hours = _client_state_mtime_hours(state_path, project_root=project_root)
            return bool(mtime_hours is not None and mtime_hours > timeout_hours)
        last_entry = read_last_jsonl_record(state_path)
        if not last_entry:
            mtime_hours = _client_state_mtime_hours(state_path, project_root=project_root)
            return bool(mtime_hours is not None and mtime_hours > timeout_hours)
        return _is_stale_entry(last_entry, timeout_hours)
    except OSError as error:
        if project_root is not None:
            log_failure(project_root, "runtime_cleanup_failed", error, operation="check_stale", target=str(state_path))
        return False


def _is_client_stale(state_path, timeout_hours, project_root=None):
    return _is_client_state_stale(state_path, timeout_hours, project_root=project_root)


def _is_safe_client_dir(client_dir, clients_dir_resolved, project_root_resolved):
    try:
        client_dir_resolved = client_dir.resolve()
    except OSError:
        return False
    try:
        client_dir_resolved.relative_to(clients_dir_resolved)
        client_dir_resolved.relative_to(project_root_resolved)
    except ValueError:
        return False
    return True


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
        project_root_resolved = project_root.resolve()
    except OSError:
        return []

    removed = []
    for client_dir in clients_dir.iterdir():
        if not client_dir.is_dir() or not client_dir.name.startswith("client-"):
            continue
        if not _is_safe_client_dir(client_dir, clients_dir_resolved, project_root_resolved):
            continue

        state_path = client_dir / "state.jsonl"
        if _is_client_stale(state_path, timeout_hours, project_root=project_root):
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
