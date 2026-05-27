import json

from claude_auto_review.config.models import PluginSettings
from claude_auto_review.runtime.context import resolve_project_root


SETTINGS_FILENAME = "settings.json"
PLUGIN_SETTINGS_KEY = "claude-auto-review"


def _settings_path(project_root):
    return resolve_project_root(project_root) / ".claude" / SETTINGS_FILENAME


def _load_settings_document(settings_path):
    try:
        data = json.loads(settings_path.read_text(encoding="utf-8")) if settings_path.exists() else {}
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def load_settings_document(project_root=None) -> dict:
    return _load_settings_document(_settings_path(project_root))


def load_settings(project_root=None) -> PluginSettings:
    data = load_settings_document(project_root)
    plugin_settings = data.get(PLUGIN_SETTINGS_KEY, {})
    return PluginSettings.from_mapping(plugin_settings if isinstance(plugin_settings, dict) else {})
