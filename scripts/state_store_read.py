import hashlib
import json
from pathlib import Path

from scripts.paths import get_project_root, normalize_relative_path


def _resolve_project_root(project_root=None):
    return Path(project_root or get_project_root())


def _timestamp_value(entry):
    return entry.get("timestamp", "")


def get_file_hash(file_path, project_root=None):
    project_root = _resolve_project_root(project_root)
    relative = normalize_relative_path(file_path, project_root)
    if not relative:
        return None
    full_path = project_root / relative
    if not full_path.is_file():
        return None
    return hashlib.sha256(full_path.read_bytes()).hexdigest()[:8]


def load_state(project_root=None, client_id=""):
    from scripts.paths import client_state_path, get_client_id

    project_root = _resolve_project_root(project_root)
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
