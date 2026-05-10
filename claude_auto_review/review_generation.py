import subprocess
from datetime import datetime
from pathlib import Path


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
        return f"Git diff unavailable. Review the current file contents directly.\n{stderr.strip()}"


def read_if_exists(path, fallback=""):
    path = Path(path)
    return path.read_text(encoding="utf-8") if path.exists() else fallback


def format_review_timestamp(timestamp):
    ts = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    local_ts = ts.astimezone()
    offset = local_ts.strftime("%z")
    offset = f"{offset[:3]}:{offset[3:]}" if offset else ""
    return f"{local_ts.strftime('%Y-%m-%d | %H:%M:%S')} {offset}".rstrip()


def format_file_list(entries):
    return "\n".join(f"- {entry['file']} (hash: {entry['hash']})" for entry in entries)


def format_review_prompt(
    review_id,
    readable_timestamp,
    file_list,
    rules,
    diff,
    snapshots,
    review_path,
):
    return f"""# Claude Auto Review Request {review_id}

You must review the changed files before stopping. Use the reviewer agent behavior from `agents/reviewer.md`: focus on semantic bugs, security, maintainability, and project rules. Do not nitpick formatting.

## Review Output

Write the final review to:

`{review_path}`

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

## After Review

After receiving review results:

1. Show all findings to the user.
2. Evaluate each finding against one heuristic: what produces the highest quality code?
3. Fix the finding unless one of these skip reasons clearly applies:
   - IMPOSSIBLE: you tried the fix and cannot satisfy feedback, product requirements, lint rules, and tests simultaneously.
   - CONFLICTS WITH REQUIREMENTS: the feedback directly contradicts explicit product requirements.
   - MAKES CODE WORSE: applying the feedback would genuinely degrade code quality.
4. These are not valid skip reasons:
   - too much time
   - too complex
   - out of scope after you touched the file
   - pre-existing code
   - only renamed or moved
   - would require a larger refactor
5. If uncertain, ask the user.

If you edit files, the hook will track those new hashes and require another review pass."""


def format_review_file(review_id, readable_timestamp, file_list, prompt_path):
    return f"""# Review {review_id} - {readable_timestamp}

## Files Reviewed
{file_list}

## Findings

Pending. Claude must complete this review from {prompt_path}.

## Verdict

Pending.
"""


def format_review_files(entries, prompt_path, review_id, timestamp):
    readable_timestamp = format_review_timestamp(timestamp)
    file_list = format_file_list(entries)
    return format_review_file(review_id, readable_timestamp, file_list, prompt_path)


def current_file_snapshots(files, project_root):
    sections = []
    max_chars = 40000
    for file_path in files:
        full_path = Path(project_root) / file_path
        if not full_path.is_file():
            sections.append(_format_missing_file_snapshot(file_path))
            continue
        content = full_path.read_text(encoding="utf-8", errors="replace")
        sections.append(_format_file_snapshot(file_path, content, max_chars=max_chars))
    return "\n\n".join(sections)


def build_prompt(review_id, timestamp, entries, rules, diff, snapshots, review_path):
    readable_timestamp = format_review_timestamp(timestamp)
    file_list = format_file_list(entries)
    return format_review_prompt(
        review_id,
        readable_timestamp,
        file_list,
        rules,
        diff,
        snapshots,
        review_path,
    )


def _format_missing_file_snapshot(file_path):
    return f"## {file_path}\n\nFile does not currently exist."


def _format_file_snapshot(file_path, content, max_chars=40000):
    if len(content) > max_chars:
        content = f"{content[:max_chars]}\n\n[truncated at {max_chars} characters]"
    return f"## {file_path}\n\n```\n{content}\n```"
