import json
from pathlib import Path

from claude_auto_review.paths import get_project_root

DEFAULT_SETTINGS = {
    "enabled": True,
    "rulesFile": str(Path(".claude") / "claude-auto-review" / "rules.md"),
    "includeExtensions": [],
    "skipExtensions": [],
    "minSeverity": "MEDIUM",
    "autoFix": True,
    "maxStopPasses": 3,
    "pendingReviewTimeoutHours": 1,
}


def load_settings(project_root=None):
    project_root = Path(project_root or get_project_root())
    settings_path = project_root / ".claude" / "settings.json"
    try:
        data = json.loads(settings_path.read_text(encoding="utf-8")) if settings_path.exists() else {}
        plugin_settings = data.get("claude-auto-review", {}) if isinstance(data, dict) else {}
        return {**DEFAULT_SETTINGS, **plugin_settings}
    except (OSError, json.JSONDecodeError):
        return dict(DEFAULT_SETTINGS)


def should_skip_file(file_path, settings=None):
    settings = settings or DEFAULT_SETTINGS
    ext = Path(file_path).suffix.lstrip(".").lower()
    include_extensions = [str(value).lstrip(".").lower() for value in settings.get("includeExtensions", [])]
    skip_extensions = [str(value).lstrip(".").lower() for value in settings.get("skipExtensions", [])]
    if include_extensions and ext not in include_extensions:
        return True
    return bool(ext and ext in skip_extensions)


