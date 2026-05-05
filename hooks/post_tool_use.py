#!/usr/bin/env python3
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from state import (  # noqa: E402
    append_state,
    ensure_runtime,
    extract_file_paths_from_hook_input,
    get_file_hash,
    get_project_root,
    load_settings,
    load_state,
    normalize_relative_path,
    should_skip_file,
    utc_now_iso,
    was_hash_reviewed,
)


def main():
    try:
        project_root = get_project_root()
        ensure_runtime(project_root)
        settings = load_settings(project_root)
        if not settings.get("enabled", True):
            return 0

        raw = sys.stdin.read().strip()
        payload = json.loads(raw) if raw else {}
        state = load_state(project_root)
        timestamp = utc_now_iso()

        for candidate in extract_file_paths_from_hook_input(payload):
            file_path = normalize_relative_path(candidate, project_root)
            if not file_path or should_skip_file(file_path, settings):
                continue
            file_hash = get_file_hash(file_path, project_root)
            if not file_hash:
                continue
            append_state(
                {
                    "type": "edit",
                    "file": file_path,
                    "hash": file_hash,
                    "timestamp": timestamp,
                    "reviewed": was_hash_reviewed(state, file_path, file_hash),
                },
                project_root,
            )
        return 0
    except Exception:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
