from __future__ import annotations

import subprocess
from pathlib import Path

from claude_auto_review.review.prompting.rendering import _review_context
from claude_auto_review.review.prompting.templates import (
    build_prompt as _build_prompt,
)
from claude_auto_review.review.prompting.templates import (
    format_review_files as _format_review_files,
)
from claude_auto_review.runtime.process import run_captured

_GIT_DIFF_UNAVAILABLE_MESSAGE = "Git diff unavailable. Review the current file contents directly."


def git_diff(files, project_root):
    try:
        result = run_captured(
            ["git", "diff", "--", *files],
            cwd=project_root,
            check=True,
        )
        return result.stdout
    except subprocess.CalledProcessError as error:
        stderr = error.stderr or ""
        return f"{_GIT_DIFF_UNAVAILABLE_MESSAGE}\n{stderr.strip()}"
    except (OSError, FileNotFoundError):
        return _GIT_DIFF_UNAVAILABLE_MESSAGE


def format_review_files(entries, prompt_path, review_id, timestamp, reviewer_backend="claude", reviewer_model=""):
    return _format_review_files(
        entries,
        prompt_path,
        review_id,
        timestamp,
        _review_context,
        reviewer_backend=reviewer_backend,
        reviewer_model=reviewer_model,
    )


def build_prompt(
    review_id, timestamp, entries, rules, diff, snapshots, review_path, reviewer_backend="claude", reviewer_model=""
):
    return _build_prompt(
        review_id,
        timestamp,
        entries,
        rules,
        diff,
        snapshots,
        review_path,
        _review_context,
        reviewer_backend=reviewer_backend,
        reviewer_model=reviewer_model,
    )


def read_if_exists(path, fallback=""):
    path = Path(path)
    return path.read_text(encoding="utf-8") if path.exists() else fallback
