import subprocess
from pathlib import Path

from claude_auto_review.review.prompt_templates import (
    build_prompt as _build_prompt,
    format_review_file,
    format_review_files as _format_review_files,
)
from claude_auto_review.review.rendering import _review_context, current_file_snapshots, format_review_timestamp

_GIT_DIFF_UNAVAILABLE_MESSAGE = "Git diff unavailable. Review the current file contents directly."


def git_diff(files, project_root):
    try:
        result = subprocess.run(
            ["git", "diff", "--", *files],
            cwd=project_root,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        return result.stdout
    except Exception as error:
        stderr = getattr(error, "stderr", "") or ""
        return f"{_GIT_DIFF_UNAVAILABLE_MESSAGE}\n{stderr.strip()}"


def format_review_files(entries, prompt_path, review_id, timestamp):
    return _format_review_files(entries, prompt_path, review_id, timestamp, _review_context)


def build_prompt(review_id, timestamp, entries, rules, diff, snapshots, review_path):
    return _build_prompt(review_id, timestamp, entries, rules, diff, snapshots, review_path, _review_context)


def read_if_exists(path, fallback=""):
    path = Path(path)
    return path.read_text(encoding="utf-8") if path.exists() else fallback
