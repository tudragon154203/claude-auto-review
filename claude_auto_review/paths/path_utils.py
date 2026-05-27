from __future__ import annotations

import os
from pathlib import Path

from claude_auto_review.timestamps import local_now_iso

STATE_RELATIVE_PATH = Path(".claude") / "claude-auto-review" / "state.jsonl"
RUNTIME_DIR = Path(".claude") / "claude-auto-review"
CLIENTS_DIR = RUNTIME_DIR / "clients"
DELETED_FILE_HASH = "__deleted__"
FILE_URI_PREFIX = "file://"

def get_project_root():
    return Path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())).resolve()


def get_plugin_root():
    """Return the ``claude_auto_review`` package directory."""
    return Path(__file__).resolve().parent.parent


def get_reviewer_prompt_script():
    return get_plugin_root() / "review" / "prompt.py"


def _project_root_path(project_root=None):
    return Path(project_root or get_project_root()).resolve()


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
