from __future__ import annotations

from claude_auto_review.state.shell_path_extract import _extract_paths_from_shell_command


def _append_path_candidate(candidates, value):
    if isinstance(value, str) and value.strip():
        candidates.append(value)


def _path_candidates_from_mapping(mapping, project_root=None):
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

    for key in ("command", "script"):
        command = mapping.get(key)
        if command:
            candidates.extend(_extract_paths_from_shell_command(command, project_root=project_root))

    return candidates


def _unique_strings(values):
    seen = set()
    unique = []
    for value in values:
        if value not in seen:
            seen.add(value)
            unique.append(value)
    return unique


def extract_file_paths_from_hook_input(payload, project_root=None):
    tool_input = payload.get("tool_input", payload) if isinstance(payload, dict) else {}
    candidates = _path_candidates_from_mapping(tool_input, project_root=project_root)
    return _unique_strings(candidates)
