from __future__ import annotations

import shutil
from importlib import resources
from pathlib import Path

from claude_auto_review.config.io.hooks import (
    load_hooks_document,
    merge_hook_buckets,
    merge_unique_hook_list,
)
from claude_auto_review.config.io.project import ensure_project_settings_document
from claude_auto_review.paths.path_utils import RUNTIME_DIR, STATE_RELATIVE_PATH
from claude_auto_review.runtime.client_dirs import get_client_runtime_dir
from claude_auto_review.runtime.context import resolve_project_root


def _package_resource_path(*parts):
    return resources.files("claude_auto_review").joinpath(*parts)


def _load_hooks_document(plugin_root=None):
    hooks_path = (
        _package_resource_path("hooks", "hooks.json")
        if plugin_root is None
        else Path(plugin_root) / "hooks" / "hooks.json"
    )
    return load_hooks_document(Path(hooks_path))


def _merge_unique_list(existing_items, desired_items):
    return merge_unique_hook_list(existing_items, desired_items)


def _merge_hooks(existing_hooks, desired_hooks):
    return merge_hook_buckets(existing_hooks, desired_hooks)


def _ensure_runtime_directories(base_dir, state_path):
    base_dir.mkdir(parents=True, exist_ok=True)
    state_path.parent.mkdir(parents=True, exist_ok=True)


def _ensure_rules_file(base_dir, plugin_root):
    rules_path = base_dir / "review-rules.md"
    if rules_path.exists():
        return rules_path

    if plugin_root:
        default_rules_path = Path(plugin_root) / "rules" / "review-rules.md"
    else:
        default_rules_path = _package_resource_path("rules", "review-rules.md")
    if default_rules_path.is_file():
        shutil.copyfile(default_rules_path, rules_path)
    else:
        rules_path.write_text(
            "# Claude Auto Review Rules\n\n- Review semantic correctness, security, and maintainability.\n",
            encoding="utf-8",
        )
    return rules_path


def ensure_client_runtime(project_root, client_id):
    client_dir = get_client_runtime_dir(project_root, client_id)
    client_dir.mkdir(parents=True, exist_ok=True)
    (client_dir / "state.jsonl").touch(exist_ok=True)
    (client_dir / "reviews").mkdir(exist_ok=True)
    (client_dir / "run").mkdir(exist_ok=True)
    return client_dir


def ensure_runtime(project_root=None, plugin_root=None):
    project_root = resolve_project_root(project_root)
    base_dir = project_root / RUNTIME_DIR
    state_path = project_root / STATE_RELATIVE_PATH
    _ensure_runtime_directories(base_dir, state_path)
    rules_path = _ensure_rules_file(base_dir, plugin_root)

    return {
        "base_dir": base_dir,
        "state_path": state_path,
        "rules_path": rules_path,
        "log_path": state_path,
    }


def ensure_project_settings(project_root=None):
    project_root = resolve_project_root(project_root)
    hooks_document = _load_hooks_document()
    return ensure_project_settings_document(project_root, hooks_document)
