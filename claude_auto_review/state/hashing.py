"""File-content hashing for state tracking."""

from __future__ import annotations

import hashlib
from pathlib import Path

from claude_auto_review.paths.uri_utils import normalize_relative_path
from claude_auto_review.runtime.context import resolve_project_root


def get_file_hash(file_path: str | Path, project_root: str | Path | None = None) -> str | None:
    project_root = resolve_project_root(project_root)
    relative = normalize_relative_path(file_path, project_root)
    if not relative:
        return None
    full_path = project_root / relative
    if not full_path.is_file():
        return None
    return hashlib.sha256(full_path.read_bytes()).hexdigest()[:8]
