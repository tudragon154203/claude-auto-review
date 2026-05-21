from pathlib import Path, PurePath

from claude_auto_review.paths.shell_parsing import (
    GIT_MOVE_SUBCOMMANDS,
    SHELL_COPY_COMMANDS,
    SHELL_DELETE_PS,
    SHELL_MOVE_COMMANDS,
    SHELL_MULTI_ARG_COMMANDS,
    SHELL_PATH_COMMANDS,
    SHELL_WRITE_COMMANDS,
    SHELL_WRAPPER_COMMANDS,
    first_path_token,
    is_flag_token,
    non_flag_args,
    normalize_command_token,
    option_value,
    redirection_target,
    split_shell_segments,
    strip_quotes,
    wrapper_nested_command,
)


def _append_path_candidate(candidates, value):
    if isinstance(value, str) and value.strip():
        candidates.append(value)


def _multi_arg_targets(tokens):
    return non_flag_args(tokens[1:])


def _looks_like_directory_destination(path, project_root):
    if path.endswith(("/", "\\")):
        return True
    if project_root is None:
        return False
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = Path(project_root) / candidate
    try:
        return candidate.is_dir()
    except OSError:
        return False


def _join_destination_file(directory, source):
    directory = directory.rstrip("/\\")
    source_name = PurePath(source).name
    if not directory or not source_name:
        return directory or source
    return f"{directory}/{source_name}"


def _move_args_to_tracked_paths(args, project_root=None):
    if len(args) < 2:
        return args[:1]

    sources = args[:-1]
    destination = args[-1]
    if len(sources) > 1 or _looks_like_directory_destination(destination, project_root):
        return sources + [_join_destination_file(destination, source) for source in sources]
    return list(args)


def _copy_targets(tokens):
    args = non_flag_args(tokens[1:])
    if len(args) >= 2:
        return [args[-1]]
    return args[:1]


def _move_targets(tokens, project_root=None):
    args = non_flag_args(tokens[1:])
    return _move_args_to_tracked_paths(args, project_root=project_root)


def _git_move_targets(tokens, project_root=None):
    first_non_flag = None
    subcommand_idx = None
    skip_next = False
    known_global_flags_with_values = {"-c", "-C", "--work-tree", "--git-dir"}
    i = 1
    while i < len(tokens):
        tok = tokens[i]
        if skip_next:
            skip_next = False
            i += 1
            continue
        if normalize_command_token(tok) in known_global_flags_with_values:
            skip_next = True
            i += 1
            continue
        if not is_flag_token(strip_quotes(tok)):
            first_non_flag = normalize_command_token(tok)
            subcommand_idx = i
            break
        i += 1
    if first_non_flag not in GIT_MOVE_SUBCOMMANDS:
        return []
    rest = tokens[subcommand_idx + 1:]
    args = non_flag_args(rest)
    return _move_args_to_tracked_paths(args, project_root=project_root)


def _write_targets(tokens):
    target = redirection_target(tokens[1:])
    return [target] if target else []


def _path_command_targets(tokens):
    target = option_value(tokens[1:], {"-path", "-literalpath", "-destination"})
    if target is None:
        target = first_path_token(tokens[1:])
    return [target] if target else []


def _handler_for_command(command_name):
    if command_name in SHELL_MULTI_ARG_COMMANDS or command_name == SHELL_DELETE_PS:
        return _multi_arg_targets
    if command_name in SHELL_MOVE_COMMANDS:
        return _move_targets
    if command_name in SHELL_COPY_COMMANDS:
        return _copy_targets
    if command_name == "git":
        return _git_move_targets
    if command_name in SHELL_WRITE_COMMANDS:
        return _write_targets
    if command_name in SHELL_PATH_COMMANDS:
        return _path_command_targets
    return None


def _extract_paths_from_shell_command(command, project_root=None):
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
                paths.extend(_extract_paths_from_shell_command(nested, project_root=project_root))
            continue

        handler = _handler_for_command(command_name)
        if handler is not None:
            if handler in (_move_targets, _git_move_targets):
                paths.extend(handler(tokens, project_root=project_root))
            else:
                paths.extend(handler(tokens))

    return paths


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
