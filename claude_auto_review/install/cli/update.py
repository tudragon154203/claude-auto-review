#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from claude_auto_review.paths.path_utils import ProjectContext
from claude_auto_review.runtime.events import log_event


def _run_git(args, cwd):
    return subprocess.run(
        ["git", "-C", str(cwd), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def _git_checkout_root(plugin_root=None):
    plugin_root = Path(plugin_root or ProjectContext.from_environment().plugin_root).resolve()
    result = _run_git(["rev-parse", "--show-toplevel"], plugin_root)
    if result.returncode != 0:
        return None, result
    return Path(result.stdout.strip()), result


def _print_completed_process(result):
    if result.stdout:
        print(result.stdout.rstrip())
    if result.stderr:
        print(result.stderr.rstrip(), file=sys.stderr)


def _rerun_setup(project_root):
    return subprocess.run(
        [sys.executable, "-m", "claude_auto_review.install.cli.setup"],
        cwd=project_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def main():
    project_root = ProjectContext.from_environment().project_root
    checkout_root, probe = _git_checkout_root()
    if checkout_root is None:
        _print_completed_process(probe)
        print("Claude Auto Review update requires a git checkout install.", file=sys.stderr)
        return 1

    print(f"Updating Claude Auto Review from {checkout_root}")
    pull = _run_git(["pull", "--ff-only"], checkout_root)
    _print_completed_process(pull)
    if pull.returncode != 0:
        log_event(project_root, "update_failed", checkout=str(checkout_root), returncode=pull.returncode)
        return pull.returncode

    setup = _rerun_setup(project_root)
    _print_completed_process(setup)
    if setup.returncode != 0:
        log_event(project_root, "update_setup_failed", checkout=str(checkout_root), returncode=setup.returncode)
        return setup.returncode

    log_event(project_root, "update_completed", checkout=str(checkout_root))
    print("Claude Auto Review update completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
