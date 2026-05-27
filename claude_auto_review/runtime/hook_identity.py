from __future__ import annotations

import shlex
from pathlib import Path


PLUGIN_SCRIPTS = frozenset(["post_tool_use.py", "stop_hook.py", "session_end.py"])
PLUGIN_MODULES = {
    "claude_auto_review.hooks.post_tool_use": "post_tool_use.py",
    "claude_auto_review.hooks.stop_hook": "stop_hook.py",
    "claude_auto_review.hooks.session_end": "session_end.py",
}


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
        return PLUGIN_MODULES.get(parts[2].strip("'\""))
    basename = Path(parts[-1].strip("'\"")).name
    return basename if basename in PLUGIN_SCRIPTS else None


def command_targets_plugin(cmd):
    if plugin_script_from_command(cmd):
        return True
    if not isinstance(cmd, str):
        return False
    return any(module in cmd for module in PLUGIN_MODULES)


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
