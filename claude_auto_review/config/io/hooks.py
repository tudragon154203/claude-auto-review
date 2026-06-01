"""Pure hook-list and hook-bucket merge operations.

These are generic collection operations with no filesystem or settings
dependencies — kept here so they can be tested in isolation and reused
without pulling in the full config/project_settings orchestration.
"""

from __future__ import annotations

import json

from claude_auto_review.runtime.hook_identity import (
    is_plugin_hook,
    plugin_script_name_from_hook,
)


def load_hooks_document(hooks_path):
    """Load a hooks JSON document from disk, returning a minimal empty structure on failure."""
    try:
        data = hooks_path.read_text(encoding="utf-8")
        parsed = json.loads(data) if data.strip() else {}
    except (OSError, json.JSONDecodeError):
        return {"hooks": {}}
    return parsed if isinstance(parsed, dict) else {"hooks": {}}


def _seen_key(item):
    if isinstance(item, dict) and is_plugin_hook(item):
        return ("__plugin__", plugin_script_name_from_hook(item))
    return ("__plain__", json.dumps(item, sort_keys=True, ensure_ascii=False))


def merge_unique_hook_list(existing_items, desired_items):
    """Merge two hook entry lists, deduplicating by key and preferring plugin entries."""
    existing = list(existing_items) if isinstance(existing_items, list) else []
    desired = list(desired_items) if isinstance(desired_items, list) else []
    seen = {}

    merged = []
    for item in existing:
        key = _seen_key(item)
        if key not in seen:
            merged.append(item)
            seen[key] = len(merged) - 1

    for item in desired:
        key = _seen_key(item)
        if key in seen:
            if key[0] == "__plugin__":
                merged[seen[key]] = item
        else:
            merged.append(item)
            seen[key] = len(merged) - 1

    return merged


def merge_hook_buckets(existing_hooks, desired_hooks):
    """Merge two hook-name → [entries] dictionaries."""
    merged = dict(existing_hooks) if isinstance(existing_hooks, dict) else {}
    for hook_name, desired_entries in desired_hooks.items():
        merged[hook_name] = merge_unique_hook_list(merged.get(hook_name, []), desired_entries)
    return merged