import os
from pathlib import Path
from urllib.parse import unquote, urlsplit

from claude_auto_review.paths.path_utils import FILE_URI_PREFIX, _project_root_path


def _normalize_file_uri(file_path: str) -> str:
    if not file_path.startswith(FILE_URI_PREFIX):
        return file_path
    parts = urlsplit(file_path)
    if parts.scheme != "file":
        return file_path
    if os.name == "nt" and parts.netloc and ":" in parts.netloc and not parts.path:
        return unquote(parts.netloc)
    path = unquote(parts.path or "")
    if parts.netloc and parts.netloc.lower() != "localhost":
        return f"//{parts.netloc}{path}"
    if os.name == "nt" and path.startswith("/") and len(path) > 2 and path[2] == ":":
        return path[1:]
    return path


def normalize_relative_path(file_path, project_root=None):
    if not file_path:
        return None
    file_path = _normalize_file_uri(os.fspath(file_path))
    project_root = _project_root_path(project_root)
    candidate = Path(file_path)
    resolved = candidate.resolve() if candidate.is_absolute() else (project_root / candidate).resolve()
    try:
        relative = resolved.relative_to(project_root)
    except ValueError:
        return None
    if not relative.parts:
        return None
    return relative.as_posix()
