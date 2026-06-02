"""Plugin settings and hook cleanup utilities."""

from __future__ import annotations

import copy

from claude_auto_review.runtime.hook_identity import command_targets_plugin


def remove_plugin_settings(settings: dict) -> bool:
    if "claude-auto-review" not in settings:
        return False
    del settings["claude-auto-review"]
    return True


def _is_plugin_entry(entry: dict) -> bool:
    command = entry.get("command", "")
    return bool(command_targets_plugin(command))


def _filter_hook_entries(entries: list) -> tuple[list, bool]:
    """Return (kept_entries, was_modified)."""
    filtered: list = []
    modified = False
    for entry in entries:
        if not isinstance(entry, dict):
            filtered.append(entry)
            continue

        nested_hooks = entry.get("hooks")
        if not isinstance(nested_hooks, list):
            if _is_plugin_entry(entry):
                modified = True
            else:
                filtered.append(entry)
            continue

        kept_hooks = [h for h in nested_hooks if not (isinstance(h, dict) and _is_plugin_entry(h))]
        if len(kept_hooks) < len(nested_hooks):
            if kept_hooks:
                updated = dict(entry)
                updated["hooks"] = kept_hooks
                filtered.append(updated)
                modified = True
            else:
                modified = True
        else:
            filtered.append(entry)

    return filtered, modified



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
        filtered, entry_modified = _filter_hook_entries(entries)
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
    settings = copy.deepcopy(settings)
    remove_plugin_hooks(settings)
    remove_plugin_settings(settings)
    return settings
