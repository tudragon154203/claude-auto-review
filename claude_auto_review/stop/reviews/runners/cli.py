from __future__ import annotations

from claude_auto_review.runtime.process import run_captured


def run_review_cli(cli_path, args, *, cwd, timeout, input_text=None):
    return run_captured(
        [cli_path, *args],
        cwd=cwd,
        timeout=float(timeout),
        input=input_text,
    )