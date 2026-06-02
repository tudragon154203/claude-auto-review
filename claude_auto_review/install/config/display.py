from __future__ import annotations

import shutil
from pathlib import Path

from claude_auto_review.config.resolvers.reviewer import resolved_reviewer_model
from claude_auto_review.config.settings.models import PluginSettings
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
    "opencode": "npm install -g opencode-ai",
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
    "reviewerModel": "Reviewer model name for the selected backend (use 'default' to let opencode pick its configured model)",
    "reviewerTimeoutSeconds": "Reviewer subprocess timeout in seconds",
    "reviewFeedbackMaxChars": "Maximum characters shown in stop feedback",
    "lastAssistantMessageClassifierEnabled": "Enable last assistant message classifier",
    "lastAssistantMessageClassifierTimeoutSeconds": "Classifier timeout in seconds",
    "classifierModel": "Classifier model name",
    "staleClientTimeoutHours": "Remove stale client sessions after N hours",
    "debug": "Include extra debug context in prompts and logs",
}


def _resolved_descriptions(extra_descriptions: dict[str, str] | None = None) -> dict[str, str]:
    if extra_descriptions:
        return {**SETTING_DESCRIPTIONS, **extra_descriptions}
    return SETTING_DESCRIPTIONS


def _check_backend_cli(backend: str) -> None:
    found = shutil.which(backend)
    if found:
        print(f"   ✓ {backend} CLI found: {found}")
        return
    hint = _BACKEND_INSTALL_HINTS.get(backend, f"install the {backend} CLI")
    print(f"   ⚠ {backend} CLI not found on PATH.")
    print(f"     Install with: {hint}")


def _print_advanced_settings(
    settings_path: Path,
    settings: PluginSettings,
    *,
    extra_descriptions: dict[str, str] | None = None,
) -> None:
    descriptions = _resolved_descriptions(extra_descriptions)
    mapping = settings.to_mapping()
    print(" ── Other settings " + "─" * 41)
    for key in ADVANCED_SETTING_KEYS:
        value = mapping.get(key, "")
        print(f"   {key}: {descriptions.get(key, 'Advanced setting')} (current: {value!r})")
    print(f" 📄 Full config location: {settings_path}")


def _print_summary(
    project_root: Path,
    initialized_before: bool,
    settings_path: Path,
    settings: PluginSettings,
    *,
    extra_descriptions: dict[str, str] | None = None,
) -> None:
    runtime_dir = project_root / ".claude" / "claude-auto-review"
    print()
    print("── Configuration saved " + "─" * 37)
    print(f" ✓ Setup: {'already initialized' if initialized_before else 'initialized now'}")
    print(f" 📄 Settings file: {settings_path}")
    print(f" 📁 Runtime directory: {runtime_dir}")
    print(
        f" ⚙  reviewerBackend={settings.reviewer_backend}, "
        f"reviewerModel={resolved_reviewer_model(settings)}, "
        f"minimumBlockingSeverity={settings.minimum_blocking_severity}, "
        f"maxStopPasses={settings.max_stop_passes}"
    )
    _print_advanced_settings(settings_path, settings, extra_descriptions=extra_descriptions)
