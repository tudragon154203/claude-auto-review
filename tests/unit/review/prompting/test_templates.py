import unittest

from claude_auto_review.review.prompting.templates import (
    build_prompt,
    format_review_file,
    format_review_prompt,
    format_review_files,
)


class TestPromptTemplates(unittest.TestCase):
    def test_format_review_prompt_includes_all_sections(self):
        result = format_review_prompt(
            review_id="rev-123",
            readable_timestamp="May 15, 2026 10:00 AM",
            file_list="- src/app.ts (hash: abc123)",
            rules="Rule one.\nRule two.",
            diff="-old\n+new",
            snapshots="## src/app.ts\n```ts\nconst value = 1\n```",
            review_path="/tmp/review-123.md",
        )

        self.assertIn("# Claude Auto Review Request rev-123", result)
        self.assertIn("# Review rev-123 - May 15, 2026 10:00 AM", result)
        self.assertIn("## Files Reviewed", result)
        self.assertIn("- src/app.ts (hash: abc123)", result)
        self.assertIn("## Findings", result)
        self.assertIn("## Files To Review", result)
        self.assertIn("## Rules", result)
        self.assertIn("Rule one.\nRule two.", result)
        self.assertIn("## Git Diff", result)
        self.assertIn("```diff\n-old\n+new\n```", result)
        self.assertIn("## Current File Snapshots", result)
        self.assertIn("Output only the final review markdown to stdout.", result)
        self.assertIn("Do not emit progress updates, planning notes, or any text before or after the final markdown review.", result)
        self.assertIn("Complete the review in a single response.", result)
        self.assertIn('If you record one or more findings under "## Findings", you MUST NOT use a clean verdict.', result)
        self.assertNotIn("/tmp/review-123.md", result)

    def test_format_review_file_includes_prompt_path_placeholder(self):
        result = format_review_file(
            review_id="rev-123",
            readable_timestamp="May 15, 2026 10:00 AM",
            file_list="- src/app.ts (hash: abc123)",
            prompt_path="/tmp/review-123-prompt.md",
        )

        self.assertIn("# Review rev-123 - May 15, 2026 10:00 AM", result)
        self.assertIn("## Files Reviewed", result)
        self.assertIn("- src/app.ts (hash: abc123)", result)
        self.assertIn("## Findings", result)
        self.assertIn("No findings yet. This file is a placeholder until Claude completes the review.", result)
        self.assertIn("Pending. Claude must complete this review from /tmp/review-123-prompt.md.", result)
        self.assertIn("## Verdict", result)
        self.assertIn("Pending.", result)

    def test_format_review_files_uses_review_context(self):
        calls = []

        def review_context(entries, timestamp):
            calls.append((entries, timestamp))
            return "May 15, 2026 10:00 AM", "- src/app.ts (hash: abc123)"

        entries = [object()]
        result = format_review_files(
            entries,
            prompt_path="/tmp/review-123-prompt.md",
            review_id="rev-123",
            timestamp="2026-05-15T10:00:00+07:00",
            review_context=review_context,
        )

        self.assertEqual(calls, [(entries, "2026-05-15T10:00:00+07:00")])
        self.assertEqual(
            result,
            format_review_file(
                "rev-123",
                "May 15, 2026 10:00 AM",
                "- src/app.ts (hash: abc123)",
                "/tmp/review-123-prompt.md",
            ),
        )

    def test_build_prompt_uses_review_context(self):
        calls = []

        def review_context(entries, timestamp):
            calls.append((entries, timestamp))
            return "May 15, 2026 10:00 AM", "- src/app.ts (hash: abc123)"

        entries = [object()]
        result = build_prompt(
            review_id="rev-123",
            timestamp="2026-05-15T10:00:00+07:00",
            entries=entries,
            rules="Rule one.",
            diff="-old\n+new",
            snapshots="## src/app.ts",
            review_path="/tmp/review-123-prompt.md",
            review_context=review_context,
        )

        self.assertEqual(calls, [(entries, "2026-05-15T10:00:00+07:00")])
        self.assertEqual(
            result,
            format_review_prompt(
                "rev-123",
                "May 15, 2026 10:00 AM",
                "- src/app.ts (hash: abc123)",
                "Rule one.",
                "-old\n+new",
                "## src/app.ts",
                "/tmp/review-123-prompt.md",
            ),
        )


if __name__ == "__main__":
    unittest.main()
