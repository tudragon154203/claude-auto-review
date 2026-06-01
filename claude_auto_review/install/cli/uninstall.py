#!/usr/bin/env python3
"""Uninstall claude-auto-review from project.

Removes runtime data, cleans up .claude/settings.json and .gitignore.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

if __name__ == "__main__":
    _plugin_root = Path(__file__).resolve().parents[3]
    if str(_plugin_root) not in sys.path:
        sys.path.insert(0, str(_plugin_root))

from claude_auto_review.config.io.cleanup import remove_plugin_hooks as _remove_plugin_hooks  # noqa: F811, E501
from claude_auto_review.config.io.cleanup import remove_plugin_settings as _remove_plugin_settings  # noqa: F811, E501
from claude_auto_review.config.io.settings_file import _load_settings_document, _settings_path
from claude_auto_review.install.installer import ensure_gitignore_entries
from claude_auto_review.paths.path_utils import get_project_root
from claude_auto_review.runtime.events import log_event

GITIGNORE_ENTRY = ".claude/claude-auto-review/"


def main():
    project_root = get_project_root()
    runtime_dir = project_root / ".claude" / "claude-auto-review"
    removed = []

    if runtime_dir.exists():
        removed.append(str(runtime_dir.relative_to(project_root)))

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
            ],
        )

    settings_path = _settings_path(project_root)
    if settings_path.exists():
        try:
            settings = _load_settings_document(settings_path)
        except (OSError, json.JSONDecodeError):
            settings = {}
        hooks_modified = _remove_plugin_hooks(settings)
        settings_modified = _remove_plugin_settings(settings)
        if hooks_modified or settings_modified:
            settings_path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")

    log_event(project_root, "uninstall_completed", removed=removed)
    shutil.rmtree(runtime_dir, ignore_errors=True)
    if removed:
        print("Claude Auto Review uninstalled. Removed:")
        for path in removed:
            print(f"  - {path}")
    else:
        print("Claude Auto Review was not installed. Nothing to remove.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
