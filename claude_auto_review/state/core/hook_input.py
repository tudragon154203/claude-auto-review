from claude_auto_review.utils.core.shell_parsing import (
    SHELL_COPY_MOVE_COMMANDS,
    SHELL_DELETE_PS,
    SHELL_MULTI_ARG_COMMANDS,
    SHELL_PATH_COMMANDS,
    SHELL_WRITE_COMMANDS,
    SHELL_WRAPPER_COMMANDS,
    first_path_token,
    non_flag_args,
    normalize_command_token,
    option_value,
    redirection_target,
    split_shell_segments,
    wrapper_nested_command,
)


def _append_path_candidate(candidates, value):
    if isinstance(value, str) and value.strip():
        candidates.append(value)


def _extract_paths_from_shell_command(command):
    if not isinstance(command, str) or not command.strip():
        return []

    paths = []

    for tokens in split_shell_segments(command):
        if not tokens:
            continue
        command_name = normalize_command_token(tokens[0])
        if command_name in SHELL_WRAPPER_COMMANDS:
            nested = wrapper_nested_command(tokens)
            if nested:
                paths.extend(_extract_paths_from_shell_command(nested))
            continue

        if command_name in SHELL_MULTI_ARG_COMMANDS or command_name == SHELL_DELETE_PS:
            paths.extend(non_flag_args(tokens[1:]))
            continue

        if command_name in SHELL_COPY_MOVE_COMMANDS:
            args = non_flag_args(tokens[1:])
            if len(args) >= 2:
                paths.append(args[-1])
            elif args:
                paths.append(args[0])
            continue

        if command_name in SHELL_WRITE_COMMANDS:
            target = redirection_target(tokens[1:])
            if target:
                paths.append(target)
            continue

        if command_name in SHELL_PATH_COMMANDS:
            target = option_value(tokens[1:], {"-path", "-literalpath", "-destination"})
            if target is None:
                target = first_path_token(tokens[1:])
            if target:
                paths.append(target)
            continue

    return paths


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

    for key in ("command", "script"):
        command = mapping.get(key)
        if command:
            candidates.extend(_extract_paths_from_shell_command(command))

    return candidates


def _unique_strings(values):
    seen = set()
    unique = []
    for value in values:
        if value not in seen:
            seen.add(value)
            unique.append(value)
    return unique


def extract_file_paths_from_hook_input(payload):
    tool_input = payload.get("tool_input", payload) if isinstance(payload, dict) else {}
    candidates = _path_candidates_from_mapping(tool_input)
    return _unique_strings(candidates)
