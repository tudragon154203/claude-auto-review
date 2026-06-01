"""Registry for shell command path-extraction handlers."""
from __future__ import annotations

from collections.abc import Callable

from claude_auto_review.paths.shell_parsing import (
    SHELL_COPY_COMMANDS,
    SHELL_DELETE_PS,
    SHELL_MOVE_COMMANDS,
    SHELL_MULTI_ARG_COMMANDS,
    SHELL_PATH_COMMANDS,
    SHELL_WRITE_COMMANDS,
)
from claude_auto_review.state.shell_targets import (
    copy_targets,
    git_move_targets,
    move_targets,
    multi_arg_targets,
    path_command_targets,
    write_targets,
)


_HANDLER_TABLE: dict[str, Callable] = {}
_TRACKED_COMMANDS: set[str] = set()


def register_handler(command_name: str, handler: Callable) -> None:
    _HANDLER_TABLE[command_name] = handler
    _TRACKED_COMMANDS.add(command_name)


def _register_all() -> None:
    for cmd in SHELL_MULTI_ARG_COMMANDS:
        register_handler(cmd, multi_arg_targets)
    register_handler(SHELL_DELETE_PS, multi_arg_targets)
    for cmd in SHELL_MOVE_COMMANDS:
        register_handler(cmd, move_targets)
    for cmd in SHELL_COPY_COMMANDS:
        register_handler(cmd, copy_targets)
    register_handler("git", git_move_targets)
    for cmd in SHELL_WRITE_COMMANDS:
        register_handler(cmd, write_targets)
    for cmd in SHELL_PATH_COMMANDS:
        register_handler(cmd, path_command_targets)


_register_all()


def handler_for_command(command_name):
    return _HANDLER_TABLE.get(command_name)


def is_tracked_command(command_name: str) -> bool:
    return command_name in _TRACKED_COMMANDS

