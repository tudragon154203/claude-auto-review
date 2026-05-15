#!/usr/bin/env python3
import sys
from pathlib import Path

# Ensure repo root is on path so claude_auto_review package is importable
_repo_root = Path(__file__).resolve().parent.parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))
from claude_auto_review.utils.core.bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from claude_auto_review.paths.core.path_utils import get_project_root
from claude_auto_review.install.core.installer import copy_if_changed, ensure_gitignore_entries, write_runtime_shims
from claude_auto_review.runtime.core.setup import ensure_project_settings, ensure_runtime
from claude_auto_review.runtime.core.events import log_event


def main():
    project_root = get_project_root()
    plugin_root = Path(__file__).resolve().parent.parent.parent
    runtime = ensure_runtime(project_root, plugin_root)
    ensure_project_settings(project_root)
    runtime_scripts = runtime["base_dir"] / "scripts"
    runtime_agents = runtime["base_dir"] / "agents"
    runtime_agents.mkdir(parents=True, exist_ok=True)

    write_runtime_shims(runtime_scripts, plugin_root)
    copy_if_changed(plugin_root / "agents" / "reviewer.md", runtime_agents / "reviewer.md")

    ensure_gitignore_entries(
        project_root / ".gitignore",
        [
            ".claude/claude-auto-review/",
        ],
        remove_entries=[
            ".claude/claude-auto-review/clients/*/run/",
            ".claude/claude-auto-review/clients/*/reviews/",
            ".claude/claude-auto-review/scripts/",
            ".claude/claude-auto-review/agents/",
            ".claude/claude-auto-review/claude-auto-review.log",
        ],
    )

    log_event(project_root, "setup_completed")
    print(f"Claude Auto Review initialized at {runtime['base_dir']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
