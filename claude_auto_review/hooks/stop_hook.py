#!/usr/bin/env python3
import sys

from claude_auto_review.hooks.common import run_hook
from claude_auto_review.stop.orchestration.flow import run_stop_flow


def _run_stop_hook(ctx):
    return run_stop_flow(ctx.project_root, ctx.payload, client_id=ctx.client_id, settings=ctx.settings)


def main():
    return run_hook(_run_stop_hook, raw_input=sys.stdin.read(), event_type="stop_error")


if __name__ == "__main__":
    raise SystemExit(main())
