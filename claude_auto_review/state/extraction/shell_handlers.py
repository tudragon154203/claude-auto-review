"""Shell command target extraction handlers for file-tracking path discovery."""
from __future__ import annotations

from pathlib import Path, PurePath
from typing import Callable

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


def _multi_arg_targets(tokens, project_root=None):
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


def _copy_targets(tokens, project_root=None):
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


def _write_targets(tokens, project_root=None):
    target = redirection_target(tokens[1:])
    return [target] if target else []


def _path_command_targets(tokens, project_root=None):
    target = option_value(tokens[1:], {"-path", "-literalpath", "-destination"})
    if target is None:
        target = first_path_token(tokens[1:])
    return [target] if target else []


_HANDLER_TABLE: dict[str, tuple[Callable, bool]] = {}  # command → (handler, needs_project_root)


def register_handler(command_name: str, handler: Callable, *, needs_project_root: bool = False) -> None:
    """Register or replace a handler for a shell command name.

    This is the OCP extension point — new commands can be added
    without modifying the built-in registry.  Pass needs_project_root=True
    when the handler calls _looks_like_directory_destination.
    """
    _HANDLER_TABLE[command_name] = (handler, needs_project_root)


def _register_all():
    for cmd in SHELL_MULTI_ARG_COMMANDS:
        _HANDLER_TABLE[cmd] = (_multi_arg_targets, False)
    _HANDLER_TABLE[SHELL_DELETE_PS] = (_multi_arg_targets, False)
    for cmd in SHELL_MOVE_COMMANDS:
        _HANDLER_TABLE[cmd] = (_move_targets, True)
    for cmd in SHELL_COPY_COMMANDS:
        _HANDLER_TABLE[cmd] = (_copy_targets, False)
    _HANDLER_TABLE["git"] = (_git_move_targets, True)
    for cmd in SHELL_WRITE_COMMANDS:
        _HANDLER_TABLE[cmd] = (_write_targets, False)
    for cmd in SHELL_PATH_COMMANDS:
        _HANDLER_TABLE[cmd] = (_path_command_targets, False)


_register_all()


def handler_for_command(command_name):
    entry = _HANDLER_TABLE.get(command_name)
    return entry[0] if entry else None


def handler_needs_project_root(command_name) -> bool:
    """Return whether the handler for command_name requires project_root for correct resolution."""
    entry = _HANDLER_TABLE.get(command_name)
    return entry[1] if entry else False
