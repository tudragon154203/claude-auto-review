import hashlib
import json
import shutil
from pathlib import Path

from scripts.paths import (
    CLIENTS_DIR,
    DELETED_FILE_HASH,
    LOG_RELATIVE_PATH,
    RUNTIME_DIR,
    STATE_RELATIVE_PATH,
    client_reviews_dir,
    client_run_dir,
    client_state_path,
    get_client_id,
    get_client_runtime_dir,
    get_log_path,
    get_plugin_root,
    get_project_root,
    get_state_path,
    normalize_relative_path,
    utc_now_iso,
)
from scripts.reviews import is_review_complete, is_review_expired, pending_reviews_for_entries

DEFAULT_SETTINGS = {
    "enabled": True,
    "rulesFile": str(Path(".claude") / "claude-auto-review" / "rules.md"),
    "includeExtensions": [],
    "skipExtensions": [],
    "minSeverity": "MEDIUM",
    "autoFix": True,
    "maxStopPasses": 3,
    "pendingReviewTimeoutHours": 1,
}


def load_settings(project_root=None):
    project_root = Path(project_root or get_project_root())
    settings_path = project_root / ".claude" / "settings.json"
    try:
        data = json.loads(settings_path.read_text(encoding="utf-8")) if settings_path.exists() else {}
        plugin_settings = data.get("claude-auto-review", {}) if isinstance(data, dict) else {}
        return {**DEFAULT_SETTINGS, **plugin_settings}
    except (OSError, json.JSONDecodeError):
        return dict(DEFAULT_SETTINGS)


def should_skip_file(file_path, settings=None):
    settings = settings or DEFAULT_SETTINGS
    ext = Path(file_path).suffix.lstrip(".").lower()
    include_extensions = [str(value).lstrip(".").lower() for value in settings.get("includeExtensions", [])]
    skip_extensions = [str(value).lstrip(".").lower() for value in settings.get("skipExtensions", [])]
    if include_extensions and ext not in include_extensions:
        return True
    return bool(ext and ext in skip_extensions)


def get_file_hash(file_path, project_root=None):
    project_root = Path(project_root or get_project_root())
    relative = normalize_relative_path(file_path, project_root)
    if not relative:
        return None
    full_path = project_root / relative
    if not full_path.is_file():
        return None
    return hashlib.sha256(full_path.read_bytes()).hexdigest()[:8]


def log_event(project_root, event_type, **kwargs):
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


def load_state(project_root=None, client_id=""):
    project_root = Path(project_root or get_project_root())
    if not client_id:
        client_id = get_client_id()
    state_file = client_state_path(project_root, client_id)
    if not state_file.exists():
        return []
    entries = []
    for line in state_file.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return entries


def append_state(entry, project_root=None, client_id=""):
    project_root = Path(project_root or get_project_root())
    if not client_id:
        client_id = get_client_id()
    ensure_client_runtime(project_root, client_id)
    state_file = client_state_path(project_root, client_id)
    with state_file.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(entry) + "\n")


def _timestamp_value(entry):
    return entry.get("timestamp", "")


def latest_entries_by_file(state):
    latest = {}
    for entry in state:
        if not isinstance(entry, dict):
            continue
        if entry.get("type") != "edit" or not entry.get("file") or not entry.get("hash"):
            continue
        current = latest.get(entry["file"])
        if current is None or _timestamp_value(entry) >= _timestamp_value(current):
            latest[entry["file"]] = entry
    return latest


def reviewed_hashes_by_file(state):
    reviewed = {}
    for entry in state:
        if (
            isinstance(entry, dict)
            and entry.get("type") == "edit"
            and entry.get("file")
            and entry.get("hash")
            and entry.get("reviewed")
        ):
            reviewed.setdefault(entry["file"], set()).add(entry["hash"])
    return reviewed


def was_hash_reviewed(state, file_path, file_hash):
    return file_hash in reviewed_hashes_by_file(state).get(file_path, set())


def get_unreviewed_files(state):
    return [entry for entry in latest_entries_by_file(state).values() if not entry.get("reviewed")]


def append_review_started(entries, review_id, review_path, project_root=None, client_id=""):
    if not client_id:
        client_id = get_client_id()
    append_state(
        {
            "type": "review",
            "reviewId": review_id,
            "reviewPath": str(review_path),
            "timestamp": utc_now_iso(),
            "status": "pending",
            "files": [{"file": entry["file"], "hash": entry["hash"]} for entry in entries],
            "clientId": client_id,
        },
        project_root,
        client_id=client_id,
    )


def consecutive_stop_blocks(state):
    last_reviewed_idx = -1
    for idx, entry in enumerate(state):
        if not isinstance(entry, dict):
            continue
        if entry.get("type") == "edit" and entry.get("reviewed", False):
            last_reviewed_idx = idx

    count = 0
    for entry in state[last_reviewed_idx + 1 :]:
        if isinstance(entry, dict) and entry.get("type") == "stop_blocked":
            count += 1
    return count


def mark_files_reviewed(entries, review_id, project_root=None, client_id=""):
    if not client_id:
        client_id = get_client_id()
    timestamp = utc_now_iso()
    for entry in entries:
        append_state(
            {
                "type": "edit",
                "file": entry["file"],
                "hash": entry["hash"],
                "timestamp": timestamp,
                "reviewed": True,
                "reviewId": review_id,
            },
            project_root,
            client_id=client_id,
        )


def extract_file_paths_from_hook_input(payload):
    candidates = []
    tool_input = payload.get("tool_input", payload) if isinstance(payload, dict) else {}

    def add(value):
        if isinstance(value, str) and value.strip():
            candidates.append(value)

    if isinstance(tool_input, dict):
        add(tool_input.get("file_path"))
        add(tool_input.get("path"))
        add(tool_input.get("filePath"))
        edits = tool_input.get("edits")
        if isinstance(edits, list):
            for edit in edits:
                if isinstance(edit, dict):
                    add(edit.get("file_path"))
                    add(edit.get("path"))
                    add(edit.get("filePath"))

    seen = set()
    unique = []
    for candidate in candidates:
        if candidate not in seen:
            seen.add(candidate)
            unique.append(candidate)
    return unique


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
        log_event(project_root, "expired_reviews_cleaned", count=removed)
    return removed


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
            try:
                if target.is_dir():
                    shutil.rmtree(target)
                    removed.append(target)
                elif target.exists():
                    target.unlink()
                    removed.append(target)
            except OSError:
                pass
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
