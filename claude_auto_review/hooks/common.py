from __future__ import annotations

from claude_auto_review.runtime.hook_context import build_hook_runtime_context
from claude_auto_review.runtime.process import run_fail_open


def run_hook(handler, *, raw_input: str, event_type: str, ensure_client: bool = True):
    def _run():
        ctx = build_hook_runtime_context(raw_input, ensure_client=ensure_client)
        return handler(ctx)

    return run_fail_open(_run, event_type=event_type)
