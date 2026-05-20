import json
import shutil
from importlib import resources
from pathlib import Path

from claude_auto_review.config.io import _load_settings_document, _settings_path
from claude_auto_review.config.models import PluginSettings
from claude_auto_review.paths.path_utils import (
    RUNTIME_DIR,
    STATE_RELATIVE_PATH,
)
from claude_auto_review.runtime.client_dirs import get_client_runtime_dir
from claude_auto_review.runtime.context import resolve_project_root
from claude_auto_review.runtime.hook_identity import (
    is_plugin_hook as _is_plugin_hook,
    plugin_script_name_from_hook as _get_plugin_script_name,
)


def _package_resource_path(*parts):
    return resources.files("claude_auto_review").joinpath(*parts)

def _load_hooks_document(plugin_root=None):
    hooks_path = _package_resource_path("hooks", "hooks.json") if plugin_root is None else Path(plugin_root) / "hooks" / "hooks.json"
    try:
        data = json.loads(hooks_path.read_text(encoding="utf-8")) if hooks_path.exists() else {}
    except (OSError, json.JSONDecodeError):
        return {"hooks": {}}
    return data if isinstance(data, dict) else {"hooks": {}}


def _merge_unique_list(existing_items, desired_items):
    existing = list(existing_items) if isinstance(existing_items, list) else []
    desired = list(desired_items) if isinstance(desired_items, list) else []

    seen = set()

    def _seen_key(item):
        if isinstance(item, dict) and _is_plugin_hook(item):
            return ("__plugin__", _get_plugin_script_name(item))
        return ("__plain__", json.dumps(item, sort_keys=True, ensure_ascii=False))

    # Build merged list preserving order: existing items first, then new desired items
    merged = []
    for item in existing:
        key = _seen_key(item)
        if key not in seen:
            merged.append(item)
            seen.add(key)

    for item in desired:
        key = _seen_key(item)
        if key not in seen:
            merged.append(item)
            seen.add(key)
        elif key[0] == "__plugin__":
            # Replace existing plugin hook with desired version
            for i, m in enumerate(merged):
                if _seen_key(m) == key:
                    merged[i] = item
                    break

    return merged


def _merge_hooks(existing_hooks, desired_hooks):
    merged = dict(existing_hooks) if isinstance(existing_hooks, dict) else {}
    for hook_name, desired_entries in desired_hooks.items():
        merged[hook_name] = _merge_unique_list(merged.get(hook_name, []), desired_entries)
    return merged


def _ensure_plugin_settings(settings):
    plugin_settings = settings.get("claude-auto-review", {})
    settings["claude-auto-review"] = PluginSettings.from_mapping(plugin_settings).to_mapping()


def _merge_project_hooks(settings, hooks_document):
    desired_hooks = hooks_document.get("hooks")
    if desired_hooks:
        settings["hooks"] = _merge_hooks(settings.get("hooks", {}), desired_hooks)


def _ensure_runtime_directories(base_dir, state_path):
    base_dir.mkdir(parents=True, exist_ok=True)
    state_path.parent.mkdir(parents=True, exist_ok=True)


def _ensure_rules_file(base_dir, plugin_root):
    rules_path = base_dir / "review-rules.md"
    if rules_path.exists():
        return rules_path

    if plugin_root:
        default_rules_path = Path(plugin_root) / "rules" / "review-rules.md"
    else:
        default_rules_path = _package_resource_path("rules", "review-rules.md")
    if default_rules_path.is_file():
        shutil.copyfile(default_rules_path, rules_path)
    else:
        rules_path.write_text(
            "# Claude Auto Review Rules\n\n- Review semantic correctness, security, and maintainability.\n",
            encoding="utf-8",
        )
    return rules_path


def ensure_client_runtime(project_root, client_id):
    client_dir = get_client_runtime_dir(project_root, client_id)
    client_dir.mkdir(parents=True, exist_ok=True)
    (client_dir / "state.jsonl").touch(exist_ok=True)
    (client_dir / "reviews").mkdir(exist_ok=True)
    (client_dir / "run").mkdir(exist_ok=True)
    return client_dir


def ensure_runtime(project_root=None, plugin_root=None):
    project_root = resolve_project_root(project_root)
    base_dir = project_root / RUNTIME_DIR
    state_path = project_root / STATE_RELATIVE_PATH
    _ensure_runtime_directories(base_dir, state_path)
    rules_path = _ensure_rules_file(base_dir, plugin_root)

    return {
        "base_dir": base_dir,
        "state_path": state_path,
        "rules_path": rules_path,
        "log_path": state_path,
    }


def ensure_project_settings(project_root=None):
    project_root = resolve_project_root(project_root)
    settings_path = _settings_path(project_root)
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings = _load_settings_document(settings_path)
    hooks_document = _load_hooks_document()

    _ensure_plugin_settings(settings)
    _merge_project_hooks(settings, hooks_document)
    settings_path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8", newline="\n")
    return settings_path
