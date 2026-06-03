"""Extract file paths from shell commands for edit-tracking."""
from __future__ import annotations

from claude_auto_review.paths.shell_parsing import (
    SHELL_WRAPPER_COMMANDS,
    normalize_command_token,
    split_shell_segments,
    wrapper_nested_command,
)
from claude_auto_review.state.extraction.shell_handlers import (
    handler_for_command,
    handler_needs_project_root,
)


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

        handler = handler_for_command(command_name)
        if handler is None:
            continue

        if handler_needs_project_root(command_name):
            paths.extend(handler(tokens, project_root=project_root))
        else:
            paths.extend(handler(tokens))

    return paths
