import hashlib
import json
from pathlib import Path

from scripts.paths import (
    DELETED_FILE_HASH,
    client_reviews_dir,
    client_run_dir,
    client_state_path,
    get_client_runtime_dir,
    get_client_id,
    get_log_path,
    get_plugin_root,
    get_project_root,
    get_state_path,
    normalize_relative_path,
    utc_now_iso,
)
from scripts.reviews import is_review_complete, pending_reviews_for_entries
import scripts.runtime as runtime
from scripts.settings import DEFAULT_SETTINGS, load_settings, should_skip_file


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
    runtime.ensure_client_runtime(project_root, client_id)
    state_file = client_state_path(project_root, client_id)
    with state_file.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(entry) + "\n")


def ensure_client_runtime(project_root, client_id):
    return runtime.ensure_client_runtime(project_root, client_id)


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
    return runtime.ensure_runtime(project_root, plugin_root)


def ensure_project_settings(project_root=None):
    return runtime.ensure_project_settings(project_root)


def cleanup_expired_pending_reviews(project_root=None, client_id=""):
    return runtime.cleanup_expired_pending_reviews(project_root, client_id)


def cancel_runtime(project_root=None, client_id=""):
    return runtime.cancel_runtime(project_root, client_id)


def cancel_session(project_root=None, client_id=""):
    return runtime.cancel_session(project_root, client_id)
