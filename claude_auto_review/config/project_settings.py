from __future__ import annotations

import json

from claude_auto_review.config.hooks_merge import (
    merge_hook_buckets,
)
from claude_auto_review.config.io import PLUGIN_SETTINGS_KEY, _settings_path, load_settings_document
from claude_auto_review.config.models import PluginSettings


def normalize_plugin_settings(settings: dict):
    plugin_settings = settings.get(PLUGIN_SETTINGS_KEY, {})
    settings[PLUGIN_SETTINGS_KEY] = PluginSettings.from_mapping(plugin_settings).to_mapping()


def merge_project_settings_document(settings: dict, hooks_document: dict):
    normalize_plugin_settings(settings)
    desired_hooks = hooks_document.get("hooks")
    if desired_hooks:
        settings["hooks"] = merge_hook_buckets(settings.get("hooks", {}), desired_hooks)
    return settings


def ensure_project_settings_document(project_root, hooks_document: dict):
    settings_path = _settings_path(project_root)
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings = load_settings_document(project_root)
    merged_settings = merge_project_settings_document(settings, hooks_document)
    settings_path.write_text(json.dumps(merged_settings, indent=2) + "\n", encoding="utf-8", newline="\n")
    return settings_path
