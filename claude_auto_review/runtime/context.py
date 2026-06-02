"""Project root and client ID resolution."""

from __future__ import annotations

from pathlib import Path

from claude_auto_review.paths.path_utils import get_project_root
from claude_auto_review.runtime.client_dirs import get_client_id


class _ClientIdCache:
    """Explicit cache object replacing raw global mutation."""

    def __init__(self):
        self._value: str | None = None

    def get(self, client_id: str = "") -> str:
        if client_id:
            return client_id
        if self._value is None:
            self._value = get_client_id()
        return self._value

    def reset(self) -> None:
        self._value = None


_CLIENT_ID_CACHE = _ClientIdCache()


def resolve_project_root(project_root=None) -> Path:
    return Path(project_root or get_project_root())


def resolve_client_id(client_id="") -> str:
    return _CLIENT_ID_CACHE.get(client_id)
