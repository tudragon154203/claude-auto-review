import hashlib
import json
from pathlib import Path

from claude_auto_review.paths import is_runtime_relative_path, normalize_relative_path
from claude_auto_review.runtime.helpers import resolve_client_id, resolve_project_root


def _timestamp_value(entry):
    return entry.get("timestamp", "")


def _is_edit_entry(entry):
    return isinstance(entry, dict) and entry.get("type") == "edit" and entry.get("file") and entry.get("hash")


def _edit_entry_key(entry):
    if not _is_edit_entry(entry):
        return None
    return entry["file"], entry["hash"]


def _append_path_candidate(candidates, value):
    if isinstance(value, str) and value.strip():
        candidates.append(value)


def _path_candidates_from_mapping(mapping):
    candidates = []
    if not isinstance(mapping, dict):
        return candidates

    for key in ("file_path", "path", "filePath"):
        _append_path_candidate(candidates, mapping.get(key))

    edits = mapping.get("edits")
    if isinstance(edits, list):
        for edit in edits:
            if isinstance(edit, dict):
                for key in ("file_path", "path", "filePath"):
                    _append_path_candidate(candidates, edit.get(key))
    return candidates


def _unique_strings(values):
    seen = set()
    unique = []
    for value in values:
        if value not in seen:
            seen.add(value)
            unique.append(value)
    return unique


def read_jsonl_records(path):
    path = Path(path)
    if not path.exists():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            entry = None
        records.append((line, entry))
    return records


def get_file_hash(file_path, project_root=None):
    project_root = resolve_project_root(project_root)
    relative = normalize_relative_path(file_path, project_root)
    if not relative:
        return None
    full_path = project_root / relative
    if not full_path.is_file():
        return None
    return hashlib.sha256(full_path.read_bytes()).hexdigest()[:8]


def load_state(project_root=None, client_id=""):
    from claude_auto_review.paths import client_state_path

    project_root = resolve_project_root(project_root)
    client_id = resolve_client_id(client_id)
    state_file = client_state_path(project_root, client_id)
    return [entry for _, entry in read_jsonl_records(state_file) if entry is not None]


def latest_entries_by_file(state):
    latest = {}
    for entry in state:
        key = _edit_entry_key(entry)
        if key is None:
            continue
        file_path, _ = key
        current = latest.get(file_path)
        if current is None or _timestamp_value(entry) >= _timestamp_value(current):
            latest[file_path] = entry
    return latest


def reviewed_hashes_by_file(state):
    reviewed = {}
    for entry in state:
        key = _edit_entry_key(entry)
        if key is None or not entry.get("reviewed"):
            continue
        file_path, file_hash = key
        reviewed.setdefault(file_path, set()).add(file_hash)
    return reviewed


def was_hash_reviewed(state, file_path, file_hash):
    return file_hash in reviewed_hashes_by_file(state).get(file_path, set())


def get_unreviewed_files(state):
    return [
        entry
        for entry in latest_entries_by_file(state).values()
        if not entry.get("reviewed") and not entry.get("deleted") and not is_runtime_relative_path(entry.get("file"))
    ]


def consecutive_stop_blocks(state):
    last_reviewed_idx = -1
    for idx, entry in enumerate(state):
        if _is_edit_entry(entry) and entry.get("reviewed", False):
            last_reviewed_idx = idx

    count = 0
    for entry in state[last_reviewed_idx + 1 :]:
        if isinstance(entry, dict) and entry.get("type") == "stop_blocked":
            count += 1
    return count


def extract_file_paths_from_hook_input(payload):
    tool_input = payload.get("tool_input", payload) if isinstance(payload, dict) else {}
    candidates = _path_candidates_from_mapping(tool_input)
    return _unique_strings(candidates)
