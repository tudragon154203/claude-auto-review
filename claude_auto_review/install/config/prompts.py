from __future__ import annotations

import argparse

from claude_auto_review.config.settings.models import DEFAULT_REVIEWER_MODELS, PluginSettings
from claude_auto_review.config.utils.schema import (
    SETTING_MAX_STOP_PASSES,
    SETTING_MINIMUM_BLOCKING_SEVERITY,
    SETTING_REVIEWER_BACKEND,
    SETTING_REVIEWER_MODEL,
)

SEVERITY_CHOICES = ["info", "low", "medium", "high", "critical"]

_TERMINAL_WIDTH = 60


def _separator(label: str = "") -> None:
    if label:
        text = f"── {label} "
    else:
        text = "──"
    print(text + "─" * max(1, _TERMINAL_WIDTH - len(text)))


def _prompt_choice(prompt: str, options: list[str], default: str) -> str:
    labels = "/".join(options)
    while True:
        answer = input(f" ⚙  {prompt} [{labels}] ({default}): ").strip().lower()
        if not answer:
            return default
        if answer in options:
            return answer
        print(f" ⚠  Please choose one of: {', '.join(options)}")


def _prompt_text(prompt: str, default: str) -> str:
    answer = input(f" ⚙  {prompt} ({default}): ").strip()
    return answer or default


def _prompt_int(prompt: str, default: int) -> int:
    while True:
        answer = input(f" ⚙  {prompt} ({default}): ").strip()
        if not answer:
            return default
        try:
            value = int(answer)
        except ValueError:
            print(" ⚠  Please enter a whole number.")
            continue
        if value < 0:
            print(" ⚠  Please enter 0 or a positive number.")
            continue
        return value


def _validate_backend_choice(backend: str) -> None:
    from claude_auto_review.install.config.display import _check_backend_cli
    _check_backend_cli(backend)


def _apply_wizard_settings(settings: PluginSettings, *, backend: str, model: str, severity: str, max_stop_passes: int) -> PluginSettings:
    return PluginSettings.from_mapping(
        {
            **settings.to_mapping(),
            SETTING_REVIEWER_BACKEND: backend,
            SETTING_REVIEWER_MODEL: model,
            SETTING_MINIMUM_BLOCKING_SEVERITY: severity,
            SETTING_MAX_STOP_PASSES: max_stop_passes,
        }
    )


def _run_wizard(settings: PluginSettings) -> PluginSettings:
    from claude_auto_review.install.config.apply import _apply_args

    _separator("Claude Auto Review ─ setup wizard")
    from claude_auto_review.config.resolvers.reviewer import resolved_reviewer_backend, resolved_reviewer_model
    backend_default = resolved_reviewer_backend(settings)
    backend = _prompt_choice("Reviewer backend", sorted(DEFAULT_REVIEWER_MODELS), backend_default)
    _validate_backend_choice(backend)
    normalized = _apply_args(
        PluginSettings.from_mapping({**settings.to_mapping(), SETTING_REVIEWER_BACKEND: backend}),
        argparse.Namespace(backend=backend, model=None, severity=None, max_stop_passes=None, non_interactive=False),
    )
    if backend == "opencode":
        print(" ℹ  OpenCode: enter 'default' or 'none' to defer to opencode's own configured model.")
    model = _prompt_text("Reviewer model", resolved_reviewer_model(normalized, backend=backend))
    severity = _prompt_choice("Minimum blocking severity", SEVERITY_CHOICES, settings.flow.minimum_blocking_severity)
    max_stop_passes = _prompt_int("Max stop passes before circuit breaker", settings.flow.max_stop_passes)
    return _apply_wizard_settings(settings, backend=backend, model=model, severity=severity, max_stop_passes=max_stop_passes)
