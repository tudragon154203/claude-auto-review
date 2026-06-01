from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from claude_auto_review.config.io import load_settings
from claude_auto_review.paths.path_utils import get_project_root
from claude_auto_review.runtime.client_dirs import get_client_id
from claude_auto_review.runtime.context import get_payload_session_id, read_json_payload
from claude_auto_review.runtime.setup import ensure_client_runtime
from claude_auto_review.stop.orchestration.context import RuntimeContext


@runtime_checkable
class HookContextFactory(Protocol):
    def project_root(self) -> str: ...
    def client_id(self, payload: dict) -> str: ...
    def payload(self, raw: str) -> Any: ...
    def ensure_runtime(self, project_root: str, client_id: str) -> None: ...
    def load_settings(self, project_root: str) -> Any: ...


@dataclass(frozen=True)
class DefaultHookContextFactory:
    def project_root(self) -> str:
        return str(get_project_root())

    def client_id(self, payload: dict) -> str:
        return get_client_id(get_payload_session_id(payload))

    def payload(self, raw: str) -> Any:
        return read_json_payload(raw)

    def ensure_runtime(self, project_root: str, client_id: str) -> None:
        ensure_client_runtime(project_root, client_id)

    def load_settings(self, project_root: str) -> Any:
        return load_settings(project_root)


_DEFAULT_FACTORY = DefaultHookContextFactory()


def build_hook_runtime_context(raw="", *, payload=None, ensure_client=True, factory: HookContextFactory = _DEFAULT_FACTORY):
    project_root = factory.project_root()
    payload = factory.payload(raw) if payload is None else payload
    client_id = factory.client_id(payload)
    if ensure_client:
        factory.ensure_runtime(project_root, client_id)
    return RuntimeContext(
        project_root=Path(project_root),
        client_id=client_id,
        settings=factory.load_settings(project_root),
        payload=payload,
    )
