import json
from pathlib import Path

from claude_auto_review.config.io import PLUGIN_SETTINGS_KEY, _settings_path, load_settings_document
from claude_auto_review.config.models import PluginSettings
from claude_auto_review.runtime.hook_identity import (
    is_plugin_hook,
    plugin_script_name_from_hook,
)


def load_hooks_document(hooks_path: Path):
    try:
        data = json.loads(hooks_path.read_text(encoding="utf-8")) if hooks_path.exists() else {}
    except (OSError, json.JSONDecodeError):
        return {"hooks": {}}
    return data if isinstance(data, dict) else {"hooks": {}}


def merge_unique_hook_list(existing_items, desired_items):
    existing = list(existing_items) if isinstance(existing_items, list) else []
    desired = list(desired_items) if isinstance(desired_items, list) else []
    seen = set()

    def seen_key(item):
        if isinstance(item, dict) and is_plugin_hook(item):
            return ("__plugin__", plugin_script_name_from_hook(item))
        return ("__plain__", json.dumps(item, sort_keys=True, ensure_ascii=False))

    merged = []
    for item in existing:
        key = seen_key(item)
        if key not in seen:
            merged.append(item)
            seen.add(key)

    for item in desired:
        key = seen_key(item)
        if key not in seen:
            merged.append(item)
            seen.add(key)
        elif key[0] == "__plugin__":
            for index, merged_item in enumerate(merged):
                if seen_key(merged_item) == key:
                    merged[index] = item
                    break

    return merged


def merge_hook_buckets(existing_hooks, desired_hooks):
    merged = dict(existing_hooks) if isinstance(existing_hooks, dict) else {}
    for hook_name, desired_entries in desired_hooks.items():
        merged[hook_name] = merge_unique_hook_list(merged.get(hook_name, []), desired_entries)
    return merged


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
