from __future__ import annotations

from claude_auto_review.config.io import load_settings
from claude_auto_review.paths.path_utils import get_project_root
from claude_auto_review.runtime.client_dirs import get_client_id
from claude_auto_review.runtime.context import get_payload_session_id, read_json_payload
from claude_auto_review.runtime.setup import ensure_client_runtime
from claude_auto_review.stop.orchestration.context import RuntimeContext



def build_hook_runtime_context(raw="", *, payload=None, ensure_client=True):
    project_root = get_project_root()
    payload = read_json_payload(raw) if payload is None else payload
    client_id = get_client_id(get_payload_session_id(payload))
    if ensure_client:
        ensure_client_runtime(project_root, client_id)
    return RuntimeContext(
        project_root=project_root,
        client_id=client_id,
        settings=load_settings(project_root),
        payload=payload,
    )
