import json
from pathlib import Path

from claude_auto_review.paths.path_utils import get_log_path, local_now_iso


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
        log_path = get_log_path(project_root)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        entry = {"timestamp": local_now_iso(), "type": event_type}
        if client_id:
            entry["clientId"] = client_id
        entry.update(_json_safe(kwargs))
        with log_path.open("a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(entry, separators=(",", ":"), default=str) + "\n")
        return True
    except OSError:
        return False


def log_failure(project_root, event_type, error, client_id=None, **kwargs):
    return log_event(project_root, event_type, client_id=client_id, error=str(error), **kwargs)
