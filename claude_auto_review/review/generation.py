import subprocess
from pathlib import Path

from claude_auto_review.review.rendering import (
    _review_context,
    current_file_snapshots,
    format_file_list,
    format_review_timestamp,
)
from claude_auto_review.review.prompt_templates import (
    build_prompt as _build_prompt,
    format_review_file,
    format_review_files as _format_review_files,
    format_review_prompt,
)

_GIT_DIFF_UNAVAILABLE_MESSAGE = "Git diff unavailable. Review the current file contents directly."

_REVIEW_PROMPT_TEMPLATE = """# Claude Auto Review Request {review_id}

You must review the changed files before stopping. Use the reviewer agent behavior from `agents/reviewer.md`: focus on semantic bugs, security, maintainability, and project rules. Do not nitpick formatting.

## Review Output

Output the final review to stdout. It will be captured and saved to the review file. You do not have Write or Edit tools.

Use this exact top matter:

```markdown
# Review {review_id} - {readable_timestamp}

## Files Reviewed
{file_list}

## Findings
```

If no findings exist, write "Clean - no issues found. Claude may stop." under "## Verdict".

## Files To Review
{file_list}

## Rules
{rules}

## Git Diff
```diff
{diff}
```

## Current File Snapshots
{snapshots}

Complete the review in 10 turns or less."""

_REVIEW_FILE_TEMPLATE = """# Review {review_id} - {readable_timestamp}

## Files Reviewed
{file_list}

## Findings

Pending. Claude must complete this review from {prompt_path}.

## Verdict

Pending.
"""


def _read_text_with_limit(path, max_chars, encoding="utf-8"):
    chunks = []
    remaining = max_chars + 1
    with Path(path).open("r", encoding=encoding, errors="replace") as handle:
        while remaining > 0:
            chunk = handle.read(min(remaining, _TEXT_READ_CHUNK_SIZE))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
    return "".join(chunks)


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


def read_if_exists(path, fallback=""):
    path = Path(path)
    return path.read_text(encoding="utf-8") if path.exists() else fallback
def format_review_files(entries, prompt_path, review_id, timestamp):
    return _format_review_files(entries, prompt_path, review_id, timestamp, _review_context)


def build_prompt(review_id, timestamp, entries, rules, diff, snapshots, review_path):
    return _build_prompt(review_id, timestamp, entries, rules, diff, snapshots, review_path, _review_context)
