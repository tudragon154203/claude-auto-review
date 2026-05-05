#!/usr/bin/env python3
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from state import ensure_runtime, get_project_root, get_unreviewed_files, load_settings, load_state, log_event  # noqa: E402


def main():
    try:
        project_root = get_project_root()
        ensure_runtime(project_root)
        settings = load_settings(project_root)
        if not settings.get("enabled", True):
            log_event(project_root, "stop_disabled")
            return 0

        unreviewed = get_unreviewed_files(load_state(project_root))
        if not unreviewed:
            log_event(project_root, "stop_approved", reason="no_unreviewed_files")
            return 0

        files = ", ".join(entry["file"] for entry in unreviewed)
        plugin_review_script = Path(__file__).resolve().parent.parent / "scripts" / "review_prompt.py"
        project_review_script = project_root / ".claude" / "claude-auto-review" / "scripts" / "review_prompt.py"
        command = f'python "{plugin_review_script}"'
        print(
            json.dumps(
                {
                    "block": True,
                    "message": f"Claude Auto Review: Unreviewed changes detected in {files}.",
                    "feedback": (
                        f"Review required before stopping. Run {command}, follow the generated review prompt, "
                        "write the review, and fix any CRITICAL or HIGH findings you agree with. "
                        f"Project-local script path after setup: {project_review_script}"
                    ),
                    "continue": False,
                },
                separators=(",", ":"),
            )
        )
        log_event(project_root, "stop_blocked", files=[entry["file"] for entry in unreviewed])
        return 2
    except Exception as error:
        try:
            log_event(get_project_root(), "stop_error", error=str(error))
        except Exception:
            pass
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
