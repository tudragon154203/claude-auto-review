from __future__ import annotations

from pathlib import Path


DEFAULT_FEEDBACK_MAX_CHARS = 9000


def _file_of(entry):
    return entry.file


def build_unreviewed_files_string(unreviewed_entries):
    return ", ".join(_file_of(entry) for entry in unreviewed_entries)


def build_review_completion_prompt(review_path):
    return (
        f"Complete the review at {review_path}. "
        "Return only the final markdown review to stdout. "
        "Do not output planning notes, progress updates, or next-step narration. "
        "Read each file, evaluate findings, set verdicts "
        "(Confirmed/Skipped), and write the final review "
        "with a non-Pending Verdict."
    )


def review_feedback_max_chars(settings):
    return settings.review_feedback_max_chars


def _minimum_blocking_severity_message(minimum_blocking_severity=None):
    severity = str(minimum_blocking_severity or "").strip().lower()
    if not severity or severity == "info":
        return "All Confirmed findings block stopping."
    return (
        f"Confirmed findings at {severity.title()} severity or higher block stopping. "
        "Lower-severity Confirmed findings are advisory at the current threshold."
    )


def read_review_feedback(review_path, max_chars=None, project_root=None):
    if max_chars is None:
        max_chars = DEFAULT_FEEDBACK_MAX_CHARS
    path = Path(review_path)
    display = path.relative_to(project_root).as_posix() if project_root else str(path)
    if not path.is_file():
        return f"Review file is missing: {display}"
    content = path.read_text(encoding="utf-8", errors="replace")
    if len(content) <= max_chars:
        return content
    return (
        f"{content[:max_chars]}\n\n"
        f"[Review truncated at {max_chars} characters. Read the full review at {display}.]"
    )


def build_review_findings_feedback(
    review_id,
    review_path,
    max_chars=None,
    project_root=None,
    minimum_blocking_severity=None,
):
    review_text = read_review_feedback(review_path, max_chars=max_chars, project_root=project_root)
    display = Path(review_path).relative_to(project_root).as_posix() if project_root else review_path
    return (
        f"Claude Auto Review completed review {review_id} and found blocking findings.\n\n"
        f"Review file: {display}\n\n"
        "Act on the review below before stopping. Fix each blocking Confirmed finding, "
        "or make a narrowly justified code change that renders it inapplicable. "
        f"{_minimum_blocking_severity_message(minimum_blocking_severity)} "
        "Skipped findings never block. After making changes, try stopping again so the changed files are reviewed.\n\n"
        f"{review_text}"
    )
