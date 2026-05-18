from pathlib import Path

from claude_auto_review.runtime.client_dirs import get_existing_client_runtime_dir
from claude_auto_review.paths.path_utils import get_state_path, local_now_iso
from claude_auto_review.runtime.context import resolve_project_root
from claude_auto_review.state.store.write import write_jsonl_line


def _json_safe(value):
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Exception):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, set):
        return sorted((_json_safe(item) for item in value), key=repr)
    return value


def log_event(project_root, event_type, client_id=None, **kwargs):
    try:
        project_root = resolve_project_root(project_root)
        if client_id:
            client_dir = get_existing_client_runtime_dir(project_root, client_id)
            target_path = (client_dir / "state.jsonl") if client_dir is not None else get_state_path(project_root)
        else:
            target_path = get_state_path(project_root)
        entry = {"timestamp": local_now_iso(), "type": event_type}
        if client_id:
            entry["clientId"] = client_id
        entry.update(_json_safe(kwargs))
        write_jsonl_line(target_path, entry)
        return True
    except OSError:
        return False


def log_failure(project_root, event_type, error, client_id=None, **kwargs):
    return log_event(project_root, event_type, client_id=client_id, error=str(error), **kwargs)
