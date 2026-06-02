from __future__ import annotations

from pathlib import Path

from claude_auto_review.config.settings.models import PluginSettings
from claude_auto_review.paths.path_utils import is_runtime_relative_path


def _normalize_extensions(extensions: tuple[str, ...]) -> list[str]:
    return [str(value).lstrip(".").lower() for value in extensions]


def should_skip_file(file_path, settings: PluginSettings | None = None):
    settings = settings or PluginSettings()
    if is_runtime_relative_path(file_path):
        return True
    ext = Path(file_path).suffix.lstrip(".").lower()
    include_extensions = _normalize_extensions(settings.filters.include_extensions)
    skip_extensions = _normalize_extensions(settings.filters.skip_extensions)
    if include_extensions and ext not in include_extensions:
        return True
    return bool(ext and ext in skip_extensions)
