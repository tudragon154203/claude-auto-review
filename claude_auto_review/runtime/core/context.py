import json
from pathlib import Path

from claude_auto_review.runtime.core.client_dirs import get_client_id
from claude_auto_review.paths.core.path_utils import get_project_root


def resolve_project_root(project_root=None):
    return Path(project_root or get_project_root())


def resolve_client_id(client_id=""):
    return client_id or get_client_id()


def read_json_payload(raw):
    raw = raw.strip()
    return json.loads(raw) if raw else {}


def get_payload_session_id(payload):
    if isinstance(payload, dict):
        return payload.get("session_id")
    return None
