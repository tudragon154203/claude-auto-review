from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from claude_auto_review.config.io import load_settings
from claude_auto_review.config.models import PluginSettings
from claude_auto_review.paths.path_utils import get_project_root
from claude_auto_review.runtime.client_dirs import get_client_id
from claude_auto_review.runtime.context import get_payload_session_id, read_json_payload
from claude_auto_review.runtime.setup import ensure_client_runtime


@dataclass(frozen=True)
class HookRuntimeContext:
    project_root: Path
    client_id: str
    settings: PluginSettings = field(default_factory=PluginSettings)
    payload: dict[str, Any] = field(default_factory=dict)


def build_hook_runtime_context(raw="", *, payload=None, ensure_client=True):
    project_root = get_project_root()
    payload = read_json_payload(raw) if payload is None else payload
    client_id = get_client_id(get_payload_session_id(payload))
    if ensure_client:
        ensure_client_runtime(project_root, client_id)
    return HookRuntimeContext(
        project_root=project_root,
        client_id=client_id,
        settings=load_settings(project_root),
        payload=payload,
    )
