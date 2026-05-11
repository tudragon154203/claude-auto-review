import json
from pathlib import Path

from claude_auto_review.paths import get_project_root

DEFAULT_SETTINGS = {
    "enabled": True,
    "rulesFile": str(Path(".claude") / "claude-auto-review" / "rules.md"),
    "includeExtensions": [],
    "skipExtensions": [],
    "maxStopPasses": 3,
    "pendingReviewTimeoutHours": 1,
    "reviewerTimeoutSeconds": 600,
    "lastAssistantMessageClassifierEnabled": True,
    "lastAssistantMessageClassifierTimeoutSeconds": 10,
}


def _settings_path(project_root):
    return Path(project_root or get_project_root()) / ".claude" / "settings.json"


def _load_settings_document(settings_path):
    try:
        data = json.loads(settings_path.read_text(encoding="utf-8")) if settings_path.exists() else {}
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def load_settings(project_root=None):
    settings_path = _settings_path(project_root)
    data = _load_settings_document(settings_path)
    plugin_settings = data.get("claude-auto-review", {})
    return {**DEFAULT_SETTINGS, **plugin_settings} if isinstance(plugin_settings, dict) else dict(DEFAULT_SETTINGS)


def resolve_rules_file_path(project_root, settings):
    rules_path = Path(settings.get("rulesFile", ""))
    if not rules_path.is_absolute():
        rules_path = Path(project_root) / ".claude" / "claude-auto-review" / "rules.md"
    return rules_path


def should_skip_file(file_path, settings=None):
    settings = settings or DEFAULT_SETTINGS
    ext = Path(file_path).suffix.lstrip(".").lower()
    include_extensions = [str(value).lstrip(".").lower() for value in settings.get("includeExtensions", [])]
    skip_extensions = [str(value).lstrip(".").lower() for value in settings.get("skipExtensions", [])]
    if include_extensions and ext not in include_extensions:
        return True
    return bool(ext and ext in skip_extensions)


