import json
import shutil
from pathlib import Path

from claude_auto_review.paths import (
    LOG_RELATIVE_PATH,
    RUNTIME_DIR,
    STATE_RELATIVE_PATH,
    get_client_runtime_dir,
    get_plugin_root,
    get_project_root,
)
from claude_auto_review.runtime.helpers import resolve_project_root
from claude_auto_review.settings import DEFAULT_SETTINGS, _load_settings_document, _settings_path


def _load_hooks_document(plugin_root):
    hooks_path = Path(plugin_root) / "hooks" / "hooks.json"
    try:
        data = json.loads(hooks_path.read_text(encoding="utf-8")) if hooks_path.exists() else {}
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _merge_unique_list(existing_items, desired_items):
    merged = list(existing_items) if isinstance(existing_items, list) else []
    seen = {
        json.dumps(item, sort_keys=True, ensure_ascii=False)
        for item in merged
    }
    for item in desired_items if isinstance(desired_items, list) else []:
        marker = json.dumps(item, sort_keys=True, ensure_ascii=False)
        if marker not in seen:
            merged.append(item)
            seen.add(marker)
    return merged


def _merge_hooks(existing_hooks, desired_hooks):
    merged = dict(existing_hooks) if isinstance(existing_hooks, dict) else {}
    for hook_name, desired_entries in desired_hooks.items():
        merged[hook_name] = _merge_unique_list(merged.get(hook_name, []), desired_entries)
    return merged


def ensure_client_runtime(project_root, client_id):
    client_dir = get_client_runtime_dir(project_root, client_id)
    client_dir.mkdir(parents=True, exist_ok=True)
    (client_dir / "state.jsonl").touch(exist_ok=True)
    (client_dir / "reviews").mkdir(exist_ok=True)
    (client_dir / "run").mkdir(exist_ok=True)
    return client_dir


def ensure_runtime(project_root=None, plugin_root=None):
    project_root = resolve_project_root(project_root)
    plugin_root = Path(plugin_root or get_plugin_root())
    base_dir = project_root / RUNTIME_DIR
    base_dir.mkdir(parents=True, exist_ok=True)
    state_path = project_root / STATE_RELATIVE_PATH
    state_path.parent.mkdir(parents=True, exist_ok=True)

    rules_path = base_dir / "review-rules.md"
    if not rules_path.exists():
        default_rules_path = plugin_root / "rules" / "review-rules.md"
        if default_rules_path.exists():
            shutil.copyfile(default_rules_path, rules_path)
        else:
            rules_path.write_text(
                "# Claude Auto Review Rules\n\n- Review semantic correctness, security, and maintainability.\n",
                encoding="utf-8",
            )

    return {
        "base_dir": base_dir,
        "state_path": state_path,
        "rules_path": rules_path,
        "log_path": project_root / LOG_RELATIVE_PATH,
    }


def ensure_project_settings(project_root=None):
    project_root = Path(project_root or get_project_root())
    plugin_root = Path(get_plugin_root())
    settings_path = _settings_path(project_root)
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings = _load_settings_document(settings_path)
    hooks_document = _load_hooks_document(plugin_root)

    if "claude-auto-review" not in settings:
        settings["claude-auto-review"] = dict(DEFAULT_SETTINGS)
    if hooks_document.get("hooks"):
        settings["hooks"] = _merge_hooks(settings.get("hooks", {}), hooks_document["hooks"])
    settings_path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8", newline="\n")
    return settings_path
