from __future__ import annotations

import json
import os
from collections.abc import Callable
from pathlib import Path

from claude_auto_review.config.io.settings_file import _load_settings_document, _settings_path
from claude_auto_review.config.settings.models import PluginSettings
from claude_auto_review.runtime.setup import ensure_runtime


def _has_settings_doc(project_root: Path) -> bool:
    data = _load_settings_document(_settings_path(project_root))
    return isinstance(data.get("claude-auto-review"), dict)


def _has_hooks_doc(project_root: Path) -> bool:
    data = _load_settings_document(_settings_path(project_root))
    return isinstance(data.get("hooks"), dict)


def _has_runtime_dir(project_root: Path) -> bool:
    return (project_root / ".claude" / "claude-auto-review").exists()


def _has_rules_file(project_root: Path) -> bool:
    runtime_dir = project_root / ".claude" / "claude-auto-review"
    return (runtime_dir / "review-rules.md").exists()


def _is_initialized(project_root: Path) -> bool:
    return all(
        check(project_root)
        for check in (_has_settings_doc, _has_hooks_doc, _has_runtime_dir, _has_rules_file)
    )


def _ensure_initialized(project_root: Path, *, setup_fn: Callable | None = None):
    if setup_fn is None:
        from claude_auto_review.install.cli.setup import main as setup_main
        setup_fn = setup_main

    previous_cwd = Path.cwd()
    try:
        if previous_cwd != project_root:
            os.chdir(project_root)
        setup_fn()
    finally:
        if Path.cwd() != previous_cwd:
            os.chdir(previous_cwd)
    return ensure_runtime(project_root)


def _write_plugin_settings(project_root: Path, settings: PluginSettings) -> Path:
    settings_path: Path = _settings_path(project_root)
    document = _load_settings_document(settings_path)
    document["claude-auto-review"] = settings.to_mapping()
    settings_path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    return settings_path
