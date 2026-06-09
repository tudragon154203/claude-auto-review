"""Project root and client ID resolution."""

from __future__ import annotations

from pathlib import Path
import subprocess

from claude_auto_review.paths.path_utils import ProjectContext
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
    """Resolve the effective project root for state and config lookups.

    When an explicit root is provided, it is used verbatim. Otherwise, the
    environment-derived root is refined with ``git rev-parse --show-toplevel``
    so worktrees, subdirectories, and symlinked paths all collapse to the
    repository root that git itself reports. Falls back to the environment
    root on any git error.
    """
    if project_root:
        return Path(project_root)

    resolved = ProjectContext.from_environment().project_root
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=resolved,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
        )
    except (FileNotFoundError, OSError, subprocess.CalledProcessError):
        return Path(resolved)
    return Path(result.stdout.strip())


def resolve_client_id(client_id="") -> str:
    return _CLIENT_ID_CACHE.get(client_id)
