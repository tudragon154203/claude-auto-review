from pathlib import Path

from claude_auto_review.install.shims import build_runpy_shim_content


def _write_text_if_changed(path, content):
    path = Path(path)
    if not path.exists() or path.read_text(encoding="utf-8") != content:
        path.write_text(content, encoding="utf-8", newline="\n")


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
        build_runpy_shim_content(plugin_root / "claude_auto_review" / "review" / "prompt.py"),
    )
    _write_text_if_changed(
        runtime_scripts / "cancel_claude_auto_review.py",
        build_runpy_shim_content(plugin_root / "claude_auto_review" / "install" / "cancel_cli.py"),
    )


def ensure_gitignore_entries(gitignore_path, ignore_entries):
    gitignore_path = Path(gitignore_path)
    existing = gitignore_path.read_text(encoding="utf-8") if gitignore_path.exists() else ""
    existing_lines = set(existing.splitlines())
    missing = [entry for entry in ignore_entries if entry not in existing_lines]
    if missing:
        prefix = "" if not existing or existing.endswith("\n") else "\n"
        with gitignore_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(prefix + "\n".join(missing) + "\n")
