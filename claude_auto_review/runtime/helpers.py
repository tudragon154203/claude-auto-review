import json
from pathlib import Path

from claude_auto_review.paths import get_client_id, get_log_path, get_project_root, local_now_iso


def resolve_project_root(project_root=None):
    return Path(project_root or get_project_root())


def resolve_client_id(client_id=""):
    return client_id or get_client_id()


def read_json_payload(raw):
    raw = raw.strip()
    return json.loads(raw) if raw else {}


def log_event(project_root, event_type, **kwargs):
    try:
        log_path = get_log_path(project_root)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        entry = {"timestamp": local_now_iso(), "type": event_type, **kwargs}
        with log_path.open("a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(entry, separators=(",", ":")) + "\n")
    except OSError:
        pass


def log_failure(project_root, event_type, error, **kwargs):
    try:
        log_event(project_root, event_type, error=str(error), **kwargs)
        return True
    except Exception:
        return False


def get_payload_session_id(payload):
    if isinstance(payload, dict):
        return payload.get("session_id")
    return None


def run_fail_open(callback, *, project_root=None, event_type=None, on_error=None, fallback=0):
    try:
        return callback()
    except Exception as error:
        handled = False
        if on_error is not None:
            try:
                handled = bool(on_error(error))
            except Exception:
                handled = False
        if event_type and not handled:
            log_failure(project_root, event_type, error)
        return fallback
