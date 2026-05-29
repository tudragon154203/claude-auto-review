from __future__ import annotations

import json
import os
from pathlib import Path

from claude_auto_review.config.io import _load_settings_document, _settings_path
from claude_auto_review.config.models import PluginSettings
from claude_auto_review.install.setup_cli import main as setup_main
from claude_auto_review.runtime.setup import ensure_runtime


def _is_initialized(project_root: Path) -> bool:
    settings_path = _settings_path(project_root)
    data = _load_settings_document(settings_path)
    plugin_settings = data.get("claude-auto-review")
    runtime_dir = project_root / ".claude" / "claude-auto-review"
    rules_path = runtime_dir / "review-rules.md"
    return (
        isinstance(plugin_settings, dict)
        and isinstance(data.get("hooks"), dict)
        and runtime_dir.exists()
        and rules_path.exists()
    )


def _ensure_initialized(project_root: Path):
    previous_cwd = Path.cwd()
    try:
        if previous_cwd != project_root:
            os.chdir(project_root)
        setup_main()
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
