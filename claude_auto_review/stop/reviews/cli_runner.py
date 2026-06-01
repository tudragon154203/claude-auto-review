"""Thin subprocess wrapper shared by all backend runners.

Extracted from ``prompt_runner.py`` to break the circular import between
that module and the backend-specific modules (``prompt_runner_codex``,
``prompt_runner_claude``, etc.).
"""
from __future__ import annotations

from claude_auto_review.runtime import process as _process_mod

# Module-level reference so tests can patch cli_runner.run_captured.
run_captured = _process_mod.run_captured


def run_review_cli(cli_path, args, *, cwd, timeout, input_text=None):
    """Run a reviewer CLI subprocess and return a ``CompletedProcess``."""
    return run_captured(
        [cli_path, *args],
        cwd=cwd,
        timeout=float(timeout),
        input=input_text,
    )
