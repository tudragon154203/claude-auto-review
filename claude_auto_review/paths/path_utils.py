"""Path constants and resolvers.

Use ``ProjectContext.from_environment()`` or ``ProjectContext.for_project_root()``
to resolve project and plugin roots.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

RUNTIME_DIR_STR = ".claude/claude-auto-review"
STATE_RELATIVE_PATH = Path(RUNTIME_DIR_STR) / "state.jsonl"
RUNTIME_DIR = Path(RUNTIME_DIR_STR)
CLIENTS_DIR = RUNTIME_DIR / "clients"
GITIGNORE_ENTRY = f"{RUNTIME_DIR_STR}/"
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


def is_runtime_relative_path(file_path):
    if not file_path:
        return False
    candidate = Path(os.fspath(file_path))
    try:
        relative = candidate.relative_to(RUNTIME_DIR)
    except ValueError:
        return False
    return bool(relative.parts)


def get_state_path(project_root: Path | str | None = None) -> Path:
    """Return the path to the runtime state directory."""
    ctx = ProjectContext.from_environment() if project_root is None else ProjectContext.for_project_root(project_root)
    return ctx.project_root / RUNTIME_DIR / STATE_RELATIVE_PATH.name
