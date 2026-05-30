#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

if __name__ == "__main__":
    _plugin_root = Path(__file__).resolve().parents[2]
    if str(_plugin_root) not in sys.path:
        sys.path.insert(0, str(_plugin_root))

from claude_auto_review.install.installer import copy_if_changed, ensure_gitignore_entries, write_runtime_shims
from claude_auto_review.install.reviewer_format import check_and_repair_reviewer
from claude_auto_review.paths.path_utils import get_plugin_root, get_project_root
from claude_auto_review.runtime.events import log_event
from claude_auto_review.runtime.setup import ensure_project_settings, ensure_runtime


def main():
    project_root = get_project_root()
    plugin_root = get_plugin_root()
    runtime = ensure_runtime(project_root)
    ensure_project_settings(project_root)
    runtime_scripts = runtime["base_dir"] / "scripts"
    runtime_agents = runtime["base_dir"] / "agents"
    runtime_agents.mkdir(parents=True, exist_ok=True)

    repaired_text, consistency_warnings, was_repaired = check_and_repair_reviewer(plugin_root)
    for warning in consistency_warnings:
        print(f"[WARNING] {warning}", file=sys.stderr)
    if was_repaired:
        print("[WARNING] reviewer.md was auto-repaired for parser consistency. "
              "Review the runtime copy at .claude/claude-auto-review/agents/reviewer.md.", file=sys.stderr)

    write_runtime_shims(runtime_scripts, plugin_root)
    if was_repaired and repaired_text is not None:
        (runtime_agents / "reviewer.md").write_text(repaired_text, encoding="utf-8")
    else:
        copy_if_changed(plugin_root / "agents" / "reviewer.md", runtime_agents / "reviewer.md")

    ensure_gitignore_entries(
        project_root / ".gitignore",
        [".claude/claude-auto-review/"],
        remove_entries=[
            ".claude/claude-auto-review/clients/*/run/",
            ".claude/claude-auto-review/clients/*/reviews/",
            ".claude/claude-auto-review/scripts/",
            ".claude/claude-auto-review/agents/",
        ],
    )

    log_event(project_root, "setup_completed")
    print(f"Claude Auto Review initialized at {runtime['base_dir']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
