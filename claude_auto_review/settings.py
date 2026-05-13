import json
from pathlib import Path

from claude_auto_review.paths import get_project_root, is_runtime_relative_path

# Setting keys for easy reference
SETTING_ENABLED = "enabled"
SETTING_RULES_FILE = "rulesFile"
SETTING_INCLUDE_EXTS = "includeExtensions"
SETTING_SKIP_EXTS = "skipExtensions"
SETTING_MAX_STOP_PASSES = "maxStopPasses"
SETTING_PENDING_TIMEOUT = "pendingReviewTimeoutHours"
SETTING_REVIEWER_TIMEOUT = "reviewerTimeoutSeconds"
SETTING_FEEDBACK_MAX_CHARS = "reviewFeedbackMaxChars"
SETTING_CLASSIFIER_ENABLED = "lastAssistantMessageClassifierEnabled"
SETTING_CLASSIFIER_TIMEOUT = "lastAssistantMessageClassifierTimeoutSeconds"
SETTING_STALE_CLIENT_TIMEOUT = "staleClientTimeoutHours"

DEFAULT_TIMEOUT_SECONDS = 20

# Default settings for the plugin
DEFAULT_SETTINGS = {
    SETTING_ENABLED: True,
    SETTING_RULES_FILE: str(Path(".claude") / "claude-auto-review" / "review-rules.md"),
    SETTING_INCLUDE_EXTS: [],
    SETTING_SKIP_EXTS: [],
    SETTING_MAX_STOP_PASSES: 3,
    SETTING_PENDING_TIMEOUT: 1,
    SETTING_REVIEWER_TIMEOUT: 600,
    SETTING_FEEDBACK_MAX_CHARS: 9000,
    SETTING_CLASSIFIER_ENABLED: True,
    SETTING_CLASSIFIER_TIMEOUT: 20,
    SETTING_STALE_CLIENT_TIMEOUT: 48,
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
    rules_value = settings.get(SETTING_RULES_FILE, DEFAULT_SETTINGS[SETTING_RULES_FILE])
    rules_path = Path(rules_value)
    if rules_path.is_absolute():
        return rules_path
    return Path(project_root) / rules_path


def should_skip_file(file_path, settings=None):
    settings = settings or DEFAULT_SETTINGS
    if is_runtime_relative_path(file_path):
        return True
    ext = Path(file_path).suffix.lstrip(".").lower()
    include_extensions = [str(value).lstrip(".").lower() for value in settings.get(SETTING_INCLUDE_EXTS, [])]
    skip_extensions = [str(value).lstrip(".").lower() for value in settings.get(SETTING_SKIP_EXTS, [])]
    if include_extensions and ext not in include_extensions:
        return True
    return bool(ext and ext in skip_extensions)


