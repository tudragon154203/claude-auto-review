import json
import shlex
import shutil
from pathlib import Path

from claude_auto_review.paths.core.path_utils import (
    LOG_RELATIVE_PATH,
    RUNTIME_DIR,
    STATE_RELATIVE_PATH,
    get_plugin_root,
)
from claude_auto_review.runtime.core.client_dirs import get_client_runtime_dir
from claude_auto_review.runtime.core.context import resolve_project_root
from claude_auto_review.config.core.settings import DEFAULT_SETTINGS, _load_settings_document, _settings_path

PLUGIN_SCRIPTS = frozenset(["post_tool_use.py", "stop_hook.py", "session_end.py"])


def _load_hooks_document(plugin_root):
    hooks_path = Path(plugin_root) / "hooks" / "hooks.json"
    try:
        data = json.loads(hooks_path.read_text(encoding="utf-8")) if hooks_path.exists() else {}
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _plugin_script_from_command(cmd):
    """Return the plugin script basename if cmd ends with one, else None."""
    if not cmd:
        return None
    try:
        parts = shlex.split(cmd, posix=False)
    except ValueError:
        parts = cmd.split()
    if not parts:
        return None
    basename = Path(parts[-1].strip("'\"")).name
    return basename if basename in PLUGIN_SCRIPTS else None


def _is_plugin_hook(item):
    """Check if a hook item belongs to this plugin by exact script basename match."""
    if not isinstance(item, dict):
        return False
    hooks = item.get("hooks", [])
    if not isinstance(hooks, list):
        return False
    return any(_plugin_script_from_command(h.get("command", "")) for h in hooks if isinstance(h, dict))


def _get_plugin_script_name(item):
    """Identify which specific plugin script this hook uses."""
    hooks = item.get("hooks", [])
    for h in hooks:
        if not isinstance(h, dict):
            continue
        name = _plugin_script_from_command(h.get("command", ""))
        if name:
            return name
    return None


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
    if "claude-auto-review" not in settings:
        settings["claude-auto-review"] = dict(DEFAULT_SETTINGS)


def _merge_project_hooks(settings, hooks_document):
    desired_hooks = hooks_document.get("hooks")
    if desired_hooks:
        settings["hooks"] = _merge_hooks(settings.get("hooks", {}), desired_hooks)


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
    project_root = resolve_project_root(project_root)
    plugin_root = Path(get_plugin_root())
    settings_path = _settings_path(project_root)
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings = _load_settings_document(settings_path)
    hooks_document = _load_hooks_document(plugin_root)

    _ensure_plugin_settings(settings)
    _merge_project_hooks(settings, hooks_document)
    settings_path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8", newline="\n")
    return settings_path
