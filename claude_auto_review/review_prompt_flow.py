from dataclasses import dataclass
from pathlib import Path

from claude_auto_review.paths import client_reviews_dir, client_run_dir, utc_now_iso
from claude_auto_review.review_generation import (
    build_prompt,
    current_file_snapshots,
    format_review_files,
    git_diff,
    read_if_exists,
)
from claude_auto_review.settings import resolve_rules_file_path


@dataclass(frozen=True)
class ReviewPromptArtifacts:
    review_id: str
    prompt_path: Path
    review_path: Path
    files: list[str]


def _review_id_from_timestamp(timestamp):
    return "rev-" + "".join(ch for ch in timestamp if ch.isdigit())[:14]


def _review_prompt_paths(project_root, client_id, review_id):
    return (
        client_reviews_dir(project_root, client_id) / f"review-{review_id}.md",
        client_run_dir(project_root, client_id) / f"review-{review_id}-prompt.md",
    )


def _write_text_file(path, content):
    path.write_text(content, encoding="utf-8", newline="\n")


def create_review_prompt_files(project_root, client_id, unreviewed, settings):
    timestamp = utc_now_iso()
    review_id = _review_id_from_timestamp(timestamp)
    files = [entry["file"] for entry in unreviewed]

    rules = read_if_exists(resolve_rules_file_path(project_root, settings))
    diff = git_diff(files, project_root)
    snapshots = current_file_snapshots(files, project_root)

    review_path, prompt_path = _review_prompt_paths(project_root, client_id, review_id)

    _write_text_file(prompt_path, build_prompt(review_id, timestamp, unreviewed, rules, diff, snapshots, review_path))
    _write_text_file(review_path, format_review_files(unreviewed, prompt_path, review_id, timestamp))

    return ReviewPromptArtifacts(
        review_id=review_id,
        prompt_path=prompt_path,
        review_path=review_path,
        files=files,
    )

