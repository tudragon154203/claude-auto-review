#!/usr/bin/env python3
"""Uninstall claude-auto-review from project.

Removes runtime data, cleans up .claude/settings.json and .gitignore.
"""
import json
import sys
import shutil
from pathlib import Path

if __name__ == "__main__":
    _plugin_root = Path(__file__).resolve().parents[2]
    if str(_plugin_root) not in sys.path:
        sys.path.insert(0, str(_plugin_root))

from claude_auto_review.paths.path_utils import get_project_root
from claude_auto_review.runtime.events import log_event
from claude_auto_review.install.installer import ensure_gitignore_entries
from claude_auto_review.runtime.setup import _plugin_script_from_command

PLUGIN_HOOK_PATTERNS = [
    "claude_auto_review.hooks.post_tool_use",
    "claude_auto_review.hooks.stop_hook",
    "claude_auto_review.hooks.session_end",
]
GITIGNORE_ENTRY = ".claude/claude-auto-review/"


def _remove_plugin_hooks(settings):
    """Remove plugin hooks from settings dict. Returns True if modified."""
    hooks = settings.get("hooks", {})
    if not isinstance(hooks, dict):
        return False
    modified = False

    for hook_type in list(hooks.keys()):
        entries = hooks[hook_type]
        if not isinstance(entries, list):
            continue

        filtered = []
        for entry in entries:
            if not isinstance(entry, dict):
                filtered.append(entry)
                continue

            nested_hooks = entry.get("hooks", [])
            if not isinstance(nested_hooks, list):
                filtered.append(entry)
                continue

            kept_hooks = []
            entry_modified = False
            for hook in nested_hooks:
                command = hook.get("command", "") if isinstance(hook, dict) else ""
                if _plugin_script_from_command(command):
                    entry_modified = True
                    continue
                if any(pattern in command for pattern in PLUGIN_HOOK_PATTERNS):
                    entry_modified = True
                    continue
                kept_hooks.append(hook)

            if kept_hooks:
                if entry_modified:
                    updated_entry = dict(entry)
                    updated_entry["hooks"] = kept_hooks
                    filtered.append(updated_entry)
                    modified = True
                else:
                    filtered.append(entry)
            else:
                modified = True

        if not filtered:
            del hooks[hook_type]
        else:
            hooks[hook_type] = filtered

    if not hooks and "hooks" in settings:
        del settings["hooks"]
        modified = True

    if "claude-auto-review" in settings:
        del settings["claude-auto-review"]
        modified = True

    return modified


def main():
    project_root = Path(get_project_root())
    removed = []

    runtime_dir = project_root / ".claude" / "claude-auto-review"
    if runtime_dir.exists():
        removed.append(str(runtime_dir.relative_to(project_root)))

    # Clean up .gitignore
    gitignore_path = project_root / ".gitignore"
    if gitignore_path.exists():
        ensure_gitignore_entries(
            gitignore_path,
            ignore_entries=[],
            remove_entries=[
                GITIGNORE_ENTRY,
                ".claude/claude-auto-review/state.jsonl",
                ".claude/claude-auto-review/clients/*/run/",
                ".claude/claude-auto-review/clients/*/reviews/",
                ".claude/claude-auto-review/scripts/",
                ".claude/claude-auto-review/agents/",
                ".claude/claude-auto-review/claude-auto-review.log",
            ],
        )

    # Remove plugin hooks from settings.json
    settings_path = project_root / ".claude" / "settings.json"
    if settings_path.exists():
        try:
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            settings = {}
        if _remove_plugin_hooks(settings):
            settings_path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")

    log_event(project_root, "uninstall_completed", removed=removed)
    shutil.rmtree(runtime_dir, ignore_errors=True)
    if removed:
        print("Claude Auto Review uninstalled. Removed:")
        for path in removed:
            print(f"- {path}")
    else:
        print("Claude Auto Review: nothing to uninstall (not configured).")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
