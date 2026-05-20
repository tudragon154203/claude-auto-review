import json

from claude_auto_review.config.models import PluginSettings
from claude_auto_review.runtime.context import resolve_project_root


def _settings_path(project_root):
    return resolve_project_root(project_root) / ".claude" / "settings.json"


def _load_settings_document(settings_path):
    try:
        data = json.loads(settings_path.read_text(encoding="utf-8")) if settings_path.exists() else {}
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def load_settings(project_root=None) -> PluginSettings:
    settings_path = _settings_path(project_root)
    data = _load_settings_document(settings_path)
    plugin_settings = data.get("claude-auto-review", {})
    return PluginSettings.from_mapping(plugin_settings if isinstance(plugin_settings, dict) else {})
