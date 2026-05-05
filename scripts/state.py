import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

STATE_RELATIVE_PATH = Path(".claude") / "claude-auto-review" / "state.jsonl"
RUNTIME_DIR = Path(".claude") / "claude-auto-review"
LOG_RELATIVE_PATH = RUNTIME_DIR / "claude-auto-review.log"
DELETED_FILE_HASH = "__deleted__"
DEFAULT_SETTINGS = {
    "enabled": True,
    "rulesFile": str(Path(".claude") / "claude-auto-review" / "rules.md"),
    "includeExtensions": [],
    "skipExtensions": [],
    "minSeverity": "MEDIUM",
    "autoFix": True,
}


def utc_now_iso():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def get_project_root():
    return Path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())).resolve()


def get_plugin_root():
    return Path(__file__).resolve().parent.parent


def normalize_relative_path(file_path, project_root=None):
    if not file_path:
        return None
    file_path = os.fspath(file_path)
    project_root = Path(project_root or get_project_root()).resolve()
    value = file_path[7:] if file_path.startswith("file://") else file_path
    candidate = Path(value)
    resolved = candidate.resolve() if candidate.is_absolute() else (project_root / candidate).resolve()
    try:
        relative = resolved.relative_to(project_root)
    except ValueError:
        return None
    if not relative.parts:
        return None
    return relative.as_posix()


def get_state_path(project_root=None):
    return Path(project_root or get_project_root()) / STATE_RELATIVE_PATH


def get_log_path(project_root=None):
    return Path(project_root or get_project_root()) / LOG_RELATIVE_PATH


def log_event(project_root, event, **fields):
    try:
        entry = {"timestamp": utc_now_iso(), "event": event, **fields}
        log_path = get_log_path(project_root)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(entry, separators=(",", ":")) + "\n")
    except OSError:
        pass


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
    include_extensions = [
        str(value).lstrip(".").lower()
        for value in settings.get("includeExtensions", [])
    ]
    skip_extensions = [
        str(value).lstrip(".").lower()
        for value in settings.get("skipExtensions", [])
    ]
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
    digest = hashlib.sha256(full_path.read_bytes()).hexdigest()
    return digest[:8]


def load_state(project_root=None):
    state_path = get_state_path(project_root)
    if not state_path.exists():
        return []
    entries = []
    for line in state_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


def append_state(entry, project_root=None):
    state_path = get_state_path(project_root)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    with state_path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(entry, separators=(",", ":")) + "\n")


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


def append_review_started(entries, review_id, review_path, project_root=None):
    append_state(
        {
            "type": "review",
            "reviewId": review_id,
            "reviewPath": str(review_path),
            "timestamp": utc_now_iso(),
            "status": "pending",
            "files": [
                {
                    "file": entry["file"],
                    "hash": entry["hash"],
                }
                for entry in entries
            ],
        },
        project_root,
    )


def pending_reviews_for_entries(state, entries):
    needed = {(entry["file"], entry["hash"]) for entry in entries}
    matches = []
    for entry in state:
        if not isinstance(entry, dict) or entry.get("type") != "review" or entry.get("status") != "pending":
            continue
        covered = {
            (item.get("file"), item.get("hash"))
            for item in entry.get("files", [])
            if isinstance(item, dict)
        }
        if needed and needed.issubset(covered):
            matches.append(entry)
    return sorted(matches, key=_timestamp_value, reverse=True)


def is_review_complete(review_path):
    path = Path(review_path)
    if not path.is_file():
        return False
    content = path.read_text(encoding="utf-8", errors="replace")
    if "## Verdict" not in content:
        return False
    verdict = content.split("## Verdict", 1)[1].strip()
    if not verdict:
        return False
    return "Pending" not in verdict


def mark_files_reviewed(entries, review_id, project_root=None):
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
    reviews_dir = base_dir / "reviews"
    run_dir = base_dir / "run"
    reviews_dir.mkdir(parents=True, exist_ok=True)
    run_dir.mkdir(parents=True, exist_ok=True)

    state_path = project_root / STATE_RELATIVE_PATH
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.touch(exist_ok=True)

    rules_path = base_dir / "rules.md"
    if not rules_path.exists():
        default_rules_path = plugin_root / "rules" / "default-rules.md"
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
        "reviews_dir": reviews_dir,
        "run_dir": run_dir,
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


def cancel_runtime(project_root=None):
    project_root = Path(project_root or get_project_root())
    targets = [
        project_root / STATE_RELATIVE_PATH,
        project_root / RUNTIME_DIR / "run",
        project_root / RUNTIME_DIR / "reviews",
    ]
    removed = []
    for target in targets:
        try:
            if target.is_dir():
                shutil.rmtree(target)
                removed.append(target)
            elif target.exists():
                target.unlink()
                removed.append(target)
        except OSError:
            continue
    return removed
