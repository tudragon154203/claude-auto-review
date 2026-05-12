from datetime import datetime
import shutil
import json

from claude_auto_review.paths import CLIENTS_DIR, RUNTIME_DIR, client_state_path, get_client_runtime_dir
from claude_auto_review.runtime.helpers import log_event, log_failure, resolve_client_id, resolve_project_root
from claude_auto_review.runtime.pending_cleanup import cleanup_expired_pending_reviews
from claude_auto_review.settings import SETTING_STALE_CLIENT_TIMEOUT, load_settings
from claude_auto_review.state.review_expiry import is_review_expired


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


def cleanup_stale_clients(project_root=None):
    """Remove client directories that have not seen any activity for a while."""
    project_root = resolve_project_root(project_root)
    settings = load_settings(project_root)
    timeout_hours = settings.get(SETTING_STALE_CLIENT_TIMEOUT, 48)

    clients_dir = project_root / CLIENTS_DIR
    if not clients_dir.is_dir():
        return []

    removed = []
    for client_dir in clients_dir.iterdir():
        if not client_dir.is_dir() or not client_dir.name.startswith("client-"):
            continue

        state_path = client_dir / "state.jsonl"
        if not state_path.is_file():
            # If no state file, we can't judge activity.
            # But let's check directory modification time as fallback.
            st = state_path.parent.stat()
            age_hours = (datetime.now().timestamp() - st.st_mtime) / 3600.0
            if age_hours > timeout_hours:
                if _remove_tree(client_dir, project_root=project_root):
                    removed.append(client_dir)
            continue

        # Try to find the last activity timestamp in the state file
        last_entry = None
        try:
            with state_path.open("rb") as f:
                try:
                    f.seek(-2, 2)
                    while f.read(1) != b"\n":
                        f.seek(-2, 1)
                except OSError:
                    f.seek(0)
                last_line = f.read().decode("utf-8").strip()
                if last_line:
                    last_entry = json.loads(last_line)
        except (OSError, json.JSONDecodeError):
            pass

        if last_entry and is_review_expired(last_entry, timeout_hours):
            if _remove_tree(client_dir, project_root=project_root):
                removed.append(client_dir)

    if removed:
        log_event(
            project_root,
            "stale_clients_cleaned",
            count=len(removed),
            timeout_hours=timeout_hours,
        )
    return removed
