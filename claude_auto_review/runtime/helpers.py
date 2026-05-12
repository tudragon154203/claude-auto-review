import json
from pathlib import Path

from claude_auto_review.paths import get_client_id, get_log_path, get_project_root, local_now_iso


def resolve_project_root(project_root=None):
    return Path(project_root or get_project_root())


def resolve_client_id(client_id=""):
    return client_id or get_client_id()


def log_event(project_root, event_type, **kwargs):
    try:
        log_path = get_log_path(project_root)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        entry = {"timestamp": local_now_iso(), "type": event_type, **kwargs}
        with log_path.open("a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(entry, separators=(",", ":")) + "\n")
    except OSError:
        pass
