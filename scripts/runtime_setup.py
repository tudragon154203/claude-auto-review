import json
import shutil
from pathlib import Path

from scripts.paths import (
    LOG_RELATIVE_PATH,
    RUNTIME_DIR,
    STATE_RELATIVE_PATH,
    get_client_runtime_dir,
    get_plugin_root,
    get_project_root,
)
from scripts.settings import DEFAULT_SETTINGS


def ensure_client_runtime(project_root, client_id):
    client_dir = get_client_runtime_dir(project_root, client_id)
    client_dir.mkdir(parents=True, exist_ok=True)
    (client_dir / "state.jsonl").touch(exist_ok=True)
    (client_dir / "reviews").mkdir(exist_ok=True)
    (client_dir / "run").mkdir(exist_ok=True)
    return client_dir


def ensure_runtime(project_root=None, plugin_root=None):
    project_root = Path(project_root or get_project_root())
    plugin_root = Path(plugin_root or get_plugin_root())
    base_dir = project_root / RUNTIME_DIR
    base_dir.mkdir(parents=True, exist_ok=True)
    state_path = project_root / STATE_RELATIVE_PATH
    state_path.parent.mkdir(parents=True, exist_ok=True)

    rules_path = base_dir / "rules.md"
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
    settings_path = project_root / ".claude" / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        settings = json.loads(settings_path.read_text(encoding="utf-8")) if settings_path.exists() else {}
        if not isinstance(settings, dict):
            settings = {}
    except (OSError, json.JSONDecodeError):
        settings = {}

    if "claude-auto-review" not in settings:
        settings["claude-auto-review"] = dict(DEFAULT_SETTINGS)
        settings_path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8", newline="\n")
    return settings_path
