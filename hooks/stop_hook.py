#!/usr/bin/env python3
from claude_auto_review.hooks.entrypoint import ensure_repo_root_on_path, run_module_main

ensure_repo_root_on_path(__file__)

if __name__ == "__main__":
    raise SystemExit(run_module_main("claude_auto_review.hooks.stop_hook"))
