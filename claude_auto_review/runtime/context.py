import json
from pathlib import Path

from claude_auto_review.runtime.client_dirs import get_client_id
from claude_auto_review.paths.path_utils import get_project_root

_DEFAULT_CLIENT_ID = None


def resolve_project_root(project_root=None):
    return Path(project_root or get_project_root())


def resolve_client_id(client_id=""):
    global _DEFAULT_CLIENT_ID
    if client_id:
        return client_id
    if _DEFAULT_CLIENT_ID is None:
        _DEFAULT_CLIENT_ID = get_client_id()
    return _DEFAULT_CLIENT_ID


def read_json_payload(raw):
    raw = raw.strip()
    return json.loads(raw) if raw else {}


def get_payload_session_id(payload):
    if isinstance(payload, dict):
        return payload.get("session_id")
    return None
