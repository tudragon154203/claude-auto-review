from __future__ import annotations

from collections.abc import Callable

from claude_auto_review.runtime.hook_context import build_hook_runtime_context
from claude_auto_review.runtime.process import run_fail_open


def run_hook(
    handler: Callable[..., int],
    *,
    raw_input: str,
    event_type: str,
    ensure_client: bool = True,
    context_factory: Callable | None = None,
) -> int:
    factory = context_factory or build_hook_runtime_context

    def _run():
        ctx = factory(raw_input, ensure_client=ensure_client)
        return handler(ctx)

    return run_fail_open(_run, event_type=event_type)
