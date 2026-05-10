import json
import shutil
from pathlib import Path

from scripts.paths import (
    CLIENTS_DIR,
    LOG_RELATIVE_PATH,
    RUNTIME_DIR,
    STATE_RELATIVE_PATH,
    client_state_path,
    get_client_id,
    get_client_runtime_dir,
    get_log_path,
    get_plugin_root,
    get_project_root,
    utc_now_iso,
)
from scripts.reviews import is_review_expired
from scripts.settings import DEFAULT_SETTINGS, load_settings


def _log_event(project_root, event_type, **kwargs):
    try:
        log_path = get_log_path(project_root)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        entry = {"timestamp": utc_now_iso(), "event": event_type, **kwargs}
        with log_path.open("a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(entry, separators=(",", ":")) + "\n")
    except OSError:
        pass


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


def cleanup_expired_pending_reviews(project_root=None, client_id=""):
    project_root = Path(project_root or get_project_root())
    if not client_id:
        client_id = get_client_id()
    settings = load_settings(project_root)
    timeout_hours = float(settings.get("pendingReviewTimeoutHours", 1))

    state_path = client_state_path(project_root, client_id)
    if not state_path.exists():
        return 0

    entries = []
    removed = 0
    for line in state_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            entries.append(line)
            continue
        if (
            isinstance(entry, dict)
            and entry.get("type") == "review"
            and entry.get("status") == "pending"
            and is_review_expired(entry, timeout_hours)
        ):
            removed += 1
            continue
        entries.append(line)

    if removed > 0:
        with state_path.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write("\n".join(entries) + "\n")
        _log_event(project_root, "expired_reviews_cleaned", count=removed)
    return removed


def _remove_path(target, removed):
    try:
        if target.is_dir():
            shutil.rmtree(target)
            removed.append(target)
        elif target.exists():
            target.unlink()
            removed.append(target)
    except OSError:
        pass


def cancel_runtime(project_root=None, client_id=""):
    project_root = Path(project_root or get_project_root())
    removed = []
    if client_id:
        client_dir = get_client_runtime_dir(project_root, client_id)
        if client_dir.exists():
            try:
                shutil.rmtree(client_dir)
                removed.append(client_dir)
            except OSError:
                pass
        return removed
    runtime = project_root / RUNTIME_DIR
    if runtime.exists():
        for target in [
            runtime / "run",
            runtime / "reviews",
            runtime / "clients",
        ]:
            _remove_path(target, removed)
        try:
            if runtime.exists() and not any(runtime.iterdir()):
                runtime.rmdir()
                removed.append(runtime)
        except OSError:
            pass
    return removed


def cancel_session(project_root=None, client_id=""):
    project_root = Path(project_root or get_project_root())
    if not client_id:
        client_id = get_client_id()
    client_dir = get_client_runtime_dir(project_root, client_id)
    if client_dir.exists():
        removed = []
        try:
            shutil.rmtree(client_dir)
            removed.append(client_dir)
        except OSError:
            pass
        return removed
    return []
