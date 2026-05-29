from __future__ import annotations

import shutil
from pathlib import Path

from claude_auto_review.config.utils.schema import (
    KNOWN_SETTING_KEYS,
    SETTING_MAX_STOP_PASSES,
    SETTING_MINIMUM_BLOCKING_SEVERITY,
    SETTING_REVIEWER_BACKEND,
    SETTING_REVIEWER_MODEL,
)

_BACKEND_INSTALL_HINTS = {
    "claude": "npm install -g @anthropic-ai/claude-code",
    "codex": "npm install -g @openai/codex",
}

ADVANCED_SETTING_KEYS = tuple(
    sorted(
        KNOWN_SETTING_KEYS
        - {
            SETTING_REVIEWER_BACKEND,
            SETTING_REVIEWER_MODEL,
            SETTING_MINIMUM_BLOCKING_SEVERITY,
            SETTING_MAX_STOP_PASSES,
        }
    )
)

SETTING_DESCRIPTIONS = {
    "enabled": "Enable or disable the plugin",
    "rulesFile": "Review rules markdown file path",
    "includeExtensions": "Only review matching file extensions when set",
    "skipExtensions": "Never review matching file extensions",
    "maxStopPasses": "Stop blocks before circuit breaker allows exit",
    "minimumBlockingSeverity": "Minimum severity that blocks stopping",
    "pendingReviewTimeoutHours": "Expire stale pending reviews after N hours",
    "reviewerBackend": "Reviewer CLI backend",
    "reviewerModel": "Reviewer model name for the selected backend",
    "reviewerTimeoutSeconds": "Reviewer subprocess timeout in seconds",
    "reviewFeedbackMaxChars": "Maximum characters shown in stop feedback",
    "lastAssistantMessageClassifierEnabled": "Enable last assistant message classifier",
    "lastAssistantMessageClassifierTimeoutSeconds": "Classifier timeout in seconds",
    "classifierModel": "Classifier model name",
    "staleClientTimeoutHours": "Remove stale client sessions after N hours",
    "debug": "Include extra debug context in prompts and logs",
}


def _check_backend_cli(backend: str) -> None:
    found = shutil.which(backend)
    if found:
        print(f"  [OK] {backend} CLI found: {found}")
        return
    hint = _BACKEND_INSTALL_HINTS.get(backend, f"install the {backend} CLI")
    print(f"  [WARN] {backend} CLI not found on PATH.")
    print(f"    Install with: {hint}")


def _print_advanced_settings(settings_path: Path) -> None:
    print("- Other available settings in `.claude/settings.json` under `claude-auto-review`:")
    for key in ADVANCED_SETTING_KEYS:
        print(f"  - {key}: {SETTING_DESCRIPTIONS.get(key, 'Advanced setting')}")
    print(f"- Full config location: {settings_path}")


def _print_summary(project_root: Path, initialized_before: bool, settings_path: Path, settings) -> None:
    runtime_dir = project_root / ".claude" / "claude-auto-review"
    print()
    print("Configuration saved.")
    print(f"- Setup: {'already initialized' if initialized_before else 'initialized now'}")
    print(f"- Settings file: {settings_path}")
    print(f"- Runtime directory: {runtime_dir}")
    print(
        f"- Important settings updated: reviewerBackend={settings.reviewer_backend}, "
        f"reviewerModel={settings.resolved_reviewer_model()}, "
        f"minimumBlockingSeverity={settings.minimum_blocking_severity}, "
        f"maxStopPasses={settings.max_stop_passes}"
    )
    _print_advanced_settings(settings_path)
