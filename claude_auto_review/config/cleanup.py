"""Plugin settings and hook cleanup utilities."""

from __future__ import annotations

import json

from claude_auto_review.runtime.hook_identity import command_targets_plugin


def remove_plugin_settings(settings: dict) -> bool:
    if "claude-auto-review" not in settings:
        return False
    del settings["claude-auto-review"]
    return True


def remove_plugin_hooks(settings: dict) -> bool:
    """Strip every hook entry that targets the plugin from *settings*.

    Returns ``True`` when the document was modified.
    """
    hooks = settings.get("hooks", {})
    if not isinstance(hooks, dict):
        return False
    modified = False

    for hook_type in list(hooks.keys()):
        entries = hooks[hook_type]
        if not isinstance(entries, list):
            continue

        filtered = []
        entry_modified = False
        for entry in entries:
            if not isinstance(entry, dict):
                filtered.append(entry)
                continue

            nested_hooks = entry.get("hooks")
            if not isinstance(nested_hooks, list):
                command = entry.get("command", "")
                if command_targets_plugin(command):
                    modified = True
                else:
                    filtered.append(entry)
                continue

            kept_hooks = []
            hook_modified = False
            for hook in nested_hooks:
                command = hook.get("command", "") if isinstance(hook, dict) else ""
                if command_targets_plugin(command):
                    hook_modified = True
                else:
                    kept_hooks.append(hook)

            if hook_modified:
                if kept_hooks:
                    updated_entry = dict(entry)
                    updated_entry["hooks"] = kept_hooks
                    filtered.append(updated_entry)
                    entry_modified = True
                else:
                    modified = True
            else:
                filtered.append(entry)

        if filtered:
            hooks[hook_type] = filtered
            if entry_modified:
                modified = True
        else:
            del hooks[hook_type]
            modified = True

    if not hooks and "hooks" in settings:
        del settings["hooks"]
        modified = True
    return modified


def uninstall_settings_document(settings: dict) -> dict:
    """Return a copy of *settings* with plugin hooks and plugin keys removed."""
    settings = json.loads(json.dumps(settings))
    remove_plugin_hooks(settings)
    remove_plugin_settings(settings)
    return settings
