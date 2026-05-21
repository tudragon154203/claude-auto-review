from pathlib import Path

from claude_auto_review.paths.file_utils import write_text_if_changed as _write_text_if_changed
from claude_auto_review.paths.shims import build_runpy_shim_content


def copy_if_changed(source, destination):
    source = Path(source)
    destination = Path(destination)
    if not source.exists():
        return
    content = source.read_text(encoding="utf-8")
    _write_text_if_changed(destination, content)


def write_runtime_shims(runtime_scripts, plugin_root):
    runtime_scripts = Path(runtime_scripts)
    plugin_root = Path(plugin_root)
    runtime_scripts.mkdir(parents=True, exist_ok=True)
    _write_text_if_changed(
        runtime_scripts / "review_prompt.py",
        build_runpy_shim_content(plugin_root / "review" / "prompt.py"),
    )
    _write_text_if_changed(
        runtime_scripts / "cancel_claude_auto_review.py",
        build_runpy_shim_content(plugin_root / "install" / "cancel_cli.py"),
    )


def ensure_gitignore_entries(gitignore_path, ignore_entries, remove_entries=None):
    gitignore_path = Path(gitignore_path)
    existing = gitignore_path.read_text(encoding="utf-8") if gitignore_path.exists() else ""
    lines = existing.splitlines()
    remove_entries = set(remove_entries or [])
    filtered_lines = [line for line in lines if line not in remove_entries]
    existing_lines = set(filtered_lines)
    missing = [entry for entry in ignore_entries if entry not in existing_lines]
    if filtered_lines != lines or missing:
        if filtered_lines and missing:
            filtered_lines.extend(missing)
        elif missing:
            filtered_lines = list(missing)
        with gitignore_path.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write("\n".join(filtered_lines) + "\n")
