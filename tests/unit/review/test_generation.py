import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
import sys
sys.path.insert(0, str(REPO_ROOT))

from claude_auto_review.state.models import EditRecord
from claude_auto_review.review.generation import (
    build_prompt,
    current_file_snapshots,
    format_review_file,
    format_review_files,
    format_review_timestamp,
    git_diff,
)


class ReviewGenerationTests(unittest.TestCase):
    def test_build_prompt_assembles_expected_sections(self):
        review_id = "rev-123"
        timestamp = "2026-05-05T08:00:00+07:00"
        readable_timestamp = format_review_timestamp(timestamp)
        entries = [EditRecord(timestamp="2026-05-05T08:00:00+07:00", file="src/app.ts", hash="abc123")]
        rules = "Rule one."
        diff = "-old\n+new"
        snapshots = "## src/app.ts\n\n```ts\nconst value = 2;\n```"
        review_path = Path("/tmp/review-123.md")

        expected = f"""# Claude Auto Review Request {review_id}

You must review the changed files before stopping. Use the reviewer agent behavior from `agents/reviewer.md`: focus on semantic bugs, security, maintainability, and project rules. Do not nitpick formatting.

## Review Output

Output only the final review markdown to stdout. It will be captured and saved to the review file. Do not emit progress updates, planning notes, or any text before or after the final markdown review. You do not have Write or Edit tools.

Use this exact top matter:

```markdown
# Review {review_id} - {readable_timestamp}

## Files Reviewed
- src/app.ts (hash: abc123)

## Findings
```

If no findings exist, write "Clean - no issues found. Claude may stop." under "## Verdict".
If you record one or more findings under "## Findings", you MUST NOT use a clean verdict. End with a blocking verdict such as "N issues found. Claude must address all findings before stopping."

## Files To Review
- src/app.ts (hash: abc123)

## Rules
Rule one.

## Git Diff
```diff
-old
+new
```

## Current File Snapshots
{snapshots}

Complete the review in a single response."""

        self.assertEqual(
            build_prompt(review_id, timestamp, entries, rules, diff, snapshots, review_path),
            expected,
        )

    def test_format_review_file_matches_prompt_file_body(self):
        readable_timestamp = "2026-05-05 | 08:00:00 +07:00"
        file_list = "- src/app.ts (hash: abc123)"
        prompt_path = Path("/tmp/review-123-prompt.md")

        expected = f"""# Review rev-123 - {readable_timestamp}

## Files Reviewed
{file_list}

## Findings

No findings yet. This file is a placeholder until Claude completes the review.

Pending. Claude must complete this review from {prompt_path}.

## Verdict

Pending.
"""

        self.assertEqual(
            format_review_file("rev-123", readable_timestamp, file_list, prompt_path),
            expected,
        )

    def test_format_review_files_builds_review_body_from_entries(self):
        timestamp = "2026-05-05T08:00:00+07:00"
        entries = [EditRecord(timestamp="2026-05-05T08:00:00+07:00", file="src/app.ts", hash="abc123")]
        prompt_path = Path("/tmp/review-123-prompt.md")
        expected = format_review_file(
            "rev-123",
            format_review_timestamp(timestamp),
            "- src/app.ts (hash: abc123)",
            prompt_path,
        )

        self.assertEqual(
            format_review_files(entries, prompt_path, "rev-123", timestamp),
            expected,
        )

    def test_current_file_snapshots_formats_missing_and_truncated_files(self):
        project_root = Path(tempfile.mkdtemp(prefix="claude-auto-review-snapshots-"))
        present = project_root / "src" / "present.ts"
        present.parent.mkdir(parents=True, exist_ok=True)
        present.write_text("x" * 10005, encoding="utf-8")

        snapshots = current_file_snapshots(["src/present.ts", "src/missing.ts"], project_root)

        self.assertIn("## src/present.ts", snapshots)
        self.assertIn("[truncated at 10000 characters]", snapshots)
        self.assertIn("## src/missing.ts", snapshots)
        self.assertIn("File does not currently exist.", snapshots)

    def test_git_diff_uses_real_git_output_when_repo_is_available(self):
        diff = git_diff([], REPO_ROOT)

        self.assertIsInstance(diff, str)


if __name__ == "__main__":
    unittest.main()
