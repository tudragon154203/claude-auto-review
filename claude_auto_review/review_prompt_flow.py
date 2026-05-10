from dataclasses import dataclass
from pathlib import Path

from claude_auto_review.paths import client_reviews_dir, client_run_dir, utc_now_iso
from claude_auto_review.review_generation import (
    build_prompt,
    current_file_snapshots,
    format_review_timestamp,
    git_diff,
    read_if_exists,
)


@dataclass(frozen=True)
class ReviewPromptArtifacts:
    review_id: str
    prompt_path: Path
    review_path: Path
    files: list[str]


def _resolve_rules_path(project_root, settings):
    rules_path = Path(settings.get("rulesFile", ""))
    if not rules_path.is_absolute():
        rules_path = project_root / ".claude" / "claude-auto-review" / "rules.md"
    return rules_path


def create_review_prompt_files(project_root, client_id, unreviewed, settings):
    timestamp = utc_now_iso()
    review_id = "rev-" + "".join(ch for ch in timestamp if ch.isdigit())[:14]
    files = [entry["file"] for entry in unreviewed]

    rules = read_if_exists(_resolve_rules_path(project_root, settings))
    diff = git_diff(files, project_root)
    snapshots = current_file_snapshots(files, project_root)

    review_path = client_reviews_dir(project_root, client_id) / f"review-{review_id}.md"
    prompt_path = client_run_dir(project_root, client_id) / f"review-{review_id}-prompt.md"

    prompt_path.write_text(
        build_prompt(review_id, timestamp, unreviewed, rules, diff, snapshots, review_path),
        encoding="utf-8",
        newline="\n",
    )
    file_list = "\n".join(f"- {entry['file']} (hash: {entry['hash']})" for entry in unreviewed)
    review_path.write_text(
        f"""# Review {review_id} - {format_review_timestamp(timestamp)}

## Files Reviewed
{file_list}

## Findings

Pending. Claude must complete this review from {prompt_path}.

## Verdict

Pending.
""",
        encoding="utf-8",
        newline="\n",
    )

    return ReviewPromptArtifacts(
        review_id=review_id,
        prompt_path=prompt_path,
        review_path=review_path,
        files=files,
    )

