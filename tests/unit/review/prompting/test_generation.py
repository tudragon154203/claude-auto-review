import tempfile
import unittest
from pathlib import Path

from claude_auto_review.review.prompting.generation import (
    build_prompt,
    format_review_files,
    git_diff,
)
from claude_auto_review.review.prompting.rendering import current_file_snapshots, format_review_timestamp
from claude_auto_review.review.prompting.templates import format_review_file
from claude_auto_review.state.edit_record import EditRecord

REPO_ROOT = Path(__file__).resolve().parents[4]


class ReviewGenerationTests(unittest.TestCase):
    def test_build_prompt_assembles_expected_sections(self):
        review_id = "rev-123"
        timestamp = "2026-05-05T08:00:00+07:00"
        readable_timestamp = format_review_timestamp(timestamp)
        entries = [EditRecord(timestamp="2026-05-05T08:00:00+07:00", file="src/app.ts", hash="abc123")]
        rules = "Rule one."
        diff = "-old\n+new"
        review_path = Path("/tmp/review-123.md")

        expected = (
            f"# Claude Auto Review Request {review_id}\n"
            "\n"
            "You must review the changed files before stopping. Use the reviewer agent behavior from"
            " `agents/reviewer.md`: focus on semantic bugs, security, maintainability, and project rules."
            " Do not nitpick formatting.\n"
            "\n"
            "## Review Output\n"
            "\n"
            "Output only the final review markdown to stdout. It will be captured and saved to the review"
            " file. Do not emit progress updates, planning notes, or any text before or after the final"
            " markdown review. You do not have Write or Edit tools.\n"
            "\n"
            "Use this exact structure. The review is parsed by a regex-based parser. Any deviation from this format causes findings to be lost.\n"
            "\n"
            "```markdown\n"
            f"# Review {review_id} - {readable_timestamp}\n"
            "\n"
            "## Reviewer\n"
            "Backend: claude | Model: \n"
            "\n"
            "## Files Reviewed\n"
            "- src/app.ts (hash: abc123)\n"
            "\n"
            "## Findings\n"
            "- Confirmed: <title>\n"
            "  Severity: <info|low|medium|high|critical>\n"
            "  Location: path:line\n"
            "  Rationale: <why this matters>\n"
            "  Suggestion: <concrete fix>\n"
            "- Skipped: <title>\n"
            "  Reason: <why this item cannot be reviewed>\n"
            "\n"
            "## Verdict\n"
            "Clean - no issues found. Claude may stop.\n"
            "```\n"
            "\n"
            "Rules for `## Findings`:\n"
            "- Use only top-level `- Confirmed:` or `- Skipped:` entries for findings.\n"
            "- Put details on indented `Field: value` lines under that bullet.\n"
            "  Field names and values must be plain text — no bold, no italics, no backticks.\n"
            "  Correct: `  Severity: high`\n"
            "  Wrong:   `  **Severity:** high` or `  - Severity: high`\n"
            "- Severity value must be one of: `info`, `low`, `medium`, `high`, `critical` — lowercase only.\n"
            "- If there are no findings, write exactly `None.` under `## Findings`.\n"
            "- Do not write notes, commentary, or summaries inside `## Findings`.\n"
            "- Do not add blank lines, horizontal rules, or code blocks between findings.\n"
            "\n"
            "Rules for `## Verdict`:\n"
            "- If `## Findings` is exactly `None.`, write verbatim: `Clean - no issues found. Claude may stop.`\n"
            "- Otherwise write verbatim: `Findings present. Claude must address all findings before stopping.`\n"
            "\n"
            "Incorrect formats (parser will ignore these):\n"
            "```\n"
            "- **Confirmed:** title\n"
            "  **Severity:** High\n"
            "### Confirmed - High - title\n"
            "- Confirmed: title (severity: medium)\n"
            "Clean — no issues found\n"
            "```\n"
            "\n"
            "## Files To Review\n"
            "- src/app.ts (hash: abc123)\n"
            "\n"
            "## Rules\n"
            "Rule one.\n"
            "\n"
            "## Session Diff\n"
            "The diff below contains only changes made during this Claude Code session, compared against the file state before the first edit.\n"
            "\n"
            "```diff\n"
            "-old\n"
            "+new\n"
            "```\n"
            "\n"
            "Complete the review in a single response."
        )

        self.assertEqual(build_prompt(review_id, timestamp, entries, rules, diff, review_path), expected)

    def test_format_review_file_matches_prompt_file_body(self):
        readable_timestamp = "2026-05-05 | 08:00:00 +07:00"
        file_list = "- src/app.ts (hash: abc123)"
        prompt_path = Path("/tmp/review-123-prompt.md")

        result = format_review_file("rev-123", readable_timestamp, file_list, prompt_path)

        # prompt_path str representation is platform-dependent; test key structural parts
        self.assertIn("# Review rev-123 - 2026-05-05 | 08:00:00 +07:00", result)
        self.assertIn("## Reviewer\nBackend: claude | Model: ", result)
        self.assertIn("## Files Reviewed", result)
        self.assertIn(file_list, result)
        self.assertIn("No findings yet. This file is a placeholder until Claude completes the review.", result)
        self.assertIn("Pending. Claude must complete this review from", result)
        self.assertIn("## Verdict", result)
        self.assertIn("Pending.", result)

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
