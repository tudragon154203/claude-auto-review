from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from claude_auto_review.config.resolvers.rules import resolve_rules_file_path
from claude_auto_review.timestamps import local_now_iso
from claude_auto_review.review.prompting.diff_mode import all_session_diffs
from claude_auto_review.review.prompting.generation import (
    build_prompt,
    format_review_files,
    read_if_exists,
)
from claude_auto_review.runtime.client_dirs import client_reviews_dir, client_run_dir
from claude_auto_review.stop.orchestration.types.context import RuntimeContext
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


def resolve_review_paths(ctx: RuntimeContext, review_id: str) -> tuple[Path, Path]:
    return (
        client_reviews_dir(ctx.project_root, ctx.client_id) / f"review-{review_id}.md",
        client_run_dir(ctx.project_root, ctx.client_id) / f"review-{review_id}-prompt.md",
    )


def _load_rules_content(settings, project_root: Path) -> str | None:
    content = read_if_exists(resolve_rules_file_path(project_root, settings))
    return content if content else None


def _resolve_reviewer_model(settings, backend: str) -> str:
    from claude_auto_review.config.resolvers.reviewer import resolved_reviewer_model
    try:
        model: str = resolved_reviewer_model(settings, backend=backend)
        return model
    except (ValueError, KeyError):
        return settings.reviewer.reviewer_model or ""


def _build_review_contents(ctx: RuntimeContext, unreviewed, rules_content, settings, *, review_path: Path, review_id: str, timestamp: str, prompt_path: Path):
    files = [entry.file for entry in unreviewed]
    diff = all_session_diffs(files, ctx.project_root, ctx.client_id)
    reviewer_backend = settings.reviewer.reviewer_backend
    reviewer_model = _resolve_reviewer_model(settings, reviewer_backend)

    prompt_content = build_prompt(
        review_id,
        timestamp,
        unreviewed,
        rules_content,
        diff,
        review_path,
        reviewer_backend=reviewer_backend,
        reviewer_model=reviewer_model,
    )
    review_content = format_review_files(
        unreviewed,
        prompt_path,
        review_id,
        timestamp,
        reviewer_backend=reviewer_backend,
        reviewer_model=reviewer_model,
    )
    return prompt_content, review_content, files


def build_review_prompt_content(ctx: RuntimeContext, unreviewed, settings, review_path: Path, *, review_id: str, timestamp: str, prompt_path: Path):
    rules = _load_rules_content(settings, ctx.project_root)
    return _build_review_contents(
        ctx, unreviewed, rules, settings,
        review_path=review_path, review_id=review_id, timestamp=timestamp, prompt_path=prompt_path,
    )


def _write_text_file(path, content):
    path.write_text(content, encoding="utf-8", newline="\n")


def create_review_prompt_files(
    ctx: RuntimeContext,
    unreviewed,
    settings=None,
    *,
    writer: Callable[[Path, str], None] = _write_text_file,
):
    settings = settings or ctx.settings
    timestamp = local_now_iso()
    review_id = _review_id_from_timestamp(timestamp)

    review_path, prompt_path = resolve_review_paths(ctx, review_id)
    prompt_content, review_content, files = build_review_prompt_content(
        ctx, unreviewed, settings, review_path,
        review_id=review_id, timestamp=timestamp, prompt_path=prompt_path,
    )

    writer(prompt_path, prompt_content)
    writer(review_path, review_content)

    return ReviewPromptArtifacts(
        review_id=review_id,
        prompt_path=prompt_path,
        review_path=review_path,
        files=files,
    )
