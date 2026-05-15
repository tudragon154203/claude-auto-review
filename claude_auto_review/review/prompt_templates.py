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

Complete the review in 20 turns or less."""

_REVIEW_FILE_TEMPLATE = """# Review {review_id} - {readable_timestamp}

## Files Reviewed
{file_list}

## Findings

No findings yet. This file is a placeholder until Claude completes the review.

Pending. Claude must complete this review from {prompt_path}.

## Verdict

Pending.
"""


def format_review_prompt(
    review_id,
    readable_timestamp,
    file_list,
    rules,
    diff,
    snapshots,
    review_path,
):
    return _REVIEW_PROMPT_TEMPLATE.format(
        review_id=review_id,
        readable_timestamp=readable_timestamp,
        file_list=file_list,
        rules=rules,
        diff=diff,
        snapshots=snapshots,
    )


def format_review_file(review_id, readable_timestamp, file_list, prompt_path):
    return _REVIEW_FILE_TEMPLATE.format(
        review_id=review_id,
        readable_timestamp=readable_timestamp,
        file_list=file_list,
        prompt_path=prompt_path,
    )


def format_review_files(entries, prompt_path, review_id, timestamp, review_context):
    readable_timestamp, file_list = review_context(entries, timestamp)
    return format_review_file(review_id, readable_timestamp, file_list, prompt_path)


def build_prompt(review_id, timestamp, entries, rules, diff, snapshots, review_path, review_context):
    readable_timestamp, file_list = review_context(entries, timestamp)
    return format_review_prompt(
        review_id,
        readable_timestamp,
        file_list,
        rules,
        diff,
        snapshots,
        review_path,
    )
