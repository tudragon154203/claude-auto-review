"""Plugin hook identity registry.

Default entries cover the bundled hooks (`post_tool_use`, `stop_hook`,
`session_end`). Third-party integrations can call `register_plugin_hook()`
at import time to extend the registry without modifying this module.
"""

from __future__ import annotations

import shlex
from pathlib import Path

_PLUGIN_SCRIPTS: set[str] = {"post_tool_use.py", "stop_hook.py", "session_end.py"}
_PLUGIN_MODULES: dict[str, str] = {
    "claude_auto_review.hooks.post_tool_use": "post_tool_use.py",
    "claude_auto_review.hooks.stop_hook": "stop_hook.py",
    "claude_auto_review.hooks.session_end": "session_end.py",
}

PLUGIN_SCRIPTS = frozenset(_PLUGIN_SCRIPTS)
PLUGIN_MODULES = dict(_PLUGIN_MODULES)


def register_plugin_hook(module_name: str, script_name: str) -> None:
    """Register a plugin hook for OCP-friendly extension.

    Adds both the script filename and the dotted module name to the
    registries consulted by ``plugin_script_from_command`` and
    ``command_targets_plugin``.
    """
    _PLUGIN_SCRIPTS.add(script_name)
    _PLUGIN_MODULES[module_name] = script_name
    # Refresh exported snapshots so callers that import the frozenset
    # at import time still see the new entry on the next import.
    global PLUGIN_SCRIPTS, PLUGIN_MODULES
    PLUGIN_SCRIPTS = frozenset(_PLUGIN_SCRIPTS)
    PLUGIN_MODULES = dict(_PLUGIN_MODULES)


def plugin_script_from_command(cmd):
    if not cmd:
        return None
    try:
        parts = shlex.split(cmd, posix=False)
    except ValueError:
        parts = cmd.split()
    if not parts:
        return None
    if len(parts) >= 3 and parts[1] == "-m":
        return _PLUGIN_MODULES.get(parts[2].strip("'\""))
    basename = Path(parts[-1].strip("'\"")).name
    return basename if basename in _PLUGIN_SCRIPTS else None


def command_targets_plugin(cmd):
    if plugin_script_from_command(cmd):
        return True
    if not isinstance(cmd, str):
        return False
    return any(module in cmd for module in _PLUGIN_MODULES)


def is_plugin_hook(item):
    if not isinstance(item, dict):
        return False
    hooks = item.get("hooks", [])
    if not isinstance(hooks, list):
        return False
    return any(command_targets_plugin(h.get("command", "")) for h in hooks if isinstance(h, dict))


def plugin_script_name_from_hook(item):
    hooks = item.get("hooks", []) if isinstance(item, dict) else []
    for hook in hooks:
        if not isinstance(hook, dict):
            continue
        name = plugin_script_from_command(hook.get("command", ""))
        if name:
            return name
    return None
