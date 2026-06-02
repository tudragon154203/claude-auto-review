#!/usr/bin/env python3
from __future__ import annotations

import sys
from collections.abc import Callable

from claude_auto_review.hooks.common import run_hook
from claude_auto_review.stop.orchestration.flow import run_stop_flow


def _run_stop_hook(ctx, *, flow_runner: Callable = run_stop_flow):
    return flow_runner(ctx)


def main(*, flow_runner: Callable | None = None):
    runner = flow_runner or run_stop_flow
    return run_hook(
        lambda ctx: _run_stop_hook(ctx, flow_runner=runner),
        raw_input=sys.stdin.read(),
        event_type="stop_error",
    )


if __name__ == "__main__":
    raise SystemExit(main())
