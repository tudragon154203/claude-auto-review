#!/usr/bin/env python3
from __future__ import annotations

# ── stdlib ────────────────────────────────────────────────────────────────────
import argparse
import json
import os
import shutil
import sys
from pathlib import Path

if __name__ == "__main__":
    _plugin_root = Path(__file__).resolve().parents[2]
    if str(_plugin_root) not in sys.path:
        sys.path.insert(0, str(_plugin_root))

# ── project imports ───────────────────────────────────────────────────────────
from claude_auto_review.config.io import _load_settings_document, _settings_path, load_settings
from claude_auto_review.config.models import DEFAULT_REVIEWER_MODELS, PluginSettings
from claude_auto_review.config.utils.schema import (
    KNOWN_SETTING_KEYS,
    SETTING_MAX_STOP_PASSES,
    SETTING_MINIMUM_BLOCKING_SEVERITY,
    SETTING_REVIEWER_BACKEND,
    SETTING_REVIEWER_MODEL,
)
from claude_auto_review.install.setup_cli import main as setup_main
from claude_auto_review.paths.path_utils import get_project_root
from claude_auto_review.runtime.events import log_event
from claude_auto_review.runtime.setup import ensure_runtime

# ── constants ─────────────────────────────────────────────────────────────────

SEVERITY_CHOICES = ["info", "low", "medium", "high", "critical"]

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

# ── argument parser ───────────────────────────────────────────────────────────


def _build_parser():
    parser = argparse.ArgumentParser(
        prog="claude-auto-review config",
        description="Guide project setup and update Claude Auto Review settings.",
    )
    parser.add_argument("--backend", choices=sorted(DEFAULT_REVIEWER_MODELS), help="Set reviewer backend")
    parser.add_argument("--model", help="Set reviewer model")
    parser.add_argument("--severity", choices=SEVERITY_CHOICES, help="Set minimum blocking severity")
    parser.add_argument("--max-stop-passes", type=int, help="Set maxStopPasses")
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Apply only provided flags and skip the interactive wizard",
    )
    return parser

# ── initialization checks ─────────────────────────────────────────────────────


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

# ── interactive prompts ───────────────────────────────────────────────────────


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

# ── settings manipulation ─────────────────────────────────────────────────────


def _normalize_max_stop_passes(value: int) -> int:
    if value < 0:
        raise ValueError("maxStopPasses must be 0 or greater")
    return value


def _apply_args(settings: PluginSettings, args) -> PluginSettings:
    updated = settings.to_mapping()
    if args.backend:
        previous_backend = settings.resolved_reviewer_backend()
        known_default_models = set(DEFAULT_REVIEWER_MODELS.values())
        previous_default_model = DEFAULT_REVIEWER_MODELS[previous_backend]
        updated[SETTING_REVIEWER_BACKEND] = args.backend
        if not args.model and (
            settings.reviewer_model is None
            or settings.reviewer_model == previous_default_model
            or settings.reviewer_model in known_default_models
        ):
            updated[SETTING_REVIEWER_MODEL] = DEFAULT_REVIEWER_MODELS[args.backend]
    if args.model:
        updated[SETTING_REVIEWER_MODEL] = args.model
    if args.severity:
        updated[SETTING_MINIMUM_BLOCKING_SEVERITY] = args.severity
    if args.max_stop_passes is not None:
        updated[SETTING_MAX_STOP_PASSES] = _normalize_max_stop_passes(args.max_stop_passes)
    return PluginSettings.from_mapping(updated)


def _run_wizard(settings: PluginSettings) -> PluginSettings:
    print("Claude Auto Review setup wizard")
    backend_default = settings.resolved_reviewer_backend()
    backend = _prompt_choice("Reviewer backend", sorted(DEFAULT_REVIEWER_MODELS), backend_default)
    _check_backend_cli(backend)
    # Normalise model default for the chosen backend before prompting
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

# ── settings file I/O ─────────────────────────────────────────────────────────


def _write_plugin_settings(project_root: Path, settings: PluginSettings) -> Path:
    settings_path = _settings_path(project_root)
    document = _load_settings_document(settings_path)
    document["claude-auto-review"] = settings.to_mapping()
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8", newline="\n")
    return settings_path

# ── output / printing ─────────────────────────────────────────────────────────


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


def _print_summary(project_root: Path, initialized_before: bool, settings_path: Path, settings: PluginSettings) -> None:
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

# ── entry point ───────────────────────────────────────────────────────────────


def main(argv=None):
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
        if args.max_stop_passes is not None:
            _normalize_max_stop_passes(args.max_stop_passes)
    except ValueError as error:
        parser.error(str(error))

    project_root = get_project_root()
    initialized_before = _is_initialized(project_root)
    if not initialized_before:
        _ensure_initialized(project_root)

    current_settings = load_settings(project_root)
    updated_settings = _apply_args(current_settings, args)
    if args.non_interactive and args.backend:
        _check_backend_cli(args.backend)
    if not args.non_interactive:
        updated_settings = _run_wizard(updated_settings)

    settings_path = _write_plugin_settings(project_root, updated_settings)
    log_event(project_root, "config_updated", initialized=not initialized_before)
    _print_summary(project_root, initialized_before, settings_path, updated_settings)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
