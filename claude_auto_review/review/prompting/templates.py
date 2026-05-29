from __future__ import annotations

_REVIEW_PROMPT_TEMPLATE = """# Claude Auto Review Request {review_id}

You must review the changed files before stopping. Use the reviewer agent behavior from `agents/reviewer.md`: focus on semantic bugs, security, maintainability, and project rules. Do not nitpick formatting.

## Review Output

Output only the final review markdown to stdout. It will be captured and saved to the review file. Do not emit progress updates, planning notes, or any text before or after the final markdown review. You do not have Write or Edit tools.

Use this exact structure:

```markdown
# Review {review_id} - {readable_timestamp}

## Reviewer
Backend: {reviewer_backend} | Model: {reviewer_model}

## Files Reviewed
{file_list}

## Findings
- Confirmed: <title>
  Severity: info|low|medium|high|critical
  Location: path:line
  Rationale: <why this matters>
  Suggestion: <concrete fix>
- Skipped: <title>
  Reason: <why this item cannot be reviewed>

## Verdict
Clean - no issues found. Claude may stop.
```

Rules for `## Findings`:
- Use only top-level `- Confirmed:` or `- Skipped:` entries for findings.
- Put details on indented `Field: value` lines under that bullet.
- If there are no findings, write exactly `None.` under `## Findings`.
- Do not write notes, commentary, or summaries inside `## Findings`.

Rules for `## Verdict`:
- If `## Findings` is `None.`, write exactly `Clean - no issues found. Claude may stop.`
- Otherwise write exactly `Findings present. Claude must address all findings before stopping.`

## Files To Review
{file_list}

## Rules
{rules}

## Session Diff
The diff below contains only changes made during this Claude Code session, compared against the file state before the first edit.

```diff
{diff}
```

Complete the review in a single response."""

_REVIEW_FILE_TEMPLATE = """# Review {review_id} - {readable_timestamp}

## Reviewer
Backend: {reviewer_backend} | Model: {reviewer_model}

## Files Reviewed
{file_list}

## Findings

No findings yet. This file is a placeholder until Claude completes the review.

Pending. Claude must complete this review from {prompt_path}.

## Verdict

Pending.
"""


def _safe(value: str) -> str:
    return value.replace("{", "{{").replace("}", "}}")


def format_review_prompt(
    review_id,
    readable_timestamp,
    file_list,
    rules,
    diff,
    snapshots,
    review_path,
    reviewer_backend="claude",
    reviewer_model="",
):
    return _REVIEW_PROMPT_TEMPLATE.format(
        review_id=review_id,
        readable_timestamp=readable_timestamp,
        file_list=file_list,
        rules=rules,
        diff=diff,
        snapshots=snapshots,
        reviewer_backend=_safe(reviewer_backend),
        reviewer_model=_safe(reviewer_model),
    )


def format_review_file(
    review_id, readable_timestamp, file_list, prompt_path, reviewer_backend="claude", reviewer_model=""
):
    return _REVIEW_FILE_TEMPLATE.format(
        review_id=review_id,
        readable_timestamp=readable_timestamp,
        file_list=file_list,
        prompt_path=prompt_path,
        reviewer_backend=_safe(reviewer_backend),
        reviewer_model=_safe(reviewer_model),
    )


def format_review_files(
    entries, prompt_path, review_id, timestamp, review_context, reviewer_backend="claude", reviewer_model=""
):
    readable_timestamp, file_list = review_context(entries, timestamp)
    return format_review_file(review_id, readable_timestamp, file_list, prompt_path, reviewer_backend, reviewer_model)


def build_prompt(
    review_id,
    timestamp,
    entries,
    rules,
    diff,
    snapshots,
    review_path,
    review_context,
    reviewer_backend="claude",
    reviewer_model="",
):
    readable_timestamp, file_list = review_context(entries, timestamp)
    return format_review_prompt(
        review_id,
        readable_timestamp,
        file_list,
        rules,
        diff,
        snapshots,
        review_path,
        reviewer_backend=reviewer_backend,
        reviewer_model=reviewer_model,
    )
