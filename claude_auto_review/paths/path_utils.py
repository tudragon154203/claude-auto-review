"""Path constants and resolvers.

`ProjectContext` is the DIP-friendly abstraction for callers that need to
resolve the project root explicitly. Existing ``get_project_root()`` and
``get_plugin_root()`` still read implicit environment / filesystem state
for backward compatibility, but new code should prefer `ProjectContext`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

STATE_RELATIVE_PATH = Path(".claude") / "claude-auto-review" / "state.jsonl"
RUNTIME_DIR = Path(".claude") / "claude-auto-review"
CLIENTS_DIR = RUNTIME_DIR / "clients"
DELETED_FILE_HASH = "__deleted__"
FILE_URI_PREFIX = "file://"


@dataclass(frozen=True)
class ProjectContext:
    """Explicit, injectable project + plugin root pair (DIP-friendly)."""

    project_root: Path
    plugin_root: Path

    @classmethod
    def from_environment(
        cls,
        *,
        env: dict[str, str] | None = None,
        cwd: Path | str | None = None,
    ) -> ProjectContext:
        """Build a context from explicit environment / cwd (defaults to os.environ / os.getcwd)."""
        env_map = env if env is not None else os.environ
        cwd_path = Path(cwd) if cwd is not None else Path(os.getcwd())
        project_root = Path(env_map.get("CLAUDE_PROJECT_DIR", str(cwd_path))).resolve()
        plugin_root = Path(__file__).resolve().parent.parent
        return cls(project_root=project_root, plugin_root=plugin_root)

    @classmethod
    def for_project_root(cls, project_root: str | Path, *, plugin_root: Path | None = None) -> ProjectContext:
        resolved_project = Path(project_root).resolve()
        resolved_plugin = (plugin_root or Path(__file__).resolve().parent.parent).resolve()
        return cls(project_root=resolved_project, plugin_root=resolved_plugin)

    def state_path(self) -> Path:
        return self.project_root / RUNTIME_DIR / STATE_RELATIVE_PATH.name

    def runtime_dir(self) -> Path:
        return self.project_root / RUNTIME_DIR

    def reviewer_prompt_script(self) -> Path:
        return self.plugin_root / "review" / "prompt.py"


def get_project_root():
    return ProjectContext.from_environment().project_root


def get_plugin_root():
    """Return the ``claude_auto_review`` package directory."""
    return Path(__file__).resolve().parent.parent


def get_reviewer_prompt_script():
    return get_plugin_root() / "review" / "prompt.py"


def _project_root_path(project_root=None):
    if project_root is None:
        return get_project_root()
    return Path(project_root).resolve()


def _runtime_dir_path(project_root=None):
    return _project_root_path(project_root) / RUNTIME_DIR


def is_runtime_relative_path(file_path):
    if not file_path:
        return False
    candidate = Path(os.fspath(file_path))
    try:
        relative = candidate.relative_to(RUNTIME_DIR)
    except ValueError:
        return False
    return bool(relative.parts)


def get_state_path(project_root=None):
    return _runtime_dir_path(project_root) / STATE_RELATIVE_PATH.name
