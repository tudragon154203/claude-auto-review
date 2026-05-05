#!/usr/bin/env python3
from pathlib import Path

from state import ensure_runtime, get_project_root


def copy_if_changed(source, destination):
    source = Path(source)
    destination = Path(destination)
    if not source.exists():
        return
    content = source.read_text(encoding="utf-8")
    if not destination.exists() or destination.read_text(encoding="utf-8") != content:
        destination.write_text(content, encoding="utf-8", newline="\n")


def main():
    project_root = get_project_root()
    plugin_root = Path(__file__).resolve().parent.parent
    runtime = ensure_runtime(project_root, plugin_root)
    runtime_scripts = runtime["base_dir"] / "scripts"
    runtime_agents = runtime["base_dir"] / "agents"
    runtime_scripts.mkdir(parents=True, exist_ok=True)
    runtime_agents.mkdir(parents=True, exist_ok=True)

    shim_path = runtime_scripts / "review_prompt.py"
    plugin_review_script = plugin_root / "scripts" / "review_prompt.py"
    shim_path.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "import runpy\n"
        f"sys.path.insert(0, {str(plugin_review_script.parent)!r})\n"
        f"runpy.run_path({str(plugin_review_script)!r}, run_name='__main__')\n",
        encoding="utf-8",
        newline="\n",
    )
    copy_if_changed(plugin_root / "agents" / "reviewer.md", runtime_agents / "reviewer.md")

    gitignore_path = project_root / ".gitignore"
    ignore_entries = [
        ".claude/claude-auto-review/state.jsonl",
        ".claude/claude-auto-review/run/",
        ".claude/claude-auto-review/reviews/",
    ]
    existing = gitignore_path.read_text(encoding="utf-8") if gitignore_path.exists() else ""
    existing_lines = set(existing.splitlines())
    missing = [entry for entry in ignore_entries if entry not in existing_lines]
    if missing:
        prefix = "" if not existing or existing.endswith("\n") else "\n"
        with gitignore_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(prefix + "\n".join(missing) + "\n")

    print(f"Claude Auto Review initialized at {runtime['base_dir']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
