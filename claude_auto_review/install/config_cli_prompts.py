from __future__ import annotations

import argparse

from claude_auto_review.config.models import DEFAULT_REVIEWER_MODELS, PluginSettings
from claude_auto_review.config.utils.schema import (
    SETTING_MAX_STOP_PASSES,
    SETTING_MINIMUM_BLOCKING_SEVERITY,
    SETTING_REVIEWER_BACKEND,
    SETTING_REVIEWER_MODEL,
)

SEVERITY_CHOICES = ["info", "low", "medium", "high", "critical"]


def _prompt_choice(prompt: str, options: list[str], default: str) -> str:
    labels = "/".join(options)
    while True:
        answer = input(f"{prompt} [{labels}] ({default}): ").strip().lower()
        if not answer:
            return default
        if answer in options:
            return answer
        print(f"Please choose one of: {', '.join(options)}")


def _prompt_text(prompt: str, default: str) -> str:
    answer = input(f"{prompt} ({default}): ").strip()
    return answer or default


def _prompt_int(prompt: str, default: int) -> int:
    while True:
        answer = input(f"{prompt} ({default}): ").strip()
        if not answer:
            return default
        try:
            value = int(answer)
        except ValueError:
            print("Please enter a whole number.")
            continue
        if value < 0:
            print("Please enter 0 or a positive number.")
            continue
        return value


def _run_wizard(settings: PluginSettings) -> PluginSettings:
    from claude_auto_review.install.config_cli_apply import _apply_args
    from claude_auto_review.install.config_cli_display import _check_backend_cli

    print("Claude Auto Review setup wizard")
    backend_default = settings.resolved_reviewer_backend()
    backend = _prompt_choice("Reviewer backend", sorted(DEFAULT_REVIEWER_MODELS), backend_default)
    _check_backend_cli(backend)
    normalized = _apply_args(
        PluginSettings.from_mapping({**settings.to_mapping(), SETTING_REVIEWER_BACKEND: backend}),
        argparse.Namespace(backend=backend, model=None, severity=None, max_stop_passes=None, non_interactive=False),
    )
    model = _prompt_text("Reviewer model", normalized.resolved_reviewer_model(backend=backend))
    severity = _prompt_choice("Minimum blocking severity", SEVERITY_CHOICES, settings.minimum_blocking_severity)
    max_stop_passes = _prompt_int("Max stop passes before circuit breaker", settings.max_stop_passes)
    return PluginSettings.from_mapping(
        {
            **settings.to_mapping(),
            SETTING_REVIEWER_BACKEND: backend,
            SETTING_REVIEWER_MODEL: model,
            SETTING_MINIMUM_BLOCKING_SEVERITY: severity,
            SETTING_MAX_STOP_PASSES: max_stop_passes,
        }
    )
