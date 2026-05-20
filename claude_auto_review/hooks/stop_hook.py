#!/usr/bin/env python3
import sys

from claude_auto_review.runtime.hook_context import build_hook_runtime_context
from claude_auto_review.runtime.process import run_fail_open
from claude_auto_review.stop.orchestration.flow import run_stop_flow


def _run_stop_hook():
    ctx = build_hook_runtime_context(sys.stdin.read())
    return run_stop_flow(ctx.project_root, ctx.payload, client_id=ctx.client_id, settings=ctx.settings)


def main():
    return run_fail_open(_run_stop_hook, event_type="stop_error")


if __name__ == "__main__":
    raise SystemExit(main())
