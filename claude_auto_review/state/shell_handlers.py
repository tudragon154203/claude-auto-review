"""Shell command target extraction handlers for file-tracking path discovery."""
from __future__ import annotations

from pathlib import Path, PurePath

from claude_auto_review.paths.shell_parsing import (
    GIT_MOVE_SUBCOMMANDS,
    SHELL_COPY_COMMANDS,
    SHELL_DELETE_PS,
    SHELL_MOVE_COMMANDS,
    SHELL_MULTI_ARG_COMMANDS,
    SHELL_PATH_COMMANDS,
    SHELL_WRITE_COMMANDS,
    first_path_token,
    is_flag_token,
    non_flag_args,
    normalize_command_token,
    option_value,
    redirection_target,
    strip_quotes,
)


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
    rest = tokens[subcommand_idx + 1 :]
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
