from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from claude_auto_review.runtime.client_dirs import client_reviews_dir, client_run_dir
from claude_auto_review.paths.path_utils import local_now_iso
from claude_auto_review.review.prompting.generation import (
    build_prompt,
    format_review_files,
    git_diff,
    read_if_exists,
)
from claude_auto_review.review.prompting.rendering import current_file_snapshots
from claude_auto_review.config.rules import resolve_rules_file_path
from claude_auto_review.stop.orchestration.context import RuntimeContext
from claude_auto_review.timestamps import parse_iso_timestamp


@dataclass(frozen=True)
class ReviewPromptArtifacts:
    review_id: str
    prompt_path: Path
    review_path: Path
    files: list[str]


def _review_id_from_timestamp(timestamp):
    try:
        parsed = parse_iso_timestamp(timestamp)
    except (TypeError, ValueError):
        return "rev-" + "".join(ch for ch in timestamp if ch.isdigit())
    return "rev-" + parsed.strftime("%Y%m%d%H%M%S%f")


def _review_prompt_paths(ctx: RuntimeContext, review_id):
    return (
        client_reviews_dir(ctx.project_root, ctx.client_id) / f"review-{review_id}.md",
        client_run_dir(ctx.project_root, ctx.client_id) / f"review-{review_id}-prompt.md",
    )


def _write_text_file(path, content):
    path.write_text(content, encoding="utf-8", newline="\n")


def create_review_prompt_files(ctx: RuntimeContext, unreviewed, settings=None):
    settings = settings or ctx.settings
    timestamp = local_now_iso()
    review_id = _review_id_from_timestamp(timestamp)
    files = [entry.file for entry in unreviewed]

    rules = read_if_exists(resolve_rules_file_path(ctx.project_root, settings))
    diff = git_diff(files, ctx.project_root)
    snapshots = current_file_snapshots(files, ctx.project_root)

    review_path, prompt_path = _review_prompt_paths(ctx, review_id)

    _write_text_file(prompt_path, build_prompt(review_id, timestamp, unreviewed, rules, diff, snapshots, review_path))
    _write_text_file(review_path, format_review_files(unreviewed, prompt_path, review_id, timestamp))

    return ReviewPromptArtifacts(
        review_id=review_id,
        prompt_path=prompt_path,
        review_path=review_path,
        files=files,
    )
