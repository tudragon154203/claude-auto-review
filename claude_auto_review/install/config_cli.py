#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __name__ == "__main__":
    _plugin_root = Path(__file__).resolve().parents[2]
    if str(_plugin_root) not in sys.path:
        sys.path.insert(0, str(_plugin_root))

from claude_auto_review.config.io import load_settings
from claude_auto_review.config.models import DEFAULT_REVIEWER_MODELS, PluginSettings  # noqa: F401
from claude_auto_review.install.config_cli_io import _ensure_initialized, _is_initialized, _write_plugin_settings
from claude_auto_review.install.config_cli_apply import _apply_args, _normalize_max_stop_passes
from claude_auto_review.install.config_cli_prompts import SEVERITY_CHOICES, _prompt_choice, _prompt_int, _prompt_text, _run_wizard  # noqa: F401
from claude_auto_review.install.config_cli_display import (
    _BACKEND_INSTALL_HINTS,  # noqa: F401
    ADVANCED_SETTING_KEYS,  # noqa: F401
    SETTING_DESCRIPTIONS,  # noqa: F401
    _check_backend_cli,
    _print_advanced_settings,  # noqa: F401
    _print_summary,
)
from claude_auto_review.paths.path_utils import get_project_root
from claude_auto_review.runtime.events import log_event


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
